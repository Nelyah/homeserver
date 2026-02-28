"""List services command."""

from collections.abc import Mapping
from pathlib import Path
from typing import TYPE_CHECKING

from rich.text import Text

from ...config import load_restic_env
from ...controllers import unit_last_success
from ...controllers.docker import ContainerInfo
from ...core import validate_service
from ...exceptions import EXIT_SUCCESS
from ..args import ListArgs, ListBackupsArgs
from ..renderer import TableColumn, TableRow
from .base import AppContext, Command

if TYPE_CHECKING:
    from ...controllers.restic import ResticSnapshot


_MIN_TRUNCATE_AVAILABLE = 3


def _truncate_image(image: str, max_len: int = 25) -> str:
    """Truncate image name to max length, keeping tag visible."""
    if len(image) <= max_len:
        return image
    # Try to keep the tag (after last :)
    if ":" in image:
        name, tag = image.rsplit(":", 1)
        available = max_len - len(tag) - 4  # account for ".." and ":"
        if available > _MIN_TRUNCATE_AVAILABLE:
            return f"{name[:available]}..:{tag}"
    return image[: max_len - 2] + ".."


def _format_container_line(container: ContainerInfo, detailed: bool = False) -> str:
    """Format a single container as a line: name  image  uptime."""
    image = _truncate_image(container.image)
    uptime = container.running_for

    if detailed and container.ports:
        return f"{container.name:<20} {image:<25} {uptime:<12} {container.ports}"
    return f"{container.name:<20} {image:<25} {uptime}"


def _group_containers_by_project(
    all_containers: list[ContainerInfo],
) -> dict[str, list[ContainerInfo]]:
    """Group containers by docker-compose project name."""
    containers_by_project: dict[str, list[ContainerInfo]] = {}
    for container in all_containers:
        if container.project:
            containers_by_project.setdefault(container.project, []).append(container)
    return containers_by_project


def _is_deployed(deploy_root: str, service_name: str) -> bool:
    """Check whether service has a deploy directory."""
    deploy_dir = Path(deploy_root) / service_name
    try:
        return deploy_dir.is_dir()
    except OSError:
        return False


def _last_backup_ok(*, backup_enabled: bool, global_last_ok: bool | None) -> bool:
    """Return the last backup result for this service based on global unit state."""
    if not backup_enabled:
        return False
    return bool(global_last_ok is True)


def _format_containers_cell(
    service_name: str,
    deployed: bool,
    *,
    containers_by_project: Mapping[str, list[ContainerInfo]],
    detailed: bool = False,
) -> Text:
    """Build a multi-line Text with one line per container."""
    if not deployed:
        return Text("-", style="dim")

    containers = containers_by_project.get(service_name, [])
    if not containers:
        return Text("(no containers)", style="dim")

    lines = [
        _format_container_line(container, detailed)
        for container in sorted(containers, key=lambda c: c.name)
    ]

    return Text("\n".join(lines))


def _format_status_cell(
    service_name: str,
    deployed: bool,
    *,
    containers_by_project: Mapping[str, list[ContainerInfo]],
) -> Text:
    """Format container health status."""
    if not deployed:
        return Text("-", style="dim")

    containers = containers_by_project.get(service_name, [])
    if not containers:
        return Text("-", style="dim")

    running = sum(1 for c in containers if c.is_up)
    total = len(containers)
    all_healthy = all(c.is_healthy for c in containers if c.is_up)

    if running == total and all_healthy:
        return Text(f"{running}/{total}", style="green")
    if running == total:
        return Text(f"{running}/{total} !", style="yellow")
    if running > 0:
        return Text(f"{running}/{total}", style="yellow")
    return Text(f"{running}/{total}", style="red")


class ListCommand(Command[ListArgs]):
    """List all services and their status."""

    async def execute(self, args: ListArgs, ctx: AppContext) -> int:
        """Render a table of services with deploy/backup/container status."""
        services = sorted(ctx.config.services.keys())
        if not services:
            ctx.renderer.print_warn("No services found in config")
            return EXIT_SUCCESS

        backup_env = args.backup_env
        global_backup_unit = (
            "backup.service" if backup_env == "local" else "backup-remote.service"
        )

        global_last_ok = await unit_last_success(ctx.systemctl, global_backup_unit)

        containers_by_project = _group_containers_by_project(
            await ctx.docker.list_containers()
        )

        # Build columns - adjust based on --detailed flag
        columns = [
            TableColumn("Service", style="bold"),
            TableColumn("Containers"),
            TableColumn("Status", justify="center"),
            TableColumn("Backup", justify="center"),
            TableColumn(f"Last ({backup_env})", justify="center"),
        ]

        rows: list[TableRow] = []
        for name in services:
            svc = ctx.config.services[name]
            deployed_ok = _is_deployed(ctx.config.paths.deploy_root, name)
            backup_ok = bool(svc.backup.enable)
            last_ok = _last_backup_ok(backup_enabled=backup_ok, global_last_ok=global_last_ok)

            rows.append(
                TableRow(
                    cells=[
                        name,
                        _format_containers_cell(
                            name,
                            deployed_ok,
                            containers_by_project=containers_by_project,
                            detailed=args.detailed,
                        ),
                        _format_status_cell(
                            name,
                            deployed_ok,
                            containers_by_project=containers_by_project,
                        ),
                        ctx.renderer.format_check(backup_ok),
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
