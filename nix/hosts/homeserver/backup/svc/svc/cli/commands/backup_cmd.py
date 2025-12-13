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
        service_arg = args.service

        # Load restic environment
        env_vars = load_restic_env(ctx.config.paths.secrets_root, env)
        restic = ctx.create_restic_runner(env_vars)

        # Create orchestrator
        orchestrator = BackupOrchestrator(
            config=ctx.config,
            restic=restic,
            systemctl=ctx.systemctl,
            path_resolver=ctx.path_resolver,
        )

        # Get services to backup
        services = orchestrator.get_backup_services(service_arg)

        if not services:
            ctx.renderer.print_warn("No services with backup enabled")
            return EXIT_SUCCESS

        # Check if any service requires stopping (needs root)
        for svc in services:
            if svc.backup.needs_service_stopped:
                require_root(f"backup {svc.name} (needsServiceStopped)")

        # Show backup plan
        plan_columns = [
            TableColumn("Service", style="bold"),
            TableColumn("Stop", justify="center"),
            TableColumn("Volumes", justify="right"),
            TableColumn("Paths", justify="right"),
            TableColumn("Tags"),
        ]

        plan_rows: list[TableRow] = []
        for svc in services:
            plan = orchestrator.create_backup_plan(svc)
            stop_display = "yes" if plan.needs_stop else "no"
            plan_rows.append(
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

        ctx.renderer.render_table(f"Backup plan ({env})", plan_columns, plan_rows)

        # Execute backups
        results: list[tuple[str, int]] = []
        overall_status = EXIT_SUCCESS

        for svc in services:
            ctx.renderer.print_heading(f"Backup: {svc.name} ({env})")

            if ctx.dry_run:
                ctx.renderer.print_warn("Dry run enabled: no changes will be made")

            result = await orchestrator.backup_service(svc, dry_run=ctx.dry_run)

            if result.success:
                ctx.renderer.print_ok(result.message)
            else:
                ctx.renderer.print_error(result.message)
                if result.missing_paths:
                    ctx.renderer.print_error("Missing paths: " + ", ".join(result.missing_paths))
                overall_status = result.exit_code

            if result.forget_status is not None and result.forget_status != 0:
                ctx.renderer.print_warn(
                    f"Forget failed for {svc.name} (exit code {result.forget_status})"
                )

            results.append((svc.name, result.exit_code))

        # Show results summary
        result_columns = [
            TableColumn("Service", style="bold"),
            TableColumn("Result"),
        ]

        result_rows: list[TableRow] = []
        for name, code in results:
            status = "OK" if code == EXIT_SUCCESS else f"FAIL ({code})"
            result_rows.append(TableRow(cells=[name, status]))

        ctx.renderer.render_table("Backup results", result_columns, result_rows)

        return overall_status
