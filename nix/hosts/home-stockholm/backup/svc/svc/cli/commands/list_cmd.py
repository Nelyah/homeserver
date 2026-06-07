"""List services command."""

from typing import TYPE_CHECKING

from ...config import load_restic_env
from ...controllers import unit_last_success
from ...core import require_root, validate_service
from ...exceptions import EXIT_SUCCESS
from ..args import ListArgs, ListBackupsArgs
from ..renderer import TableColumn, TableRow
from .base import AppContext, Command

if TYPE_CHECKING:
    from ...config import ServiceConfig
    from ...controllers.restic import ResticSnapshot


def _last_backup_ok(*, backup_enabled: bool, global_last_ok: bool | None) -> bool:
    """Return the last backup result for this service based on global unit state."""
    if not backup_enabled:
        return False
    return bool(global_last_ok is True)


def _target_summary(svc: "ServiceConfig") -> str:
    """Summarize configured backup targets."""
    parts: list[str] = []
    if svc.backup.paths:
        parts.append(f"{len(svc.backup.paths)} path(s)")
    if svc.backup.kubernetes is not None and svc.backup.kubernetes.pvcs:
        parts.append(f"{len(svc.backup.kubernetes.pvcs)} pvc(s)")
    return ", ".join(parts) if parts else "-"

def _tag_summary(svc: "ServiceConfig") -> str:
    """Summarize restic tags."""
    return ", ".join(svc.backup.tags) if svc.backup.tags else "-"


class ListCommand(Command[ListArgs]):
    """List all services and their status."""

    async def execute(self, args: ListArgs, ctx: AppContext) -> int:
        """Render a table of configured backup services."""
        services = sorted(ctx.config.services.keys())
        if not services:
            ctx.renderer.print_warn("No services found in config")
            return EXIT_SUCCESS

        backup_env = args.backup_env
        global_backup_unit = (
            "backup.service" if backup_env == "local" else "backup-remote.service"
        )

        global_last_ok = await unit_last_success(ctx.systemctl, global_backup_unit)

        columns = [
            TableColumn("Service", style="bold"),
            TableColumn("Backup", justify="center"),
            TableColumn("Targets"),
            TableColumn("Tags"),
            TableColumn(f"Last ({backup_env})", justify="center"),
        ]

        rows: list[TableRow] = []
        for name in services:
            svc = ctx.config.services[name]
            backup_ok = bool(svc.backup.enable)
            last_ok = _last_backup_ok(backup_enabled=backup_ok, global_last_ok=global_last_ok)

            rows.append(
                TableRow(
                    cells=[
                        name,
                        ctx.renderer.format_check(backup_ok),
                        _target_summary(svc),
                        _tag_summary(svc),
                        ctx.renderer.format_check(last_ok),
                    ]
                )
            )

        ctx.renderer.render_table("Services", columns, rows)

        if global_last_ok is None:
            ctx.renderer.print_warn(f"Could not determine last result for {global_backup_unit}")

        return EXIT_SUCCESS


class ListBackupsCommand(Command[ListBackupsArgs]):
    """List snapshots for a service."""

    async def execute(self, args: ListBackupsArgs, ctx: AppContext) -> int:
        """List snapshots for a service and show configured backup targets."""
        env = args.env
        service_name = args.service

        svc = validate_service(ctx.config, service_name)
        if svc.backup.kubernetes is not None:
            require_root(f"list backups for {service_name}")
        path_resolver = ctx.path_resolver

        resolved, missing = await path_resolver.resolve_all(
            svc.backup.paths, svc.backup.kubernetes
        )

        # Show backup contents table
        columns = [
            TableColumn("Type", style="bold"),
            TableColumn("Name/path"),
            TableColumn("Filesystem path"),
            TableColumn("Exists", justify="center"),
        ]

        rows: list[TableRow] = []
        rows = [
            TableRow(
                cells=[
                    rp.source_type,
                    rp.source_name,
                    rp.filesystem_path,
                    ctx.renderer.format_check(rp.exists),
                ]
            )
            for rp in resolved
        ]

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
