"""Restore orchestration logic."""

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, cast

from ..config import Config, ServiceConfig
from ..controllers import DeploymentScale, KubernetesController, ResticRunner
from ..exceptions import (
    EXIT_CONFIG_ERROR,
    EXIT_RESTIC_ERROR,
    EXIT_SUCCESS,
    KubernetesError,
)
from .path_resolver import PathResolver, ResolvedPath

logger = logging.getLogger("svc.core.restore")


@dataclass
class RestoreResult:
    """Result of a restore operation."""

    service_name: str
    success: bool
    exit_code: int
    message: str
    snapshot_id: str = ""
    include_paths: list[str] = field(default_factory=lambda: cast("list[str]", []))
    missing_in_snapshot: list[str] = field(default_factory=lambda: cast("list[str]", []))


@dataclass
class KubernetesRestoreTarget:
    """A PVC restore target with snapshot and current filesystem paths."""

    source_name: str
    snapshot_path: str
    current_path: str


class RestoreOrchestrator:
    """Orchestrates restore operations for services."""

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

    async def resolve_snapshot(
        self, svc: ServiceConfig, snapshot_spec: str
    ) -> tuple[str | None, str | None]:
        """
        Resolve snapshot specification to snapshot ID.

        Returns:
            Tuple of (snapshot_id, error_message)

        """
        if snapshot_spec == "latest":
            snapshot_id = await self.restic.get_latest_snapshot_id(svc.restore.tag)
            if not snapshot_id:
                return None, f"No snapshots found for {svc.name} (tag: {svc.restore.tag})"
            logger.info(f"Resolved 'latest' to snapshot {snapshot_id[:8]}")
            return snapshot_id, None
        return snapshot_spec, None

    async def verify_snapshot_includes(
        self, snapshot_id: str, include_paths: list[str]
    ) -> list[str]:
        """
        Verify which paths exist in the snapshot.

        Returns:
            List of paths that are missing from the snapshot.

        """
        missing: list[str] = []
        for p in include_paths:
            result = await self.restic.ls(snapshot_id, path=p)
            if result.returncode != 0:
                missing.append(p)
        return missing

    async def restore_service(
        self,
        svc: ServiceConfig,
        snapshot_spec: str,
        verify_includes: bool = False,
    ) -> RestoreResult:
        """
        Execute restore for a single service.

        Handles:
        - Snapshot resolution
        - Path validation
        - Kubernetes deployment scaling (if configured)
        - Restic restore execution
        """
        snapshot_id, error = await self.resolve_snapshot(svc, snapshot_spec)
        if error or not snapshot_id:
            message = error or "Failed to resolve snapshot"
            return RestoreResult(
                service_name=svc.name,
                success=False,
                exit_code=EXIT_RESTIC_ERROR,
                message=message,
            )

        resolved, missing = await self.path_resolver.resolve_all(
            svc.restore.paths, svc.restore.kubernetes
        )
        include_paths = [
            r.filesystem_path for r in resolved if r.source_type != "kubernetes-pvc"
        ]
        kubernetes_targets = await self._kubernetes_restore_targets(snapshot_id, svc, resolved)
        restore_paths = include_paths + [t.current_path for t in kubernetes_targets]
        snapshot_paths = include_paths + [t.snapshot_path for t in kubernetes_targets]

        invalid = self._validate_include_paths(svc, snapshot_id, restore_paths, missing)
        if invalid is not None:
            return invalid

        self._log_restore_plan(snapshot_id, include_paths, kubernetes_targets)

        missing_in_snapshot: list[str] = []
        if verify_includes:
            missing_in_snapshot = await self.verify_snapshot_includes(snapshot_id, snapshot_paths)

        deployment_scales: list[DeploymentScale] = []
        try:
            deployment_scales = await self._scale_down_kubernetes_deployments(svc)
            status = await self._restore_paths(snapshot_id, include_paths, svc.restore.target)
            if status == 0:
                status = await self._restore_kubernetes_targets(snapshot_id, kubernetes_targets)
        finally:
            await self._restore_kubernetes_deployments(deployment_scales)

        if status != 0:
            message = f"Restore failed for {svc.name} (exit code {status})"
            return RestoreResult(
                service_name=svc.name,
                success=False,
                exit_code=EXIT_RESTIC_ERROR,
                message=message,
                snapshot_id=snapshot_id,
                include_paths=restore_paths,
            )

        dry_run_prefix = "[dry-run] " if self.restic.dry_run else ""
        message = f"{dry_run_prefix}Restore completed for {svc.name}"
        return RestoreResult(
            service_name=svc.name,
            success=True,
            exit_code=EXIT_SUCCESS,
            message=message,
            snapshot_id=snapshot_id,
            include_paths=restore_paths,
            missing_in_snapshot=missing_in_snapshot,
        )

    def _validate_include_paths(
        self,
        svc: ServiceConfig,
        snapshot_id: str,
        include_paths: list[str],
        missing: list[str],
    ) -> RestoreResult | None:
        """Validate include paths and return an early RestoreResult on failure."""
        if not include_paths:
            message = f"No restore paths configured for {svc.name}"
            return RestoreResult(
                service_name=svc.name,
                success=False,
                exit_code=EXIT_CONFIG_ERROR,
                message=message,
                snapshot_id=snapshot_id,
            )

        if missing:
            message = "Configured restore targets do not exist"
            return RestoreResult(
                service_name=svc.name,
                success=False,
                exit_code=EXIT_CONFIG_ERROR,
                message=message,
                snapshot_id=snapshot_id,
            )

        return None

    def _log_restore_plan(
        self,
        snapshot_id: str,
        include_paths: list[str],
        kubernetes_targets: list[KubernetesRestoreTarget],
    ) -> None:
        """Log the restore plan to the application logger."""
        logger.info("Snapshot: %s", snapshot_id[:8])
        logger.info("Restore includes:")
        for path in include_paths:
            logger.info("  %s", path)
        for target in kubernetes_targets:
            logger.info("  %s -> %s", target.snapshot_path, target.current_path)

    async def _restore_paths(
        self, snapshot_id: str, include_paths: list[str], target: str
    ) -> int:
        """Restore raw filesystem path targets."""
        if not include_paths:
            return 0

        logger.info("Running restic restore...")
        return await self.restic.restore(snapshot_id, include_paths, target)

    async def _restore_kubernetes_targets(
        self, snapshot_id: str, targets: list[KubernetesRestoreTarget]
    ) -> int:
        """Restore Kubernetes PVC targets using restic subfolder restore."""
        for target in targets:
            logger.info(
                "Restoring %s from %s to %s...",
                target.source_name,
                target.snapshot_path,
                target.current_path,
            )
            status = await self.restic.restore_subfolder(
                snapshot_id,
                target.snapshot_path,
                target.current_path,
                delete=True,
            )
            if status != 0:
                return status
        return 0

    async def _kubernetes_restore_targets(
        self,
        snapshot_id: str,
        svc: ServiceConfig,
        resolved: list[ResolvedPath],
    ) -> list[KubernetesRestoreTarget]:
        """Build Kubernetes restore targets from snapshot metadata and current PVC paths."""
        metadata = await self._load_backup_metadata(snapshot_id, svc.name)
        snapshot_paths = self._snapshot_pvc_paths(metadata)
        targets: list[KubernetesRestoreTarget] = []

        for item in resolved:
            if item.source_type != "kubernetes-pvc":
                continue

            targets.append(
                KubernetesRestoreTarget(
                    source_name=item.source_name,
                    snapshot_path=snapshot_paths.get(item.source_name, item.filesystem_path),
                    current_path=item.filesystem_path,
                )
            )

        return targets

    async def _load_backup_metadata(
        self, snapshot_id: str, service_name: str
    ) -> dict[str, Any]:
        """Load service backup metadata from a snapshot if present."""
        result = await self.restic.dump_file(snapshot_id, str(self._backup_metadata_path(service_name)))
        if result.returncode != 0:
            return {}

        try:
            raw = json.loads(result.stdout)
        except json.JSONDecodeError:
            return {}

        return cast("dict[str, Any]", raw) if isinstance(raw, dict) else {}

    def _backup_metadata_path(self, service_name: str) -> Path:
        """Return the snapshot path used for the service backup metadata file."""
        return Path(self.config.paths.backup_metadata_root) / f"{service_name}.json"

    def _snapshot_pvc_paths(self, metadata: dict[str, Any]) -> dict[str, str]:
        """Extract namespace/PVC to snapshot path mappings from metadata."""
        kubernetes = metadata.get("kubernetes")
        if not isinstance(kubernetes, dict):
            return {}

        pvcs = kubernetes.get("pvcs")
        if not isinstance(pvcs, list):
            return {}

        result: dict[str, str] = {}
        for item in pvcs:
            if not isinstance(item, dict):
                continue

            source = item.get("source")
            path = item.get("path")
            if isinstance(source, str) and isinstance(path, str):
                result[source] = path

        return result

    async def _scale_down_kubernetes_deployments(
        self, svc: ServiceConfig
    ) -> list[DeploymentScale]:
        """Scale configured Kubernetes deployments to zero for restore."""
        kubernetes = svc.restore.kubernetes
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
