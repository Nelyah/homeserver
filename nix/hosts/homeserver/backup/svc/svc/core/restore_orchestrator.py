"""Restore orchestration logic."""

import logging
from dataclasses import dataclass, field
from typing import cast

from ..config import Config, ServiceConfig
from ..controllers import ResticRunner, SystemctlController
from ..exceptions import EXIT_CONFIG_ERROR, EXIT_RESTIC_ERROR, EXIT_SUCCESS
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
    include_paths: list[str] = field(default_factory=lambda: cast(list[str], []))
    missing_in_snapshot: list[str] = field(default_factory=lambda: cast(list[str], []))


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
        else:
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
        # Resolve snapshot
        snapshot_id, error = await self.resolve_snapshot(svc, snapshot_spec)
        if error or not snapshot_id:
            return RestoreResult(
                service_name=svc.name,
                success=False,
                exit_code=EXIT_RESTIC_ERROR,
                message=error or "Failed to resolve snapshot",
            )

        # Resolve include paths
        include_paths, missing = await self.path_resolver.get_backup_paths(
            svc.restore.volumes, svc.restore.paths
        )

        if not include_paths:
            return RestoreResult(
                service_name=svc.name,
                success=False,
                exit_code=EXIT_CONFIG_ERROR,
                message=f"No restore paths configured for {svc.name}",
                snapshot_id=snapshot_id,
            )

        if missing:
            return RestoreResult(
                service_name=svc.name,
                success=False,
                exit_code=EXIT_CONFIG_ERROR,
                message="Configured restore targets do not exist (create docker volumes/paths first)",
                snapshot_id=snapshot_id,
            )

        logger.info(f"Snapshot: {snapshot_id[:8]}")
        logger.info("Restore includes:")
        for p in include_paths:
            logger.info(f"  {p}")

        # Verify includes if requested
        missing_in_snapshot: list[str] = []
        if verify_includes:
            missing_in_snapshot = await self.verify_snapshot_includes(
                snapshot_id, include_paths
            )

        compose_unit = svc.restore.compose_unit
        was_stopped = False

        # Stop service if configured
        if svc.restore.stop_compose and compose_unit:
            is_loaded = await self.systemctl.is_loaded(compose_unit)
            is_active = await self.systemctl.is_active(compose_unit)

            if is_loaded and is_active:
                logger.info(f"Stopping {compose_unit}...")
                await self.systemctl.stop(compose_unit)
                was_stopped = True

        try:
            # Run restore
            logger.info("Running restic restore...")
            status = await self.restic.restore(
                snapshot_id, include_paths, svc.restore.target
            )

            if status != 0:
                return RestoreResult(
                    service_name=svc.name,
                    success=False,
                    exit_code=EXIT_RESTIC_ERROR,
                    message=f"Restore failed for {svc.name} (exit code {status})",
                    snapshot_id=snapshot_id,
                    include_paths=include_paths,
                )

            return RestoreResult(
                service_name=svc.name,
                success=True,
                exit_code=EXIT_SUCCESS,
                message=f"Restore completed for {svc.name}",
                snapshot_id=snapshot_id,
                include_paths=include_paths,
                missing_in_snapshot=missing_in_snapshot,
            )

        finally:
            # Restart service if we stopped it
            if was_stopped and compose_unit:
                try:
                    is_loaded = await self.systemctl.is_loaded(compose_unit)
                    if is_loaded:
                        logger.info(f"Starting {compose_unit}...")
                        await self.systemctl.start(compose_unit)
                except Exception as e:
                    logger.warning(f"Failed to restart {compose_unit}: {e}")
