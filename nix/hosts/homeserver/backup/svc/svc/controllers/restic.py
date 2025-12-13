"""Restic backup controller with async support."""

import asyncio
import json
import logging
import os
from dataclasses import dataclass
from datetime import datetime
from typing import Any, TypedDict, cast

from ..config import RetentionPolicy
from ..exceptions import ResticError

logger = logging.getLogger("svc.controllers.restic")


class ResticSnapshot(TypedDict, total=False):
    id: str
    time: str
    hostname: str


@dataclass
class CommandResult:
    """Result of a restic command execution."""

    returncode: int
    stdout: str = ""
    stderr: str = ""


class ResticRunner:
    """Executes restic commands asynchronously."""

    def __init__(self, env_vars: dict[str, str], dry_run: bool = False):
        self.env_vars = env_vars
        self.dry_run = dry_run
        self.restic = "/run/current-system/sw/bin/restic"

    async def _run(self, args: list[str], capture_output: bool = False) -> CommandResult:
        """Run a restic command with environment."""
        env = os.environ.copy()
        env.update(self.env_vars)

        cmd = [self.restic, *args]
        logger.debug("Running: %s", " ".join(cmd))

        if self.dry_run and not capture_output:
            logger.info(f"[DRY RUN] Would run: restic {' '.join(args)}")
            return CommandResult(returncode=0)

        if capture_output:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                env=env,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout_bytes, stderr_bytes = await proc.communicate()
            return CommandResult(
                returncode=proc.returncode or 0,
                stdout=stdout_bytes.decode() if stdout_bytes else "",
                stderr=stderr_bytes.decode() if stderr_bytes else "",
            )
        proc = await asyncio.create_subprocess_exec(*cmd, env=env)
        await proc.wait()
        return CommandResult(returncode=proc.returncode or 0)

    async def backup(self, paths: list[str], tags: list[str], exclude: list[str]) -> int:
        """Run restic backup command."""
        args = ["backup"]
        args.extend(paths)
        for tag in tags:
            args.extend(["--tag", tag])
        for pattern in exclude:
            args.extend(["--exclude", pattern])

        result = await self._run(args)
        return result.returncode

    async def forget(self, tags: list[str], policy: RetentionPolicy) -> int:
        """Run restic forget with retention policy."""
        args = ["forget"]

        if policy.last is not None:
            args.extend(["--keep-last", str(policy.last)])
        if policy.hourly is not None:
            args.extend(["--keep-hourly", str(policy.hourly)])
        if policy.daily is not None:
            args.extend(["--keep-daily", str(policy.daily)])
        if policy.weekly is not None:
            args.extend(["--keep-weekly", str(policy.weekly)])
        if policy.monthly is not None:
            args.extend(["--keep-monthly", str(policy.monthly)])
        if policy.yearly is not None:
            args.extend(["--keep-yearly", str(policy.yearly)])

        args.append("--prune")

        for tag in tags:
            args.extend(["--tag", tag])

        result = await self._run(args)
        return result.returncode

    async def restore(self, snapshot_id: str, include_paths: list[str], target: str = "/") -> int:
        """Run restic restore command with --delete flag."""
        args = ["restore", snapshot_id]

        for path in include_paths:
            args.extend(["--include", path])

        args.extend(["--delete", "--target", target])

        result = await self._run(args)
        return result.returncode

    async def snapshots(self, tags: list[str]) -> list[ResticSnapshot]:
        """List snapshots for given tags."""
        args = ["snapshots", "--json"]
        for tag in tags:
            args.extend(["--tag", tag])

        result = await self._run(args, capture_output=True)
        if result.returncode != 0:
            message = f"Failed to list snapshots: {result.stderr}"
            raise ResticError(message)

        try:
            raw: Any = json.loads(result.stdout) if result.stdout else []
        except json.JSONDecodeError:
            return []

        if not isinstance(raw, list):
            return []

        snapshots: list[ResticSnapshot] = []
        raw_list = cast("list[Any]", raw)
        for item in raw_list:
            if not isinstance(item, dict):
                continue
            item_dict = cast("dict[str, Any]", item)
            snap: ResticSnapshot = {}
            snap_id = item_dict.get("id")
            if isinstance(snap_id, str):
                snap["id"] = snap_id
            snap_time = item_dict.get("time")
            if isinstance(snap_time, str):
                snap["time"] = snap_time
            snap_hostname = item_dict.get("hostname")
            if isinstance(snap_hostname, str):
                snap["hostname"] = snap_hostname
            snapshots.append(snap)

        return snapshots

    async def get_latest_snapshot_id(self, tag: str) -> str | None:
        """Get ID of the latest snapshot for a tag (across all hosts)."""
        try:
            snapshots = await self.snapshots([tag])
        except ResticError:
            return None
        latest_id, _latest_time = self._latest_snapshot_by_parsed_time(snapshots)
        if latest_id is not None:
            return latest_id

        return self._latest_snapshot_by_lex_time(snapshots)

    def _parse_snapshot_time(self, value: str | None) -> datetime | None:
        if not value:
            return None
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            if value.endswith("Z"):
                try:
                    return datetime.fromisoformat(f"{value[:-1]}+00:00")
                except ValueError:
                    return None
            return None

    def _latest_snapshot_by_parsed_time(
        self, snapshots: list[ResticSnapshot]
    ) -> tuple[str | None, datetime | None]:
        latest_id: str | None = None
        latest_time: datetime | None = None

        for snap in snapshots:
            t = self._parse_snapshot_time(snap.get("time"))
            if t is None:
                continue
            if latest_time is None or t > latest_time:
                snap_id = snap.get("id")
                if isinstance(snap_id, str):
                    latest_time = t
                    latest_id = snap_id

        return latest_id, latest_time

    def _latest_snapshot_by_lex_time(self, snapshots: list[ResticSnapshot]) -> str | None:
        candidates = [
            s for s in snapshots if isinstance(s.get("id"), str) and isinstance(s.get("time"), str)
        ]
        if not candidates:
            return None
        best = max(candidates, key=lambda s: cast("str", s.get("time") or ""))
        best_id = best.get("id")
        return best_id if isinstance(best_id, str) else None

    async def ls(self, snapshot_id: str, path: str | None = None) -> CommandResult:
        """Run `restic ls` for a snapshot, optionally restricted to a path."""
        args = ["ls", snapshot_id]
        if path is not None:
            args.extend(["--path", path])
        return await self._run(args, capture_output=True)
