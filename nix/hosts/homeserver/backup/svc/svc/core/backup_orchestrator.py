"""Backup orchestration logic."""

import logging
from dataclasses import dataclass, field
from typing import cast

from ..config import Config, ServiceConfig
from ..controllers import ResticRunner, SystemctlController
from ..exceptions import EXIT_CONFIG_ERROR, EXIT_RESTIC_ERROR, EXIT_SUCCESS, SystemctlError
from .path_resolver import PathResolver
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
    needs_stop: bool
    volumes_count: int
    paths_count: int
    tags: list[str]


class BackupOrchestrator:
    """Orchestrates backup operations for services."""

    def __init__(
        self,
        config: Config,
        restic: ResticRunner,
        systemctl: SystemctlController,
        path_resolver: PathResolver,
    ):
        self.config = config
        self.restic = restic
        self.systemctl = systemctl
        self.path_resolver = path_resolver

    def get_backup_services(self, service_arg: str) -> list[ServiceConfig]:
        """Get list of services to backup based on argument."""
        if service_arg == "all":
            return [svc for svc in self.config.services.values() if svc.backup.enable]
        return [validate_service(self.config, service_arg)]

    def create_backup_plan(self, svc: ServiceConfig) -> BackupPlan:
        """Create a backup plan for a service."""
        return BackupPlan(
            service_name=svc.name,
            needs_stop=svc.backup.needs_service_stopped,
            volumes_count=len(svc.backup.volumes),
            paths_count=len(svc.backup.paths),
            tags=list(svc.backup.tags),
        )

    async def backup_service(self, svc: ServiceConfig) -> BackupResult:
        """
        Execute backup for a single service.

        Handles:
        - Path resolution
        - Service stopping (if needed)
        - Restic backup execution
        - Retention policy application
        - Service restart
        """
        dry_run_prefix = "[dry-run] " if self.restic.dry_run else ""

        paths, missing = await self.path_resolver.get_backup_paths(
            svc.backup.volumes, svc.backup.paths
        )

        # Validate paths
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

        compose_unit = f"docker-compose-{svc.name}.service"
        was_stopped = False

        # Stop service if needed
        if svc.backup.needs_service_stopped:
            is_loaded = await self.systemctl.is_loaded(compose_unit)
            is_active = await self.systemctl.is_active(compose_unit)

            if is_loaded and is_active:
                logger.info("Stopping %s...", compose_unit)
                await self.systemctl.stop(compose_unit)
                was_stopped = True

        try:
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
            # Restart service if we stopped it
            if was_stopped:
                try:
                    logger.info("Starting %s...", compose_unit)
                    await self.systemctl.start(compose_unit)
                except SystemctlError as e:
                    logger.warning("Failed to restart %s: %s", compose_unit, e)
