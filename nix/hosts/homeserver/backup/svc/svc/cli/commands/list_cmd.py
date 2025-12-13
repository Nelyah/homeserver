"""List services command."""

import argparse
from pathlib import Path

from ...config import load_restic_env
from ...controllers import unit_last_success
from ...controllers.restic import ResticSnapshot
from ...core import validate_service
from ...exceptions import EXIT_SUCCESS
from ..renderer import TableColumn, TableRow
from .base import AppContext, Command


class ListCommand(Command):
    """List all services and their status."""

    async def execute(self, args: argparse.Namespace, ctx: AppContext) -> int:
        services = sorted(ctx.config.services.keys())
        if not services:
            ctx.renderer.print_warn("No services found in config")
            return EXIT_SUCCESS

        backup_env = getattr(args, "backup_env", "local")
        global_backup_unit = "backup.service" if backup_env == "local" else "backup-remote.service"

        global_last_ok = await unit_last_success(ctx.systemctl, global_backup_unit)

        def is_deployed(service_name: str) -> bool:
            deploy_dir = Path(ctx.config.paths.deploy_root) / service_name
            try:
                return deploy_dir.is_dir()
            except Exception:
                return False

        async def last_backup_ok(service_name: str, backup_enabled: bool) -> bool:
            if not backup_enabled:
                return False

            per_service_unit = f"backup-{service_name}.service"
            per_service_result = await unit_last_success(ctx.systemctl, per_service_unit)
            if per_service_result is not None:
                return bool(per_service_result)

            return bool(global_last_ok is True)

        columns = [
            TableColumn("Service", style="bold"),
            TableColumn("Deployed", justify="center"),
            TableColumn("Backup", justify="center"),
            TableColumn(f"Last backup ({backup_env})", justify="center"),
        ]

        rows: list[TableRow] = []
        for name in services:
            svc = ctx.config.services[name]
            deployed_ok = is_deployed(name)
            backup_ok = bool(svc.backup.enable)
            last_ok = await last_backup_ok(name, backup_ok)

            rows.append(
                TableRow(
                    cells=[
                        name,
                        ctx.renderer.format_check(deployed_ok),
                        ctx.renderer.format_check(backup_ok),
                        ctx.renderer.format_check(last_ok),
                    ]
                )
            )

        ctx.renderer.render_table("Services", columns, rows)

        if global_last_ok is None:
            ctx.renderer.print_warn(f"Could not determine last result for {global_backup_unit}")

        return EXIT_SUCCESS


class ListBackupsCommand(Command):
    """List snapshots for a service."""

    async def execute(self, args: argparse.Namespace, ctx: AppContext) -> int:
        env = args.env
        service_name = args.service

        svc = validate_service(ctx.config, service_name)
        path_resolver = ctx.path_resolver

        resolved, missing = await path_resolver.resolve_all(svc.backup.volumes, svc.backup.paths)

        # Show backup contents table
        columns = [
            TableColumn("Type", style="bold"),
            TableColumn("Name/path"),
            TableColumn("Filesystem path"),
            TableColumn("Exists", justify="center"),
        ]

        rows: list[TableRow] = []
        for rp in resolved:
            rows.append(
                TableRow(
                    cells=[
                        rp.source_type,
                        rp.source_name,
                        rp.filesystem_path,
                        ctx.renderer.format_check(rp.exists),
                    ]
                )
            )

        if not resolved:
            rows.append(TableRow(cells=["—", "—", "—", "—"]))

        ctx.renderer.render_table(f"Backup contents: {service_name}", columns, rows)

        if missing:
            ctx.renderer.print_warn(
                "Some configured backup targets do not exist: " + ", ".join(missing)
            )

        # Load restic env and list snapshots
        env_vars = load_restic_env(ctx.config.paths.secrets_root, env)
        restic = ctx.create_restic_runner(env_vars)

        tag = svc.restore.tag
        snapshots: list[ResticSnapshot] = await restic.snapshots([tag])

        if not snapshots:
            ctx.renderer.print_info(f"No snapshots found for {service_name} (tag: {tag}) in {env}")
            return EXIT_SUCCESS

        # Show snapshots table
        snap_columns = [
            TableColumn("ID", style="bold"),
            TableColumn("Time"),
            TableColumn("Hostname"),
        ]

        snap_rows: list[TableRow] = []
        for snap in snapshots:
            snap_id = (snap.get("id") or "")[:8]
            time = (snap.get("time") or "")[:19]
            hostname = snap.get("hostname") or ""
            snap_rows.append(TableRow(cells=[snap_id, time, hostname]))

        ctx.renderer.render_table(f"Snapshots for {service_name} ({env})", snap_columns, snap_rows)

        return EXIT_SUCCESS
