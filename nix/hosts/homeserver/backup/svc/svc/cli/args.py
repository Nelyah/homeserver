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
    detailed: bool = False


@dataclass(frozen=True)
class ListBackupsArgs:
    """Arguments for `svc list-backups`."""

    env: str
    service: str


@dataclass(frozen=True)
class ServiceActionArgs:
    """Arguments for `svc start` / `svc stop` / non-recreate `svc restart`."""

    service: str
    build: bool


@dataclass(frozen=True)
class RestartArgs:
    """Arguments for `svc restart`."""

    service: str
    recreate: bool
    build: bool


@dataclass(frozen=True)
class LogsArgs:
    """Arguments for `svc logs`."""

    service: str
    follow: bool
    tail: int
    timestamps: bool


@dataclass(frozen=True)
class DoctorArgs:
    """Arguments for `svc doctor`."""

    since: str = "24h"
    full: bool = False


@dataclass(frozen=True)
class EmptyArgs:
    """Marker args for commands with no arguments."""
