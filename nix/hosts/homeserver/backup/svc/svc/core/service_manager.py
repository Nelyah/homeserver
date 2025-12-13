"""Service management operations (start/stop/restart/logs)."""

import asyncio
import logging
import re
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from ..config import Config
from ..controllers import SystemctlController
from ..exceptions import DependencyError, SystemctlError

logger = logging.getLogger("svc.core.service_manager")


@dataclass
class ServiceActionResult:
    """Result of a service action (start/stop/restart)."""

    service_name: str
    success: bool
    detail: str


ActionType = Literal["start", "stop", "restart"]


class ServiceManager:
    """Manages docker-compose service lifecycle operations."""

    def __init__(self, config: Config, systemctl: SystemctlController):
        self.config = config
        self.systemctl = systemctl

    @staticmethod
    def compose_unit_for(service_name: str) -> str:
        """Get the systemd unit name for a service's docker-compose."""
        return f"docker-compose-{service_name}.service"

    def get_service_names(self, service_arg: str) -> list[str]:
        """
        Get list of service names based on argument.

        Args:
            service_arg: Service name or 'all'

        Returns:
            List of service names to operate on
        """
        if service_arg == "all":
            return sorted(self.config.services.keys())
        else:
            from .service_helpers import get_service

            return [get_service(self.config, service_arg).name]

    async def _perform_action(
        self, action: ActionType, service_name: str
    ) -> ServiceActionResult:
        """Perform a single action on a service."""
        unit = self.compose_unit_for(service_name)

        if not await self.systemctl.is_loaded(unit):
            return ServiceActionResult(
                service_name=service_name,
                success=False,
                detail="not loaded",
            )

        try:
            if action == "stop":
                await self.systemctl.stop(unit)
                return ServiceActionResult(
                    service_name=service_name,
                    success=True,
                    detail="stopped",
                )
            elif action == "start":
                await self.systemctl.start(unit)
                return ServiceActionResult(
                    service_name=service_name,
                    success=True,
                    detail="started",
                )
            elif action == "restart":
                await self.systemctl.stop(unit)
                await self.systemctl.start(unit)
                return ServiceActionResult(
                    service_name=service_name,
                    success=True,
                    detail="restarted",
                )
        except SystemctlError as e:
            return ServiceActionResult(
                service_name=service_name,
                success=False,
                detail=str(e),
            )

        # Unreachable, but satisfy type checker
        return ServiceActionResult(
            service_name=service_name,
            success=False,
            detail="unknown action",
        )

    async def perform_action(
        self, action: ActionType, service_arg: str
    ) -> list[ServiceActionResult]:
        """
        Perform an action on one or all services.

        Args:
            action: The action to perform
            service_arg: Service name or 'all'

        Returns:
            List of results for each service
        """
        service_names = self.get_service_names(service_arg)
        results: list[ServiceActionResult] = []

        for name in service_names:
            result = await self._perform_action(action, name)
            results.append(result)

        return results

    async def resolve_compose_file(self, service_name: str) -> Path:
        """Resolve the compose file path for a service."""
        unit = self.compose_unit_for(service_name)

        props = await self.systemctl.show(
            unit, ["LoadState", "ExecStart", "WorkingDirectory"]
        )
        exec_start = props.get("ExecStart", "")

        match = re.search(r"(?:^|\s)-f\s+([^\s;]+)", exec_start)
        if match:
            return Path(match.group(1))

        working_dir = props.get("WorkingDirectory")
        if working_dir:
            return Path(working_dir) / "docker-compose.yml"

        return Path(self.config.paths.deploy_root) / service_name / "docker-compose.yml"

    async def stream_logs(
        self,
        service_name: str,
        follow: bool = True,
        tail: int | None = 200,
        timestamps: bool = False,
    ) -> int:
        """
        Stream docker-compose logs for a service.

        Returns:
            Exit code from docker-compose logs
        """
        from .service_helpers import get_service

        svc = get_service(self.config, service_name)

        docker_compose = shutil.which("docker-compose") or "/run/current-system/sw/bin/docker-compose"
        if not Path(docker_compose).exists():
            raise DependencyError(
                "docker-compose not found in PATH or at /run/current-system/sw/bin/docker-compose"
            )

        compose_file = await self.resolve_compose_file(svc.name)
        if not compose_file.exists():
            from ..exceptions import ConfigError

            raise ConfigError(f"Compose file not found: {compose_file}")

        args = [docker_compose, "-f", str(compose_file), "logs"]
        if follow:
            args.append("-f")
        if timestamps:
            args.append("-t")
        if tail is not None:
            args.extend(["--tail", str(tail)])

        logger.info(f"Streaming logs for {svc.name}...")

        proc = await asyncio.create_subprocess_exec(
            *args, cwd=str(compose_file.parent)
        )
        await proc.wait()
        return proc.returncode or 0
