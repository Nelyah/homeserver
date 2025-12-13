"""Restore command."""

import logging

from ...config import load_restic_env
from ...core import RestoreOrchestrator, require_root, validate_service
from ..args import RestoreArgs
from .base import AppContext, Command

logger = logging.getLogger("svc.cli.restore")


class RestoreCommand(Command[RestoreArgs]):
    """Restore a service from backup."""

    async def execute(self, args: RestoreArgs, ctx: AppContext) -> int:
        """Restore a service snapshot and render results."""
        env = args.env
        service_name = args.service
        snapshot_spec = args.snapshot
        verify_includes = args.verify_includes

        require_root(f"restore {service_name}")

        svc = validate_service(ctx.config, service_name)

        # Load restic environment
        env_vars = load_restic_env(ctx.config.paths.secrets_root, env)
        restic = ctx.create_restic_runner(env_vars)

        # Create orchestrator
        orchestrator = RestoreOrchestrator(
            config=ctx.config,
            restic=restic,
            systemctl=ctx.systemctl,
            path_resolver=ctx.path_resolver,
        )

        ctx.renderer.print_heading(f"Restore: {service_name} ({env})")

        if ctx.dry_run:
            ctx.renderer.print_warn("Dry run enabled: no changes will be made")

        # Execute restore
        result = await orchestrator.restore_service(
            svc=svc,
            snapshot_spec=snapshot_spec,
            verify_includes=verify_includes,
        )

        if result.missing_in_snapshot:
            ctx.renderer.print_warn(
                "Snapshot is missing some expected paths "
                "(likely volumes added after snapshot): " + ", ".join(result.missing_in_snapshot)
            )

        if result.success:
            ctx.renderer.print_ok(result.message)
        else:
            ctx.renderer.print_error(result.message)

        return result.exit_code
