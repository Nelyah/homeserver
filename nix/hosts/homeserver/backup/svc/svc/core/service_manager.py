"""Service management operations (start/stop/restart/logs)."""

import asyncio
import logging
import re
import shutil
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from ..config import Config
from ..controllers import SystemctlController
from ..exceptions import DependencyError

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
        from .service_helpers import get_service

        return [get_service(self.config, service_arg).name]

    async def _perform_action(
        self,
        action: ActionType,
        service_name: str,
        *,
        output: Callable[[str], None] | None = None,
    ) -> ServiceActionResult:
        """Perform a single action on a service via docker-compose directly."""
        compose_file = await self.resolve_compose_file(service_name)
        docker_compose = self._docker_compose_bin()
        if docker_compose is None:
            return ServiceActionResult(
                service_name=service_name,
                success=False,
                detail="docker-compose not found",
            )

        if not compose_file.exists():
            return ServiceActionResult(
                service_name=service_name,
                success=False,
                detail=f"compose file not found: {compose_file}",
            )

        build = await self._compose_build_enabled(service_name)
        interactive = output is not None and sys.stdout.isatty() and sys.stderr.isatty()

        def maybe_print(cmd: str) -> None:
            if output is not None and not interactive:
                output(cmd)

        try:
            if action == "stop":
                down_args = [
                    docker_compose,
                    "-f",
                    str(compose_file),
                    "down",
                    "--remove-orphans",
                ]
                maybe_print(f"$ {' '.join(down_args)}")
                rc = await self._run_streamed(
                    down_args,
                    cwd=str(compose_file.parent),
                    output=output,
                )
                if rc != 0:
                    return ServiceActionResult(
                        service_name=service_name,
                        success=False,
                        detail="down failed",
                    )
                return ServiceActionResult(
                    service_name=service_name,
                    success=True,
                    detail="stopped",
                )

            if action == "start":
                up_args = self._compose_up_args(
                    docker_compose,
                    compose_file,
                    build=build,
                    force_recreate=True,
                    remove_orphans=True,
                )
                maybe_print(f"$ {' '.join(up_args)}")
                rc = await self._run_streamed(up_args, cwd=str(compose_file.parent), output=output)
                if rc != 0:
                    return ServiceActionResult(
                        service_name=service_name,
                        success=False,
                        detail="up failed",
                    )
                return ServiceActionResult(
                    service_name=service_name,
                    success=True,
                    detail="started",
                )

            if action == "restart":
                # Mirror the systemd unit semantics (down, then up -d ...).
                down_args = [
                    docker_compose,
                    "-f",
                    str(compose_file),
                    "down",
                    "--remove-orphans",
                ]
                maybe_print(f"$ {' '.join(down_args)}")
                down_rc = await self._run_streamed(
                    down_args,
                    cwd=str(compose_file.parent),
                    output=output,
                )
                if down_rc != 0:
                    return ServiceActionResult(
                        service_name=service_name,
                        success=False,
                        detail="down failed",
                    )

                up_args = self._compose_up_args(
                    docker_compose,
                    compose_file,
                    build=build,
                    force_recreate=True,
                    remove_orphans=True,
                )
                maybe_print(f"$ {' '.join(up_args)}")
                up_rc = await self._run_streamed(
                    up_args,
                    cwd=str(compose_file.parent),
                    output=output,
                )
                if up_rc != 0:
                    return ServiceActionResult(
                        service_name=service_name,
                        success=False,
                        detail="up failed",
                    )
                return ServiceActionResult(
                    service_name=service_name,
                    success=True,
                    detail="restarted",
                )
        except Exception as e:
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
        self,
        action: ActionType,
        service_arg: str,
        *,
        output: Callable[[str], None] | None = None,
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
        interactive = output is not None and sys.stdout.isatty() and sys.stderr.isatty()

        for name in service_names:
            if output is not None and not interactive and len(service_names) > 1:
                output(f"== {action} {name} ==")
            result = await self._perform_action(action, name, output=output)
            results.append(result)

        return results

    async def _run_streamed(
        self,
        args: list[str],
        *,
        cwd: str,
        output: Callable[[str], None] | None,
    ) -> int:
        # If we're connected to a real terminal, inheriting the parent's fds
        # preserves docker-compose's interactive/inline progress rendering.
        if output is not None and sys.stdout.isatty() and sys.stderr.isatty():
            proc = await asyncio.create_subprocess_exec(*args, cwd=cwd)
            await proc.wait()
            return proc.returncode or 0

        if output is None:
            proc = await asyncio.create_subprocess_exec(*args, cwd=cwd)
            await proc.wait()
            return proc.returncode or 0

        proc = await asyncio.create_subprocess_exec(
            *args,
            cwd=cwd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        async def pump(reader: asyncio.StreamReader | None) -> None:
            if reader is None:
                return
            while True:
                chunk = await reader.readline()
                if not chunk:
                    break
                output(chunk.decode(errors="replace").rstrip("\n"))

        await asyncio.gather(pump(proc.stdout), pump(proc.stderr))
        rc = await proc.wait()
        return rc or 0

    async def recreate_service(
        self,
        service_name: str,
        *,
        output: Callable[[str], None] | None = None,
    ) -> ServiceActionResult:
        """Recreate a service by running docker compose down/up."""
        from .service_helpers import get_service

        svc = get_service(self.config, service_name)
        compose_file = await self.resolve_compose_file(svc.name)

        docker_compose = self._docker_compose_bin()
        if docker_compose is None:
            return ServiceActionResult(
                service_name=service_name,
                success=False,
                detail="docker-compose not found",
            )

        if not compose_file.exists():
            return ServiceActionResult(
                service_name=service_name,
                success=False,
                detail=f"compose file not found: {compose_file}",
            )

        interactive = output is not None and sys.stdout.isatty() and sys.stderr.isatty()
        if output is not None and not interactive:
            output(f"$ {docker_compose} -f {compose_file} down")

        # Run docker compose down
        down_rc = await self._run_streamed(
            [docker_compose, "-f", str(compose_file), "down"],
            cwd=str(compose_file.parent),
            output=output,
        )
        if down_rc != 0:
            return ServiceActionResult(
                service_name=service_name,
                success=False,
                detail="down failed",
            )

        if output is not None and not interactive:
            output(f"$ {docker_compose} -f {compose_file} up -d")

        # Run docker compose up -d
        up_rc = await self._run_streamed(
            [docker_compose, "-f", str(compose_file), "up", "-d"],
            cwd=str(compose_file.parent),
            output=output,
        )
        if up_rc != 0:
            return ServiceActionResult(
                service_name=service_name,
                success=False,
                detail="up failed",
            )

        return ServiceActionResult(
            service_name=service_name,
            success=True,
            detail="recreated",
        )

    async def perform_recreate(
        self,
        service_arg: str,
        *,
        output: Callable[[str], None] | None = None,
    ) -> list[ServiceActionResult]:
        """Recreate one or all services via docker compose down/up."""
        service_names = self.get_service_names(service_arg)
        results: list[ServiceActionResult] = []
        interactive = output is not None and sys.stdout.isatty() and sys.stderr.isatty()

        for name in service_names:
            if output is not None and not interactive and len(service_names) > 1:
                output(f"== recreate {name} ==")
            result = await self.recreate_service(name, output=output)
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

        docker_compose = self._docker_compose_bin()
        if docker_compose is None:
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

    def _docker_compose_bin(self) -> str | None:
        docker_compose = (
            shutil.which("docker-compose")
            or "/run/current-system/sw/bin/docker-compose"
        )
        return docker_compose if Path(docker_compose).exists() else None

    async def _compose_build_enabled(self, service_name: str) -> bool:
        unit = self.compose_unit_for(service_name)
        props = await self.systemctl.show(unit, ["ExecStart"])
        exec_start = props.get("ExecStart", "")
        return "--build" in exec_start

    def _compose_up_args(
        self,
        docker_compose: str,
        compose_file: Path,
        *,
        build: bool,
        force_recreate: bool,
        remove_orphans: bool,
    ) -> list[str]:
        args = [docker_compose, "-f", str(compose_file), "up", "-d"]
        if remove_orphans:
            args.append("--remove-orphans")
        if force_recreate:
            args.append("--force-recreate")
        if build:
            args.append("--build")
        return args
