"""Systemd service controller with async support."""

from __future__ import annotations

import asyncio
import logging

logger = logging.getLogger("svc.controllers.systemctl")


class SystemctlController:
    """Reads backup unit status from systemd."""

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
