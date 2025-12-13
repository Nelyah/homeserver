"""Service management operations (start/stop/restart/logs)."""

import asyncio
import logging
import shutil
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from ..config import Config
from ..exceptions import ConfigError, DependencyError
from .service_helpers import get_service

logger = logging.getLogger("svc.core.service_manager")


@dataclass
class ServiceActionResult:
    """Result of a service action (start/stop/restart)."""

    service_name: str
    success: bool
    detail: str


ActionType = Literal["start", "stop", "restart"]


@dataclass(frozen=True)
class _ComposeStep:
    args: list[str]
    failure_detail: str


class ServiceManager:
    """Manages docker-compose service lifecycle operations."""

    def __init__(self, config: Config, *, dry_run: bool = False):
        self.config = config
        self.dry_run = dry_run

    def compose_file_for(self, service_name: str) -> Path:
        """Get the deployed docker-compose.yml path for a service."""
        return Path(self.config.paths.deploy_root) / service_name / "docker-compose.yml"

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
        return [get_service(self.config, service_arg).name]

    async def _perform_action(
        self,
        action: ActionType,
        service_name: str,
        *,
        build: bool = False,
        output: Callable[[str], None] | None = None,
    ) -> ServiceActionResult:
        """Perform a single action on a service via docker-compose directly."""
        compose_file = self.compose_file_for(service_name)
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

        try:
            steps, success_detail = self._compose_steps_for_action(
                action,
                docker_compose=docker_compose,
                compose_file=compose_file,
                build=build,
            )

            for step in steps:
                if output is not None and not interactive:
                    output(f"$ {' '.join(step.args)}")
                rc = await self._run_streamed(
                    step.args,
                    cwd=str(compose_file.parent),
                    output=output,
                )
                if rc != 0:
                    return ServiceActionResult(
                        service_name=service_name,
                        success=False,
                        detail=step.failure_detail,
                    )

            return ServiceActionResult(
                service_name=service_name,
                success=True,
                detail=success_detail,
            )
        except OSError as e:
            return ServiceActionResult(
                service_name=service_name,
                success=False,
                detail=str(e),
            )

    async def perform_action(
        self,
        action: ActionType,
        service_arg: str,
        *,
        build: bool = False,
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
            result = await self._perform_action(action, name, build=build, output=output)
            results.append(result)

        return results

    async def _run_streamed(
        self,
        args: list[str],
        *,
        cwd: str,
        output: Callable[[str], None] | None,
    ) -> int:
        if self.dry_run:
            if output is not None:
                output(f"[dry-run] Would run in {cwd}: {' '.join(args)}")
            return 0

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
        build: bool = False,
        output: Callable[[str], None] | None = None,
    ) -> ServiceActionResult:
        """Recreate a service by running docker compose down/up."""
        svc = get_service(self.config, service_name)
        compose_file = self.compose_file_for(svc.name)

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
            [
                docker_compose,
                "-f",
                str(compose_file),
                "up",
                "-d",
                *([] if not build else ["--build"]),
            ],
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
        build: bool = False,
        output: Callable[[str], None] | None = None,
    ) -> list[ServiceActionResult]:
        """Recreate one or all services via docker compose down/up."""
        service_names = self.get_service_names(service_arg)
        results: list[ServiceActionResult] = []
        interactive = output is not None and sys.stdout.isatty() and sys.stderr.isatty()

        for name in service_names:
            if output is not None and not interactive and len(service_names) > 1:
                output(f"== recreate {name} ==")
            result = await self.recreate_service(name, build=build, output=output)
            results.append(result)

        return results

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
        svc = get_service(self.config, service_name)

        docker_compose = self._docker_compose_bin()
        if docker_compose is None:
            message = (
                "docker-compose not found in PATH or at /run/current-system/sw/bin/docker-compose"
            )
            raise DependencyError(message)

        compose_file = self.compose_file_for(svc.name)
        if not compose_file.exists():
            message = f"Compose file not found: {compose_file}"
            raise ConfigError(message)

        args = [docker_compose, "-f", str(compose_file), "logs"]
        if follow:
            args.append("-f")
        if timestamps:
            args.append("-t")
        if tail is not None:
            args.extend(["--tail", str(tail)])

        logger.info("Streaming logs for %s...", svc.name)

        proc = await asyncio.create_subprocess_exec(*args, cwd=str(compose_file.parent))
        await proc.wait()
        return proc.returncode or 0

    def _docker_compose_bin(self) -> str | None:
        docker_compose = (
            shutil.which("docker-compose") or "/run/current-system/sw/bin/docker-compose"
        )
        return docker_compose if Path(docker_compose).exists() else None

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

    def _compose_down_args(
        self, docker_compose: str, compose_file: Path, *, remove_orphans: bool
    ) -> list[str]:
        args = [docker_compose, "-f", str(compose_file), "down"]
        if remove_orphans:
            args.append("--remove-orphans")
        return args

    def _compose_steps_for_action(
        self,
        action: ActionType,
        *,
        docker_compose: str,
        compose_file: Path,
        build: bool,
    ) -> tuple[list[_ComposeStep], str]:
        down = _ComposeStep(
            args=self._compose_down_args(
                docker_compose,
                compose_file,
                remove_orphans=True,
            ),
            failure_detail="down failed",
        )
        up = _ComposeStep(
            args=self._compose_up_args(
                docker_compose,
                compose_file,
                build=build,
                force_recreate=True,
                remove_orphans=True,
            ),
            failure_detail="up failed",
        )

        if action == "stop":
            return [down], "stopped"
        if action == "start":
            return [up], "started"
        return [down, up], "restarted"
