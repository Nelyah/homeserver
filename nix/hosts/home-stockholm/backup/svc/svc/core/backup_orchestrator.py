"""Backup orchestration logic."""

import asyncio
import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import cast

from ..config import Config, KubernetesBackupConfig, ServiceConfig
from ..controllers import DeploymentScale, KubernetesController, ResticRunner
from ..exceptions import (
    EXIT_CONFIG_ERROR,
    EXIT_RESTIC_ERROR,
    EXIT_SUCCESS,
    KubernetesError,
)
from .path_resolver import PathResolver, ResolvedPath
from .service_helpers import validate_service

logger = logging.getLogger("svc.core.backup")


@dataclass
class BackupResult:
    """Result of a backup operation."""

    service_name: str
    success: bool
    exit_code: int
    message: str
    paths_backed_up: list[str] = field(default_factory=lambda: cast("list[str]", []))
    missing_paths: list[str] = field(default_factory=lambda: cast("list[str]", []))
    forget_status: int | None = None


@dataclass
class BackupPlan:
    """Plan for backing up a service."""

    service_name: str
    scales_down: bool
    paths_count: int
    pvcs_count: int
    tags: list[str]


class BackupOrchestrator:
    """Orchestrates backup operations for services."""

    def __init__(
        self,
        config: Config,
        restic: ResticRunner,
        kubernetes: KubernetesController,
        path_resolver: PathResolver,
    ):
        self.config = config
        self.restic = restic
        self.kubernetes = kubernetes
        self.path_resolver = path_resolver

    def get_backup_services(self, service_arg: str) -> list[ServiceConfig]:
        """Get list of services to backup based on argument."""
        if service_arg == "all":
            return [svc for svc in self.config.services.values() if svc.backup.enable]
        return [validate_service(self.config, service_arg)]

    def create_backup_plan(self, svc: ServiceConfig) -> BackupPlan:
        """Create a backup plan for a service."""
        kubernetes = svc.backup.kubernetes
        return BackupPlan(
            service_name=svc.name,
            scales_down=kubernetes is not None and len(kubernetes.deployments) > 0,
            paths_count=len(svc.backup.paths),
            pvcs_count=len(kubernetes.pvcs) if kubernetes else 0,
            tags=list(svc.backup.tags),
        )

    async def backup_service(self, svc: ServiceConfig) -> BackupResult:
        """
        Execute backup for a single service.

        Handles:
        - Path resolution
        - Kubernetes deployment scaling (if configured)
        - Restic backup execution
        - Retention policy application
        """
        dry_run_prefix = "[dry-run] " if self.restic.dry_run else ""

        paths, invalid = await self._prepare_backup_paths(svc, dry_run_prefix)
        if invalid is not None:
            return invalid

        deployment_scales: list[DeploymentScale] = []

        try:
            deployment_scales = await self._scale_down_kubernetes_deployments(svc)

            # Run backup
            logger.info("Running restic backup...")
            status = await self.restic.backup(paths, svc.backup.tags, svc.backup.exclude)

            if status != 0:
                return BackupResult(
                    service_name=svc.name,
                    success=False,
                    exit_code=EXIT_RESTIC_ERROR,
                    message=f"{dry_run_prefix}Backup failed for {svc.name} (exit code {status})",
                    paths_backed_up=paths,
                )

            # Run forget if policy defined
            forget_status = None
            if svc.backup.policy is not None:
                logger.info("Running restic forget with retention policy...")
                forget_status = await self.restic.forget(svc.backup.tags, svc.backup.policy)

            return BackupResult(
                service_name=svc.name,
                success=True,
                exit_code=EXIT_SUCCESS,
                message=f"{dry_run_prefix}Backup completed for {svc.name}",
                paths_backed_up=paths,
                forget_status=forget_status,
            )

        finally:
            await self._restore_kubernetes_deployments(deployment_scales)

    async def _prepare_backup_paths(
        self, svc: ServiceConfig, dry_run_prefix: str
    ) -> tuple[list[str], BackupResult | None]:
        """Run preparation commands, resolve targets, and write metadata."""
        pre_backup_status = await self._run_pre_backup_commands(svc)
        if pre_backup_status != 0:
            return [], BackupResult(
                service_name=svc.name,
                success=False,
                exit_code=EXIT_CONFIG_ERROR,
                message=f"{dry_run_prefix}Pre-backup command failed for {svc.name}",
            )

        resolved, missing = await self.path_resolver.resolve_all(
            svc.backup.paths, svc.backup.kubernetes
        )
        paths = [r.filesystem_path for r in resolved]
        invalid = self._validate_backup_paths(svc, dry_run_prefix, paths, missing)
        if invalid is not None:
            return [], invalid

        try:
            metadata_path = self._write_kubernetes_backup_metadata(svc, resolved)
        except OSError as error:
            return [], BackupResult(
                service_name=svc.name,
                success=False,
                exit_code=EXIT_CONFIG_ERROR,
                message=f"Failed to write Kubernetes backup metadata: {error}",
            )
        if metadata_path is not None:
            paths.append(metadata_path)

        return paths, None

    def _validate_backup_paths(
        self,
        svc: ServiceConfig,
        dry_run_prefix: str,
        paths: list[str],
        missing: list[str],
    ) -> BackupResult | None:
        """Validate resolved backup paths."""
        if not paths:
            return BackupResult(
                service_name=svc.name,
                success=False,
                exit_code=EXIT_CONFIG_ERROR,
                message=f"{dry_run_prefix}No backup paths configured for {svc.name}",
            )

        if missing:
            return BackupResult(
                service_name=svc.name,
                success=False,
                exit_code=EXIT_CONFIG_ERROR,
                message="Configured backup targets are missing",
                missing_paths=missing,
            )

        return None

    async def _run_pre_backup_commands(self, svc: ServiceConfig) -> int:
        """Run commands configured to prepare backup targets."""
        for command in svc.backup.pre_backup_commands:
            if not command:
                continue

            logger.info("Running pre-backup command: %s", " ".join(command))
            if self.restic.dry_run:
                continue

            proc = await asyncio.create_subprocess_exec(*command)
            await proc.wait()
            if proc.returncode != 0:
                return proc.returncode or 1

        return 0

    def _write_kubernetes_backup_metadata(
        self, svc: ServiceConfig, resolved: list[ResolvedPath]
    ) -> str | None:
        """Write metadata needed to restore PVCs whose backing paths later change."""
        kubernetes = svc.backup.kubernetes
        if kubernetes is None or self.restic.dry_run:
            return None

        metadata_path = self._backup_metadata_path(svc.name)
        metadata_path.parent.mkdir(parents=True, mode=0o700, exist_ok=True)
        metadata = self._kubernetes_backup_metadata(svc.name, kubernetes, resolved)
        metadata_path.write_text(json.dumps(metadata, indent=2, sort_keys=True))
        metadata_path.chmod(0o600)
        return str(metadata_path)

    def _backup_metadata_path(self, service_name: str) -> Path:
        """Return the local path used for the service backup metadata file."""
        return Path(self.config.paths.backup_metadata_root) / f"{service_name}.json"

    def _kubernetes_backup_metadata(
        self,
        service_name: str,
        kubernetes: KubernetesBackupConfig,
        resolved: list[ResolvedPath],
    ) -> dict[str, object]:
        """Build snapshot metadata for Kubernetes backup targets."""
        pvc_entries: list[dict[str, str]] = []
        for item in resolved:
            if item.source_type != "kubernetes-pvc":
                continue

            namespace, _, pvc = item.source_name.partition("/")
            pvc_entries.append(
                {
                    "namespace": namespace,
                    "name": pvc,
                    "source": item.source_name,
                    "path": item.filesystem_path,
                }
            )

        return {
            "version": 1,
            "service": service_name,
            "kubernetes": {
                "namespace": kubernetes.namespace,
                "deployments": list(kubernetes.deployments),
                "pvcs": pvc_entries,
            },
        }

    async def _scale_down_kubernetes_deployments(
        self, svc: ServiceConfig
    ) -> list[DeploymentScale]:
        """Scale configured Kubernetes deployments to zero for a consistent backup."""
        kubernetes = svc.backup.kubernetes
        if kubernetes is None:
            return []

        original_scales: list[DeploymentScale] = []
        try:
            for deployment in kubernetes.deployments:
                scale = await self.kubernetes.deployment_scale(kubernetes.namespace, deployment)
                original_scales.append(scale)
                if scale.replicas == 0:
                    continue

                await self.kubernetes.scale_deployment(scale, 0)
                await self.kubernetes.wait_for_deployment_replicas(
                    scale.namespace,
                    scale.name,
                    0,
                )
        except KubernetesError:
            await self._restore_kubernetes_deployments(original_scales)
            raise

        return original_scales

    async def _restore_kubernetes_deployments(
        self, deployment_scales: list[DeploymentScale]
    ) -> None:
        """Restore Kubernetes deployments to their original replica counts."""
        for scale in reversed(deployment_scales):
            if scale.replicas == 0:
                continue

            try:
                await self.kubernetes.scale_deployment(scale, scale.replicas)
                await self.kubernetes.wait_for_deployment_replicas(
                    scale.namespace,
                    scale.name,
                    scale.replicas,
                )
            except KubernetesError as error:
                logger.warning(
                    "Failed to restore deployment/%s in %s: %s",
                    scale.name,
                    scale.namespace,
                    error,
                )
