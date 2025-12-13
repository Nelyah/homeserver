"""Systemd service controller with async support."""

import asyncio
import logging

from ..exceptions import SystemctlError

logger = logging.getLogger("svc.controllers.systemctl")


class SystemctlController:
    """Controls systemd services via systemctl."""

    def __init__(self, dry_run: bool = False):
        self.dry_run = dry_run
        self.systemctl = "/run/current-system/sw/bin/systemctl"

    async def _run(
        self, args: list[str], capture_output: bool = False
    ) -> asyncio.subprocess.Process:
        """Run systemctl command asynchronously."""
        cmd = [self.systemctl, *args]
        logger.debug("Running: %s", " ".join(cmd))

        if capture_output:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
        else:
            proc = await asyncio.create_subprocess_exec(*cmd)

        return proc

    async def is_loaded(self, unit: str) -> bool:
        """Check if a systemd unit is loaded."""
        try:
            proc = await self._run(
                ["show", "-p", "LoadState", "--value", unit], capture_output=True
            )
            stdout, _ = await proc.communicate()
            return stdout.decode().strip() == "loaded"
        except (OSError, UnicodeDecodeError):
            return False

    async def is_active(self, unit: str) -> bool:
        """Check if a systemd unit is currently active."""
        try:
            proc = await self._run(["--quiet", "is-active", unit])
            await proc.wait()
        except OSError:
            return False
        else:
            return proc.returncode == 0

    async def stop(self, unit: str) -> None:
        """Stop a systemd unit."""
        logger.info("Stopping %s...", unit)
        if self.dry_run:
            logger.info("[DRY RUN] Would stop %s", unit)
            return

        proc = await self._run(["stop", unit])
        await proc.wait()
        if proc.returncode != 0:
            message = f"Failed to stop {unit}"
            raise SystemctlError(message)

    async def start(self, unit: str) -> None:
        """Start a systemd unit."""
        logger.info("Starting %s...", unit)
        if self.dry_run:
            logger.info("[DRY RUN] Would start %s", unit)
            return

        proc = await self._run(["start", unit])
        await proc.wait()
        if proc.returncode != 0:
            message = f"Failed to start {unit}"
            raise SystemctlError(message)

    async def show(self, unit: str, properties: list[str]) -> dict[str, str]:
        """Return a mapping of `systemctl show` properties for a unit."""
        args = ["show"]
        for prop in properties:
            args.extend(["-p", prop])
        args.append(unit)

        proc = await self._run(args, capture_output=True)
        stdout, _ = await proc.communicate()

        if proc.returncode != 0:
            return {}

        props: dict[str, str] = {}
        for line in stdout.decode().splitlines():
            if "=" not in line:
                continue
            key, _, value = line.partition("=")
            props[key] = value
        return props


async def unit_last_success(systemctl: SystemctlController, unit: str) -> bool | None:
    """Check if a unit's last run was successful."""
    props = await systemctl.show(
        unit,
        [
            "LoadState",
            "Result",
            "ExecMainCode",
            "ExecMainStatus",
            "UnitFileState",
        ],
    )

    if not props:
        return None

    if props.get("LoadState") == "not-found":
        return None

    result = props.get("Result", "")
    if result == "success":
        return True
    if result != "":
        return False

    exec_status = props.get("ExecMainStatus", "")
    if exec_status != "":
        return exec_status == "0"

    return None
