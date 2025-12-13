"""Docker maintenance commands (health, prune-images, prune-orphans)."""

from pathlib import Path

from ...controllers.docker import ContainerInfo
from ...exceptions import EXIT_SUCCESS
from ..args import EmptyArgs
from ..renderer import TableColumn, TableRow
from .base import AppContext, Command

# Exit code for docker-related issues found
EXIT_DOCKER_ISSUES = 1


class DockerHealthCommand(Command[EmptyArgs]):
    """
    Check health of deployed docker services and containers.

    Reports:
    - Deployed services with no running container
    - Containers not in Up/healthy state
    - Orphan containers (stopped, no compose project label)
    """

    async def execute(self, args: EmptyArgs, ctx: AppContext) -> int:
        _ = args
        expected_services = self._expected_services(ctx)
        containers = await ctx.docker.list_containers()
        report = self._analyze_containers(expected_services, containers)
        self._render_report(ctx, report)
        return EXIT_DOCKER_ISSUES if report.has_issues else EXIT_SUCCESS

    def _expected_services(self, ctx: AppContext) -> set[str]:
        deploy_root = Path(ctx.config.paths.deploy_root)
        if not deploy_root.exists():
            return set()
        return {item.name for item in deploy_root.iterdir() if item.is_dir()}

    def _analyze_containers(
        self, expected_services: set[str], containers: list[ContainerInfo]
    ) -> "_DockerHealthReport":
        seen_projects = {c.project for c in containers if c.project}
        missing_services = sorted(expected_services - seen_projects)

        bad_deployed: list[ContainerInfo] = []
        bad_other: list[ContainerInfo] = []
        orphans: list[ContainerInfo] = []

        for container in containers:
            is_bad = (not container.is_up) or (not container.is_healthy)
            if is_bad:
                if container.project and container.project in expected_services:
                    bad_deployed.append(container)
                else:
                    bad_other.append(container)
            if container.is_orphan:
                orphans.append(container)

        return _DockerHealthReport(
            missing_services=missing_services,
            bad_deployed=bad_deployed,
            bad_other=bad_other,
            orphans=orphans,
        )

    def _render_report(self, ctx: AppContext, report: "_DockerHealthReport") -> None:
        if report.missing_services:
            ctx.renderer.print_heading("Deployed services with no running container")
            columns = [TableColumn("Service", style="bold")]
            rows = [TableRow(cells=[svc]) for svc in report.missing_services]
            ctx.renderer.render_table("Missing", columns, rows)

        if report.bad_deployed:
            ctx.renderer.print_heading("Deployed containers not Up/healthy")
            self._render_container_table(ctx, "Unhealthy Deployed", report.bad_deployed)

        if report.bad_other:
            ctx.renderer.print_heading("Other containers not Up/healthy")
            self._render_container_table(ctx, "Unhealthy Other", report.bad_other)

        if report.orphans:
            ctx.renderer.print_heading("Orphan containers (no compose project label, not Up)")
            columns = [TableColumn("Name", style="bold")]
            rows = [TableRow(cells=[c.name]) for c in report.orphans]
            ctx.renderer.render_table("Orphans", columns, rows)
            ctx.renderer.print_warn("Run `svc docker prune-orphans` to remove these containers.")

        if not report.has_issues:
            ctx.renderer.print_ok(
                "All good: deployed services are running, "
                "containers are healthy, and no orphans found."
            )

    def _render_container_table(
        self, ctx: AppContext, title: str, containers: list[ContainerInfo]
    ) -> None:
        """Render a table of containers."""
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


class PruneImagesCommand(Command[EmptyArgs]):
    """
    Remove dangling Docker images.

    Dangling images are images tagged <none>:<none>. They are created when you
    rebuild an image with the same tag - the old image loses its tag but remains
    on disk. These are safe to remove as they are not used by any container.

    This command only removes images that have no tag. Running containers are
    never affected.
    """

    async def execute(self, args: EmptyArgs, ctx: AppContext) -> int:
        _ = args
        images = await ctx.docker.get_dangling_images()

        if not images:
            ctx.renderer.print_ok("No dangling images found.")
            return EXIT_SUCCESS

        # Show what we're going to remove
        columns = [
            TableColumn("Image ID", style="bold"),
            TableColumn("Size"),
        ]
        rows = [TableRow(cells=[img.id, img.size]) for img in images]
        ctx.renderer.render_table("Dangling Images", columns, rows)

        if ctx.dry_run:
            ctx.renderer.print_info(f"[dry-run] Would remove {len(images)} dangling image(s).")
            return EXIT_SUCCESS

        # Remove images
        image_ids = [img.id for img in images]
        removed, failed = await ctx.docker.remove_images(image_ids)

        if removed:
            ctx.renderer.print_ok(f"Removed {len(removed)} dangling image(s).")

        if failed:
            ctx.renderer.print_error(f"Failed to remove {len(failed)} image(s).")
            return EXIT_DOCKER_ISSUES

        return EXIT_SUCCESS


class PruneOrphansCommand(Command[EmptyArgs]):
    """
    Remove orphan containers.

    Orphan containers are stopped containers that have no docker-compose project
    label (com.docker.compose.project). They may be leftover from removed compose
    stacks or one-off test runs.

    This command only removes containers that are:
    - Not running (not in "Up" state)
    - Have no compose project label

    Running containers and labeled containers are never affected.
    """

    async def execute(self, args: EmptyArgs, ctx: AppContext) -> int:
        _ = args
        containers = await ctx.docker.list_containers()

        # Find orphans (stopped, no compose project label)
        orphans = [c for c in containers if c.is_orphan]

        if not orphans:
            ctx.renderer.print_ok("No orphan containers found.")
            return EXIT_SUCCESS

        # Show what we're going to remove
        columns = [
            TableColumn("Name", style="bold"),
            TableColumn("Status"),
        ]
        rows = [TableRow(cells=[c.name, c.status]) for c in orphans]
        ctx.renderer.render_table("Orphan Containers", columns, rows)

        if ctx.dry_run:
            ctx.renderer.print_info(f"[dry-run] Would remove {len(orphans)} orphan container(s).")
            return EXIT_SUCCESS

        # Remove containers
        container_names = [c.name for c in orphans]
        removed, failed = await ctx.docker.remove_containers(container_names)

        if removed:
            ctx.renderer.print_ok(f"Removed {len(removed)} orphan container(s).")

        if failed:
            ctx.renderer.print_error(f"Failed to remove {len(failed)} container(s).")
            return EXIT_DOCKER_ISSUES

        return EXIT_SUCCESS


class _DockerHealthReport:
    def __init__(
        self,
        *,
        missing_services: list[str],
        bad_deployed: list[ContainerInfo],
        bad_other: list[ContainerInfo],
        orphans: list[ContainerInfo],
    ) -> None:
        self.missing_services = missing_services
        self.bad_deployed = bad_deployed
        self.bad_other = bad_other
        self.orphans = orphans

    @property
    def has_issues(self) -> bool:
        return bool(self.missing_services or self.bad_deployed or self.bad_other or self.orphans)
