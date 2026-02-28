"""Systemd service controller with async support."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import TYPE_CHECKING

from ..exceptions import SystemctlError

if TYPE_CHECKING:
    from ..config import TimerConfig

logger = logging.getLogger("svc.controllers.systemctl")


class TimerResult(StrEnum):
    """Result of a timer's associated service execution."""

    SUCCESS = "success"
    FAILED = "failed"
    UNKNOWN = "unknown"


@dataclass
class TimerStatus:
    """Status information for a systemd timer."""

    name: str
    unit: str
    description: str
    last_run: str | None
    next_run: str | None
    last_result: TimerResult
    is_active: bool

    @property
    def is_ok(self) -> bool:
        """Check if timer is healthy (active and last run succeeded)."""
        return self.is_active and self.last_result == TimerResult.SUCCESS


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

    async def get_timer_status(self, timer: TimerConfig) -> TimerStatus:
        """Get status information for a systemd timer."""
        timer_unit = timer.unit
        # Associated service is the timer unit minus .timer + .service
        service_unit = timer_unit.replace(".timer", ".service")

        # Query timer properties
        timer_props = await self.show(
            timer_unit,
            [
                "ActiveState",
                "NextElapseUSecRealtime",
                "NextElapseUSec",
                "LastTriggerUSecRealtime",
                "LastTriggerUSec",
            ],
        )

        # Query associated service result
        service_props = await self.show(service_unit, ["Result"])

        # Parse last trigger time
        last_run: str | None = None
        last_trigger = (
            timer_props.get("LastTriggerUSecRealtime", "")
            or timer_props.get("LastTriggerUSec", "")
        )
        if last_trigger and last_trigger not in ("n/a", "0"):
            last_run = _format_timestamp(last_trigger)

        # Parse next elapse time
        next_run: str | None = None
        next_elapse = (
            timer_props.get("NextElapseUSecRealtime", "")
            or timer_props.get("NextElapseUSec", "")
        )
        if next_elapse and next_elapse not in ("n/a", "0"):
            next_run = _format_timestamp(next_elapse)

        # Determine last result
        service_result = service_props.get("Result", "")
        if service_result == "success":
            last_result = TimerResult.SUCCESS
        elif service_result and service_result != "":
            last_result = TimerResult.FAILED
        else:
            last_result = TimerResult.UNKNOWN

        # Check if timer is active
        is_active = timer_props.get("ActiveState", "") == "active"

        return TimerStatus(
            name=timer.name,
            unit=timer.unit,
            description=timer.description,
            last_run=last_run,
            next_run=next_run,
            last_result=last_result,
            is_active=is_active,
        )


def _format_timestamp(timestamp_str: str) -> str:
    """Format a systemd timestamp string to human-readable format."""
    min_parts = 3
    # systemd returns timestamps like "Sat 2025-01-11 05:00:00 UTC"
    # or epoch microseconds - we try to parse and simplify
    ts = timestamp_str.strip()
    formatted = ""

    if ts:
        if ts.isdigit():
            usec = int(ts, 10)
            if usec > 0:
                dt = datetime.fromtimestamp(usec / 1_000_000).astimezone()
                formatted = dt.strftime("%Y-%m-%d %H:%M")
        else:
            formatted = ts[:16]
            try:
                # Try parsing the human-readable format
                if " " in ts:
                    # Take the date/time portion, skip day name
                    parts = ts.split()
                    if len(parts) >= min_parts:
                        formatted = f"{parts[1]} {parts[2][:5]}"  # "2025-01-11 05:00"
            except (ValueError, IndexError):
                formatted = ts[:16]

    return formatted


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
