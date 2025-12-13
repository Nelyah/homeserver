"""Service management commands (start/stop/restart/logs)."""

import argparse
from pathlib import Path

from ...core import ServiceManager, require_root
from ...core.service_manager import ActionType
from ...controllers.docker import ContainerInfo
from ...exceptions import EXIT_SUCCESS, EXIT_SYSTEMCTL_ERROR
from ..renderer import TableColumn, TableRow
from .base import AppContext, Command


class ServiceActionCommand(Command):
    """Base class for service action commands (start/stop/restart)."""

    def __init__(self, action: ActionType):
        self._action: ActionType = action

    async def execute(self, args: argparse.Namespace, ctx: AppContext) -> int:
        require_root(f"{self._action} services")
        service_arg = args.service

        manager = ServiceManager(ctx.config, ctx.systemctl)
        results = await manager.perform_action(self._action, service_arg)

        # Render results table
        columns = [
            TableColumn("Service", style="bold"),
            TableColumn("Result"),
        ]

        rows: list[TableRow] = []
        for result in results:
            rows.append(
                TableRow(
                    cells=[
                        result.service_name,
                        ctx.renderer.format_status(result.success, result.detail),
                    ]
                )
            )

        title = f"{self._action.capitalize()} services"
        ctx.renderer.render_table(title, columns, rows)

        all_success = all(r.success for r in results)
        return EXIT_SUCCESS if all_success else EXIT_SYSTEMCTL_ERROR


class StartCommand(ServiceActionCommand):
    """Start docker-compose service(s)."""

    def __init__(self):
        super().__init__("start")


class StopCommand(ServiceActionCommand):
    """Stop docker-compose service(s)."""

    def __init__(self):
        super().__init__("stop")


class RestartCommand(ServiceActionCommand):
    """Restart docker-compose service(s)."""

    def __init__(self):
        super().__init__("restart")


class LogsCommand(Command):
    """Stream docker-compose logs for a service."""

    async def execute(self, args: argparse.Namespace, ctx: AppContext) -> int:
        service_name = args.service
        follow = args.follow
        tail = args.tail
        timestamps = args.timestamps

        manager = ServiceManager(ctx.config, ctx.systemctl)

        return await manager.stream_logs(
            service_name=service_name,
            follow=follow,
            tail=tail,
            timestamps=timestamps,
        )


# ---------------------------------------------------------------------------
# Docker maintenance commands
# ---------------------------------------------------------------------------


# Exit code for docker-related issues found
EXIT_DOCKER_ISSUES = 1


