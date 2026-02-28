"""Restore orchestration logic."""

import logging
from dataclasses import dataclass, field
from typing import cast

from ..config import Config, ServiceConfig
from ..controllers import ResticRunner, SystemctlController
from ..exceptions import (
    EXIT_CONFIG_ERROR,
    EXIT_RESTIC_ERROR,
    EXIT_SUCCESS,
    SystemctlError,
)
from .path_resolver import PathResolver

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


class RestoreOrchestrator:
    """Orchestrates restore operations for services."""

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
        - Service stopping (if configured)
        - Restic restore execution
        - Service restart
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

        include_paths, missing = await self.path_resolver.get_backup_paths(
            svc.restore.volumes, svc.restore.paths
        )
        invalid = self._validate_include_paths(svc, snapshot_id, include_paths, missing)
        if invalid is not None:
            return invalid

        self._log_restore_plan(snapshot_id, include_paths)

        missing_in_snapshot: list[str] = []
        if verify_includes:
            missing_in_snapshot = await self.verify_snapshot_includes(snapshot_id, include_paths)

        was_stopped, compose_unit = await self._maybe_stop_compose(svc)
        try:
            logger.info("Running restic restore...")
            status = await self.restic.restore(snapshot_id, include_paths, svc.restore.target)
        finally:
            await self._maybe_restart_compose(was_stopped, compose_unit)

        if status != 0:
            message = f"Restore failed for {svc.name} (exit code {status})"
            return RestoreResult(
                service_name=svc.name,
                success=False,
                exit_code=EXIT_RESTIC_ERROR,
                message=message,
                snapshot_id=snapshot_id,
                include_paths=include_paths,
            )

        dry_run_prefix = "[dry-run] " if self.restic.dry_run else ""
        message = f"{dry_run_prefix}Restore completed for {svc.name}"
        return RestoreResult(
            service_name=svc.name,
            success=True,
            exit_code=EXIT_SUCCESS,
            message=message,
            snapshot_id=snapshot_id,
            include_paths=include_paths,
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
            message = "Configured restore targets do not exist (create docker volumes/paths first)"
            return RestoreResult(
                service_name=svc.name,
                success=False,
                exit_code=EXIT_CONFIG_ERROR,
                message=message,
                snapshot_id=snapshot_id,
            )

        return None

    def _log_restore_plan(self, snapshot_id: str, include_paths: list[str]) -> None:
        """Log the restore plan to the application logger."""
        logger.info("Snapshot: %s", snapshot_id[:8])
        logger.info("Restore includes:")
        for path in include_paths:
            logger.info("  %s", path)

    async def _maybe_stop_compose(self, svc: ServiceConfig) -> tuple[bool, str]:
        """Stop the compose service if configured; returns (stopped, unit)."""
        compose_unit = svc.restore.compose_unit
        if not svc.restore.stop_compose or not compose_unit:
            return False, compose_unit

        is_loaded = await self.systemctl.is_loaded(compose_unit)
        is_active = await self.systemctl.is_active(compose_unit)
        if is_loaded and is_active:
            logger.info("Stopping %s...", compose_unit)
            await self.systemctl.stop(compose_unit)
            return True, compose_unit

        return False, compose_unit

    async def _maybe_restart_compose(self, was_stopped: bool, compose_unit: str) -> None:
        """Restart a compose unit if it was stopped earlier."""
        if not was_stopped or not compose_unit:
            return

        try:
            is_loaded = await self.systemctl.is_loaded(compose_unit)
            if is_loaded:
                logger.info("Starting %s...", compose_unit)
                await self.systemctl.start(compose_unit)
        except SystemctlError as e:
            logger.warning("Failed to restart %s: %s", compose_unit, e)
