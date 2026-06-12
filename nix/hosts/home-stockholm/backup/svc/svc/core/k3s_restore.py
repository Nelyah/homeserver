"""K3s embedded-etcd restore orchestration."""

from __future__ import annotations

import asyncio
import logging
import os
import shlex
import shutil
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from ..config import ServiceConfig
from ..controllers import ResticRunner
from ..exceptions import (
    EXIT_CONFIG_ERROR,
    EXIT_RESTIC_ERROR,
    EXIT_SUCCESS,
)

logger = logging.getLogger("svc.core.k3s_restore")

K3S_SNAPSHOTS_PATH = "/var/lib/rancher/k3s/server/db/snapshots"
K3S_TOKEN_PATH = "/var/lib/rancher/k3s/server/token"
K3S_SERVICE = "k3s.service"


@dataclass
class CommandResult:
    """Result of a subprocess command."""

    returncode: int
    stdout: str = ""
    stderr: str = ""


@dataclass
class K3sRestoreResult:
    """Result of a k3s embedded-etcd restore."""

    success: bool
    exit_code: int
    message: str
    snapshot_id: str = ""
    snapshot_path: str = ""


class K3sRestoreOrchestrator:
    """Restore k3s embedded etcd using the backed-up snapshot and server token."""

    def __init__(
        self,
        restic: ResticRunner,
        *,
        dry_run: bool,
        systemctl_bin: str = "/run/current-system/sw/bin/systemctl",
    ):
        self.restic = restic
        self.dry_run = dry_run
        self.systemctl_bin = systemctl_bin

    async def restore_service(
        self,
        *,
        svc: ServiceConfig,
        snapshot_spec: str,
        verify_inputs: bool,
    ) -> K3sRestoreResult:
        """Restore k3s from a restic snapshot containing an etcd snapshot."""
        snapshot_id = await self._resolve_snapshot(svc, snapshot_spec)
        if snapshot_id is None:
            return K3sRestoreResult(
                success=False,
                exit_code=EXIT_RESTIC_ERROR,
                message=f"No snapshots found for {svc.name} (tag: {svc.restore.tag})",
            )

        if verify_inputs or self.dry_run:
            invalid = await self._validate_restic_inputs(snapshot_id)
            if invalid is not None:
                return K3sRestoreResult(
                    success=False,
                    exit_code=EXIT_CONFIG_ERROR,
                    snapshot_id=snapshot_id,
                    message=invalid,
                )

        base_command, error = await self._k3s_service_command()
        if error is not None:
            return K3sRestoreResult(
                success=False,
                exit_code=EXIT_CONFIG_ERROR,
                snapshot_id=snapshot_id,
                message=error,
            )

        if self.dry_run:
            return K3sRestoreResult(
                success=True,
                exit_code=EXIT_SUCCESS,
                snapshot_id=snapshot_id,
                message=(
                    "Dry run: would restore k3s etcd by staging the backed-up "
                    "server token and newest etcd snapshot, stopping k3s, running "
                    "the k3s.service command with --cluster-reset, installing the "
                    "backed-up server token, then starting k3s"
                ),
            )

        with tempfile.TemporaryDirectory(prefix="svc-k3s-restore.") as staging_raw:
            staging = Path(staging_raw)
            restore_status = await self.restic.restore(
                snapshot_id,
                [K3S_SNAPSHOTS_PATH, K3S_TOKEN_PATH],
                str(staging),
            )
            if restore_status != 0:
                return K3sRestoreResult(
                    success=False,
                    exit_code=EXIT_RESTIC_ERROR,
                    snapshot_id=snapshot_id,
                    message=f"Failed to stage k3s snapshot/token from restic (exit code {restore_status})",
                )

            token_path = self._staged_path(staging, K3S_TOKEN_PATH)
            snapshots_dir = self._staged_path(staging, K3S_SNAPSHOTS_PATH)
            snapshot_path = self._select_snapshot(snapshots_dir)
            invalid = self._validate_staged_files(token_path, snapshot_path)
            if invalid is not None:
                return K3sRestoreResult(
                    success=False,
                    exit_code=EXIT_CONFIG_ERROR,
                    snapshot_id=snapshot_id,
                    message=invalid,
                )
            assert snapshot_path is not None

            stop_status = await self._run([self.systemctl_bin, "stop", "k3s"])
            if stop_status != 0:
                return K3sRestoreResult(
                    success=False,
                    exit_code=EXIT_CONFIG_ERROR,
                    snapshot_id=snapshot_id,
                    snapshot_path=str(snapshot_path),
                    message=f"Failed to stop k3s.service (exit code {stop_status})",
                )

            reset_command = self._cluster_reset_command(base_command, snapshot_path, token_path)
            reset_status = await self._run(reset_command)
            if reset_status != 0:
                return K3sRestoreResult(
                    success=False,
                    exit_code=EXIT_CONFIG_ERROR,
                    snapshot_id=snapshot_id,
                    snapshot_path=str(snapshot_path),
                    message=(
                        "k3s cluster reset failed "
                        f"(exit code {reset_status}); k3s.service was left stopped"
                    ),
                )

            try:
                self._install_token(token_path)
            except OSError as error:
                return K3sRestoreResult(
                    success=False,
                    exit_code=EXIT_CONFIG_ERROR,
                    snapshot_id=snapshot_id,
                    snapshot_path=str(snapshot_path),
                    message=(
                        "k3s cluster reset completed, but the backed-up server token "
                        f"could not be installed at {K3S_TOKEN_PATH}: {error}"
                    ),
                )

            start_status = await self._run([self.systemctl_bin, "start", "k3s"])
            if start_status != 0:
                return K3sRestoreResult(
                    success=False,
                    exit_code=EXIT_CONFIG_ERROR,
                    snapshot_id=snapshot_id,
                    snapshot_path=str(snapshot_path),
                    message=f"k3s cluster reset completed, but k3s.service failed to start (exit code {start_status})",
                )

            return K3sRestoreResult(
                success=True,
                exit_code=EXIT_SUCCESS,
                snapshot_id=snapshot_id,
                snapshot_path=str(snapshot_path),
                message=f"Restored k3s embedded etcd from restic snapshot {snapshot_id[:8]}",
            )

    async def _resolve_snapshot(self, svc: ServiceConfig, snapshot_spec: str) -> str | None:
        """Resolve `latest` to the newest restic snapshot for the service restore tag."""
        if snapshot_spec == "latest":
            return await self.restic.get_latest_snapshot_id(svc.restore.tag)
        return snapshot_spec

    async def _validate_restic_inputs(self, snapshot_id: str) -> str | None:
        """Check that the restic snapshot contains the minimum k3s restore inputs."""
        token = await self.restic.ls(snapshot_id, K3S_TOKEN_PATH)
        if token.returncode != 0:
            return f"Restic snapshot {snapshot_id[:8]} does not contain {K3S_TOKEN_PATH}"

        snapshots = await self.restic.ls(snapshot_id, K3S_SNAPSHOTS_PATH)
        if snapshots.returncode != 0:
            return f"Restic snapshot {snapshot_id[:8]} does not contain {K3S_SNAPSHOTS_PATH}"

        if "svc-backup" not in snapshots.stdout:
            return (
                f"Restic snapshot {snapshot_id[:8]} contains {K3S_SNAPSHOTS_PATH}, "
                "but no svc-backup etcd snapshot was found there"
            )

        return None

    async def _k3s_service_command(self) -> tuple[list[str], str | None]:
        """Read the current k3s.service ExecStart command from systemd."""
        result = await self._run_capture(
            [self.systemctl_bin, "show", K3S_SERVICE, "-p", "ExecStart", "--value"]
        )
        if result.returncode != 0:
            detail = result.stderr.strip() or result.stdout.strip()
            return [], f"Failed to read {K3S_SERVICE} ExecStart from systemd: {detail}"

        command = self._parse_exec_start(result.stdout)
        if command is None:
            return [], f"Could not parse {K3S_SERVICE} ExecStart from systemd"
        if "server" not in command:
            return [], f"{K3S_SERVICE} ExecStart does not appear to run `k3s server`"

        return command, None

    def _parse_exec_start(self, raw: str) -> list[str] | None:
        """Extract argv[] from `systemctl show -p ExecStart --value` output."""
        for line in raw.splitlines():
            if "argv[]=" not in line:
                continue

            argv_raw = line.split("argv[]=", 1)[1].split(" ;", 1)[0].strip()
            if not argv_raw:
                continue

            try:
                command = shlex.split(argv_raw)
            except ValueError:
                return None
            if command:
                return command

        return None

    def _cluster_reset_command(
        self, base_command: list[str], snapshot_path: Path, token_path: Path
    ) -> list[str]:
        """Build the k3s reset command from the service command plus restore flags."""
        return [
            *self._without_restore_only_flags(base_command),
            "--cluster-reset",
            f"--cluster-reset-restore-path={snapshot_path}",
            f"--token-file={token_path}",
        ]

    def _without_restore_only_flags(self, command: list[str]) -> list[str]:
        """Remove stale reset/token flags before appending the restore-specific ones."""
        result: list[str] = []
        skip_next = False
        flags_with_values = {
            "--cluster-reset-restore-path",
            "--token",
            "-t",
            "--token-file",
        }

        for arg in command:
            if skip_next:
                skip_next = False
                continue
            if arg == "--cluster-reset":
                continue
            if arg in flags_with_values:
                skip_next = True
                continue
            if any(arg.startswith(f"{flag}=") for flag in flags_with_values):
                continue
            result.append(arg)

        return result

    def _staged_path(self, staging: Path, absolute_path: str) -> Path:
        """Map an absolute source path into a restic restore staging directory."""
        return staging / absolute_path.lstrip("/")

    def _validate_staged_files(self, token_path: Path, snapshot_path: Path | None) -> str | None:
        """Validate that the staged token and selected snapshot are usable."""
        if not token_path.is_file():
            return f"Backed-up k3s server token was not restored at {token_path}"
        if token_path.stat().st_size == 0:
            return f"Backed-up k3s server token is empty at {token_path}"
        if snapshot_path is None:
            return (
                "No svc-backup* etcd snapshot file was found in the restored "
                "k3s snapshots directory"
            )
        return None

    def _install_token(self, token_path: Path) -> None:
        """Install the restored token at the real k3s token path for normal service start."""
        target = Path(K3S_TOKEN_PATH)
        token_bytes = token_path.read_bytes()

        target.parent.mkdir(parents=True, mode=0o700, exist_ok=True)
        if target.exists() and target.read_bytes() != token_bytes:
            timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
            backup = target.with_name(f"{target.name}.svc-restore-backup-{timestamp}")
            shutil.copy2(target, backup)

        temp = target.with_name(f".{target.name}.svc-restore")
        temp.write_bytes(token_bytes)
        os.chmod(temp, 0o600)
        temp.replace(target)

    def _select_snapshot(self, snapshots_dir: Path) -> Path | None:
        """Pick the newest staged etcd snapshot, preferring snapshots made by svc."""
        if not snapshots_dir.is_dir():
            return None

        candidates = [
            path
            for path in snapshots_dir.iterdir()
            if path.is_file() and path.name.startswith("svc-backup")
        ]
        if not candidates:
            return None

        return max(candidates, key=lambda path: (path.stat().st_mtime_ns, path.name))

    async def _run(self, args: list[str]) -> int:
        """Run a subprocess, streaming output to the caller's terminal."""
        logger.info("Running: %s", " ".join(args))
        proc = await asyncio.create_subprocess_exec(*args)
        await proc.wait()
        return proc.returncode or 0

    async def _run_capture(self, args: list[str]) -> CommandResult:
        """Run a subprocess and capture stdout/stderr."""
        logger.info("Running: %s", " ".join(args))
        proc = await asyncio.create_subprocess_exec(
            *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout_bytes, stderr_bytes = await proc.communicate()
        return CommandResult(
            returncode=proc.returncode or 0,
            stdout=stdout_bytes.decode() if stdout_bytes else "",
            stderr=stderr_bytes.decode() if stderr_bytes else "",
        )