class DockerHealthCommand(Command):
    """Check health of deployed docker services and containers.

    Reports:
    - Deployed services with no running container
    - Containers not in Up/healthy state
    - Orphan containers (stopped, no compose project label)
    """

    async def execute(self, args: argparse.Namespace, ctx: AppContext) -> int:
        deploy_root = Path(ctx.config.paths.deploy_root)
        expected_services: set[str] = set()
        if deploy_root.exists():
            for item in deploy_root.iterdir():
                if item.is_dir():
                    expected_services.add(item.name)

        containers = await ctx.docker.list_containers()

        seen_projects: set[str] = set()
        for container in containers:
            if container.project:
                seen_projects.add(container.project)

        missing_services: list[str] = []
        bad_deployed: list[ContainerInfo] = []
        bad_other: list[ContainerInfo] = []
        orphans: list[ContainerInfo] = []

        for svc in sorted(expected_services):
            if svc not in seen_projects:
                missing_services.append(svc)

        for container in containers:
            is_bad = not container.is_up or not container.is_healthy

            if is_bad:
                if container.project and container.project in expected_services:
                    bad_deployed.append(container)
                else:
                    bad_other.append(container)

            if container.is_orphan:
                orphans.append(container)

        has_issues = bool(missing_services or bad_deployed or bad_other or orphans)

        if missing_services:
            ctx.renderer.print_heading("Deployed services with no running container")
            columns = [TableColumn("Service", style="bold")]
            rows = [TableRow(cells=[svc]) for svc in missing_services]
            ctx.renderer.render_table("Missing", columns, rows)

        if bad_deployed:
            ctx.renderer.print_heading("Deployed containers not Up/healthy")
            self._render_container_table(ctx, "Unhealthy Deployed", bad_deployed)

        if bad_other:
            ctx.renderer.print_heading("Other containers not Up/healthy")
            self._render_container_table(ctx, "Unhealthy Other", bad_other)

        if orphans:
            ctx.renderer.print_heading(
                "Orphan containers (no compose project label, not Up)"
            )
            columns = [TableColumn("Name", style="bold")]
            rows = [TableRow(cells=[c.name]) for c in orphans]
            ctx.renderer.render_table("Orphans", columns, rows)
            ctx.renderer.print_warn(
                "Run `svc docker prune-orphans` to remove these containers."
            )

        if not has_issues:
            ctx.renderer.print_ok(
                "All good: deployed services are running, "
                "containers are healthy, and no orphans found."
            )
            return EXIT_SUCCESS

        return EXIT_DOCKER_ISSUES

    def _render_container_table(
        self, ctx: AppContext, title: str, containers: list[ContainerInfo]
    ) -> None:
        columns = [
            TableColumn("Name", style="bold"),
            TableColumn("Status"),
            TableColumn("Project"),
            TableColumn("Service"),
        ]
        rows = [
            TableRow(
                cells=[
                    c.name,
                    c.status,
                    c.project or "unknown",
                    c.service or "-",
                ]
            )
            for c in containers
        ]
        ctx.renderer.render_table(title, columns, rows)


class PruneImagesCommand(Command):
    """Remove dangling Docker images (<none>:<none>), never affecting containers."""

    async def execute(self, args: argparse.Namespace, ctx: AppContext) -> int:
        images = await ctx.docker.get_dangling_images()

        if not images:
            ctx.renderer.print_ok("No dangling images found.")
            return EXIT_SUCCESS

        columns = [
            TableColumn("Image ID", style="bold"),
            TableColumn("Size"),
        ]
        rows = [TableRow(cells=[img.id, img.size]) for img in images]
        ctx.renderer.render_table("Dangling Images", columns, rows)

        if ctx.dry_run:
            ctx.renderer.print_info(
                f"[dry-run] Would remove {len(images)} dangling image(s)."
            )
            return EXIT_SUCCESS

        image_ids = [img.id for img in images]
        removed, failed = await ctx.docker.remove_images(image_ids)

        if removed:
            ctx.renderer.print_ok(f"Removed {len(removed)} dangling image(s).")

        if failed:
            ctx.renderer.print_error(f"Failed to remove {len(failed)} image(s).")
            return EXIT_DOCKER_ISSUES

        return EXIT_SUCCESS


class PruneOrphansCommand(Command):
    """Remove stopped containers with no compose project label."""

    async def execute(self, args: argparse.Namespace, ctx: AppContext) -> int:
        containers = await ctx.docker.list_containers()
        orphans = [c for c in containers if c.is_orphan]

        if not orphans:
            ctx.renderer.print_ok("No orphan containers found.")
            return EXIT_SUCCESS

        columns = [
            TableColumn("Name", style="bold"),
            TableColumn("Status"),
        ]
        rows = [TableRow(cells=[c.name, c.status]) for c in orphans]
        ctx.renderer.render_table("Orphan Containers", columns, rows)

        if ctx.dry_run:
            ctx.renderer.print_info(
                f"[dry-run] Would remove {len(orphans)} orphan container(s)."
            )
            return EXIT_SUCCESS

        container_names = [c.name for c in orphans]
        removed, failed = await ctx.docker.remove_containers(container_names)

        if removed:
            ctx.renderer.print_ok(f"Removed {len(removed)} orphan container(s).")

        if failed:
            ctx.renderer.print_error(f"Failed to remove {len(failed)} container(s).")
            return EXIT_DOCKER_ISSUES

        return EXIT_SUCCESS
