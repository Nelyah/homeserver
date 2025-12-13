"""Docker maintenance commands (health, prune-images, prune-orphans)."""

import argparse
from pathlib import Path

from ...controllers.docker import ContainerInfo
from ...exceptions import EXIT_SUCCESS
from ..renderer import TableColumn, TableRow
from .base import AppContext, Command

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
        # Get list of expected services from deploy_root
        deploy_root = Path(ctx.config.paths.deploy_root)
        expected_services: set[str] = set()
        if deploy_root.exists():
            for item in deploy_root.iterdir():
                if item.is_dir():
                    expected_services.add(item.name)

        # Get all containers
        containers = await ctx.docker.list_containers()

        # Build sets for analysis
        seen_projects: set[str] = set()
        for c in containers:
            if c.project:
                seen_projects.add(c.project)

        # Categorize containers
        missing_services: list[str] = []
        bad_deployed: list[ContainerInfo] = []
        bad_other: list[ContainerInfo] = []
        orphans: list[ContainerInfo] = []

        # Find missing services (deployed but no container)
        for svc in sorted(expected_services):
            if svc not in seen_projects:
                missing_services.append(svc)

        # Categorize unhealthy containers
        for c in containers:
            is_bad = not c.is_up or not c.is_healthy

            if is_bad:
                if c.project and c.project in expected_services:
                    bad_deployed.append(c)
                else:
                    bad_other.append(c)

            if c.is_orphan:
                orphans.append(c)

        # Track if we found any issues
        has_issues = bool(missing_services or bad_deployed or bad_other or orphans)

        # Report missing services
        if missing_services:
            ctx.renderer.print_heading("Deployed services with no running container")
            columns = [TableColumn("Service", style="bold")]
            rows = [TableRow(cells=[svc]) for svc in missing_services]
            ctx.renderer.render_table("Missing", columns, rows)

        # Report unhealthy deployed containers
        if bad_deployed:
            ctx.renderer.print_heading("Deployed containers not Up/healthy")
            self._render_container_table(ctx, "Unhealthy Deployed", bad_deployed)

        # Report unhealthy non-deployed containers
        if bad_other:
            ctx.renderer.print_heading("Other containers not Up/healthy")
            self._render_container_table(ctx, "Unhealthy Other", bad_other)

        # Report orphans
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


class PruneImagesCommand(Command):
    """Remove dangling Docker images.

    Dangling images are images tagged <none>:<none>. They are created when you
    rebuild an image with the same tag - the old image loses its tag but remains
    on disk. These are safe to remove as they are not used by any container.

    This command only removes images that have no tag. Running containers are
    never affected.
    """

    async def execute(self, args: argparse.Namespace, ctx: AppContext) -> int:
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
            ctx.renderer.print_info(
                f"[dry-run] Would remove {len(images)} dangling image(s)."
            )
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


class PruneOrphansCommand(Command):
    """Remove orphan containers.

    Orphan containers are stopped containers that have no docker-compose project
    label (com.docker.compose.project). They may be leftover from removed compose
    stacks or one-off test runs.

    This command only removes containers that are:
    - Not running (not in "Up" state)
    - Have no compose project label

    Running containers and labeled containers are never affected.
    """

    async def execute(self, args: argparse.Namespace, ctx: AppContext) -> int:
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
            ctx.renderer.print_info(
                f"[dry-run] Would remove {len(orphans)} orphan container(s)."
            )
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
