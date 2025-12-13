"""Service management commands (start/stop/restart/logs)."""

import argparse

from ...core import ServiceManager, require_root
from ...core.service_manager import ActionType
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
        results = await manager.perform_action(
            self._action,
            service_arg,
            output=ctx.renderer.print_info,
        )

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

    async def execute(self, args: argparse.Namespace, ctx: AppContext) -> int:
        recreate = getattr(args, "recreate", False)

        # If not recreating, use the normal systemctl-based restart
        if not recreate:
            return await super().execute(args, ctx)

        # Otherwise, do docker compose down/up
        require_root("recreate services")
        service_arg = args.service

        manager = ServiceManager(ctx.config, ctx.systemctl)
        results = await manager.perform_recreate(
            service_arg,
            output=ctx.renderer.print_info,
        )

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

        ctx.renderer.render_table("Recreate services", columns, rows)

        all_success = all(r.success for r in results)
        return EXIT_SUCCESS if all_success else EXIT_SYSTEMCTL_ERROR


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
