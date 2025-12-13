"""Typed argument payloads passed from click to command objects."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class BackupArgs:
    env: str
    service: str


@dataclass(frozen=True)
class RestoreArgs:
    env: str
    service: str
    snapshot: str
    verify_includes: bool


@dataclass(frozen=True)
class ListArgs:
    backup_env: str


@dataclass(frozen=True)
class ListBackupsArgs:
    env: str
    service: str


@dataclass(frozen=True)
class ServiceActionArgs:
    service: str
    build: bool


@dataclass(frozen=True)
class RestartArgs:
    service: str
    recreate: bool
    build: bool


@dataclass(frozen=True)
class LogsArgs:
    service: str
    follow: bool
    tail: int
    timestamps: bool


@dataclass(frozen=True)
class EmptyArgs:
    """Marker args for commands with no arguments."""

