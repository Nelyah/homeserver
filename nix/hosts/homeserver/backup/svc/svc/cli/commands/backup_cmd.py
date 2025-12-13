"""Backup command."""

import argparse

from ...config import load_restic_env
from ...core import BackupOrchestrator, require_root
from ...exceptions import EXIT_SUCCESS
from ..renderer import TableColumn, TableRow
from .base import AppContext, Command


class BackupCommand(Command):
    """Run backup for one or all services."""

    async def execute(self, args: argparse.Namespace, ctx: AppContext) -> int:
        env = args.env
        orchestrator = self._orchestrator(env, ctx)
        services = orchestrator.get_backup_services(args.service)
        if not services:
            ctx.renderer.print_warn("No services with backup enabled")
            return EXIT_SUCCESS

        self._require_root_if_needed(services)

        self._render_plan(ctx, orchestrator, env, services)
        results, overall_status = await self._run_backups(ctx, orchestrator, env, services)
        self._render_results(ctx, results)
        return overall_status

    def _orchestrator(self, env: str, ctx: AppContext) -> BackupOrchestrator:
        env_vars = load_restic_env(ctx.config.paths.secrets_root, env)
        restic = ctx.create_restic_runner(env_vars)
        return BackupOrchestrator(
            config=ctx.config,
            restic=restic,
            systemctl=ctx.systemctl,
            path_resolver=ctx.path_resolver,
        )

    def _require_root_if_needed(self, services: list) -> None:
        for svc in services:
            if svc.backup.needs_service_stopped:
                require_root(f"backup {svc.name} (needsServiceStopped)")

    def _render_plan(
        self,
        ctx: AppContext,
        orchestrator: BackupOrchestrator,
        env: str,
        services: list,
    ) -> None:
        columns = [
            TableColumn("Service", style="bold"),
            TableColumn("Stop", justify="center"),
            TableColumn("Volumes", justify="right"),
            TableColumn("Paths", justify="right"),
            TableColumn("Tags"),
        ]

        rows = []
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
        services: list,
    ) -> tuple[list[tuple[str, int]], int]:
        results: list[tuple[str, int]] = []
        overall_status = EXIT_SUCCESS

        for svc in services:
            ctx.renderer.print_heading(f"Backup: {svc.name} ({env})")
            if ctx.dry_run:
                ctx.renderer.print_warn("Dry run enabled: no changes will be made")

            result = await orchestrator.backup_service(svc, dry_run=ctx.dry_run)
            if result.exit_code != EXIT_SUCCESS:
                overall_status = result.exit_code
            self._render_backup_result(ctx, svc.name, result)
            results.append((svc.name, result.exit_code))

        return results, overall_status

    def _render_backup_result(self, ctx: AppContext, name: str, result) -> None:
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
