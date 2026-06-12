"""Typed argument payloads passed from click to command objects."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class BackupArgs:
    """Arguments for `svc backup`."""

    env: str
    service: str


@dataclass(frozen=True)
class RestoreArgs:
    """Arguments for `svc restore`."""

    env: str
    service: str
    snapshot: str
    verify_includes: bool


@dataclass(frozen=True)
class ListArgs:
    """Arguments for `svc list`."""

    backup_env: str


@dataclass(frozen=True)
class ListBackupsArgs:
    """Arguments for `svc list-backups`."""

    env: str
    service: str
