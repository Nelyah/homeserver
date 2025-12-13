"""Service management commands (start/stop/restart/logs)."""

from ...core import ServiceManager, require_root
from ...core.service_manager import ActionType, ServiceActionResult
from ...exceptions import EXIT_SERVICE_ACTION_ERROR, EXIT_SUCCESS
from ..args import LogsArgs, RestartArgs, ServiceActionArgs
from ..renderer import TableColumn, TableRow
from .base import AppContext, Command


class ServiceActionCommand(Command[ServiceActionArgs]):
    """Base class for service action commands (start/stop/restart)."""

    def __init__(self, action: ActionType):
        self._action: ActionType = action

    async def execute(self, args: ServiceActionArgs, ctx: AppContext) -> int:
        require_root(f"{self._action} services")
        service_arg = args.service

        manager = ServiceManager(ctx.config, dry_run=ctx.dry_run)
        results = await manager.perform_action(
            self._action,
            service_arg,
            build=args.build,
            output=ctx.renderer.print_info,
        )

        title = f"{self._action.capitalize()} services"
        self.render_results(ctx, title, results)

        all_success = all(r.success for r in results)
        return EXIT_SUCCESS if all_success else EXIT_SERVICE_ACTION_ERROR

    @staticmethod
    def render_results(
        ctx: AppContext, title: str, results: list[ServiceActionResult]
    ) -> None:
        columns = [
            TableColumn("Service", style="bold"),
            TableColumn("Result"),
        ]
        rows = [
            TableRow(
                cells=[
                    result.service_name,
                    ctx.renderer.format_status(result.success, result.detail),
                ]
            )
            for result in results
        ]
        ctx.renderer.render_table(title, columns, rows)


class StartCommand(ServiceActionCommand):
    """Start docker-compose service(s)."""

    def __init__(self):
        super().__init__("start")


class StopCommand(ServiceActionCommand):
    """Stop docker-compose service(s)."""

    def __init__(self):
        super().__init__("stop")


class RestartCommand(Command[RestartArgs]):
    """Restart docker-compose service(s)."""

    async def execute(self, args: RestartArgs, ctx: AppContext) -> int:
        if not args.recreate:
            require_root("restart services")
            manager = ServiceManager(ctx.config, dry_run=ctx.dry_run)
            results = await manager.perform_action(
                "restart",
                args.service,
                build=args.build,
                output=ctx.renderer.print_info,
            )
            ServiceActionCommand.render_results(ctx, "Restart services", results)
            all_success = all(r.success for r in results)
            return EXIT_SUCCESS if all_success else EXIT_SERVICE_ACTION_ERROR

        # Otherwise, do docker compose down/up
        require_root("recreate services")
        service_arg = args.service

        manager = ServiceManager(ctx.config, dry_run=ctx.dry_run)
        results = await manager.perform_recreate(
            service_arg,
            build=args.build,
            output=ctx.renderer.print_info,
        )

        ServiceActionCommand.render_results(ctx, "Recreate services", results)

        all_success = all(r.success for r in results)
        return EXIT_SUCCESS if all_success else EXIT_SERVICE_ACTION_ERROR


class LogsCommand(Command[LogsArgs]):
    """Stream docker-compose logs for a service."""

    async def execute(self, args: LogsArgs, ctx: AppContext) -> int:
        service_name = args.service
        follow = args.follow
        tail = args.tail
        timestamps = args.timestamps

        manager = ServiceManager(ctx.config, dry_run=ctx.dry_run)

        return await manager.stream_logs(
            service_name=service_name,
            follow=follow,
            tail=tail,
            timestamps=timestamps,
        )
