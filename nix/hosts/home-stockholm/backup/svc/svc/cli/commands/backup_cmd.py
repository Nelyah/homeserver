"""Backup command."""

from ...config import ServiceConfig, load_restic_env
from ...core import BackupOrchestrator, BackupResult, require_root
from ...exceptions import EXIT_SUCCESS
from ..args import BackupArgs
from ..renderer import TableColumn, TableRow
from .base import AppContext, Command


class BackupCommand(Command[BackupArgs]):
    """Run backup for one or all services."""

    async def execute(self, args: BackupArgs, ctx: AppContext) -> int:
        """Execute backups and render a plan + summary."""
        env = args.env
        orchestrator = self._orchestrator(env, ctx)
        services: list[ServiceConfig] = orchestrator.get_backup_services(args.service)
        if not services:
            ctx.renderer.print_warn("No services with backup enabled")
            return EXIT_SUCCESS

        self._require_root_if_needed(services)

        self._render_plan(ctx, orchestrator, env, services)
        results, overall_status = await self._run_backups(ctx, orchestrator, env, services)
        self._render_results(ctx, results)
        return overall_status

    def _orchestrator(self, env: str, ctx: AppContext) -> BackupOrchestrator:
        """Create a BackupOrchestrator for the selected restic env."""
        env_vars = load_restic_env(ctx.config.paths.secrets_root, env)
        restic = ctx.create_restic_runner(env_vars)
        return BackupOrchestrator(
            config=ctx.config,
            restic=restic,
            systemctl=ctx.systemctl,
            path_resolver=ctx.path_resolver,
        )

    def _require_root_if_needed(self, services: list[ServiceConfig]) -> None:
        """Require root if any service needs to be stopped for backup."""
        for svc in services:
            if svc.backup.needs_service_stopped:
                require_root(f"backup {svc.name} (needsServiceStopped)")

    def _render_plan(
        self,
        ctx: AppContext,
        orchestrator: BackupOrchestrator,
        env: str,
        services: list[ServiceConfig],
    ) -> None:
        """Render the backup plan table."""
        columns = [
            TableColumn("Service", style="bold"),
            TableColumn("Stop", justify="center"),
            TableColumn("Volumes", justify="right"),
            TableColumn("Paths", justify="right"),
            TableColumn("Tags"),
        ]

        rows: list[TableRow] = []
        for svc in services:
            plan = orchestrator.create_backup_plan(svc)
            stop_display = "yes" if plan.needs_stop else "no"
            rows.append(
                TableRow(
                    cells=[
                        plan.service_name,
                        stop_display,
                        str(plan.volumes_count),
                        str(plan.paths_count),
                        ", ".join(plan.tags),
                    ]
                )
            )

        ctx.renderer.render_table(f"Backup plan ({env})", columns, rows)

    async def _run_backups(
        self,
        ctx: AppContext,
        orchestrator: BackupOrchestrator,
        env: str,
        services: list[ServiceConfig],
    ) -> tuple[list[tuple[str, int]], int]:
        """Run backups for each service and return (results, overall_status)."""
        results: list[tuple[str, int]] = []
        overall_status = EXIT_SUCCESS

        for svc in services:
            ctx.renderer.print_heading(f"Backup: {svc.name} ({env})")
            if ctx.dry_run:
                ctx.renderer.print_warn("Dry run enabled: no changes will be made")

            result = await orchestrator.backup_service(svc)
            if result.exit_code != EXIT_SUCCESS:
                overall_status = result.exit_code
            self._render_backup_result(ctx, svc.name, result)
            results.append((svc.name, result.exit_code))

        return results, overall_status

    def _render_backup_result(
        self, ctx: AppContext, name: str, result: BackupResult
    ) -> None:
        """Render per-service backup result messages."""
        if result.success:
            ctx.renderer.print_ok(result.message)
        else:
            ctx.renderer.print_error(result.message)
            if result.missing_paths:
                missing = ", ".join(result.missing_paths)
                ctx.renderer.print_error(f"Missing paths: {missing}")

        if result.forget_status is not None and result.forget_status != 0:
            ctx.renderer.print_warn(f"Forget failed for {name} (exit code {result.forget_status})")

    def _render_results(self, ctx: AppContext, results: list[tuple[str, int]]) -> None:
        """Render the final backup summary table."""
        columns = [
            TableColumn("Service", style="bold"),
            TableColumn("Result"),
        ]
        rows = [
            TableRow(
                cells=[
                    name,
                    "OK" if code == EXIT_SUCCESS else f"FAIL ({code})",
                ]
            )
            for name, code in results
        ]
        ctx.renderer.render_table("Backup results", columns, rows)
