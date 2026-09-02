"""Typer application for the svc backup CLI."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Annotated, Any, cast

import typer

from ..controllers import SystemctlController
from .args import (
    BackupArgs,
    BackupEnvironment,
    ListArgs,
    ListBackupsArgs,
    RestoreArgs,
)
from .commands import (
    BackupCommand,
    ListBackupsCommand,
    ListCommand,
    RestoreCommand,
    register_restic_command,
)
from .runtime import GlobalOptions, run_command, setup_logging


def _load_services_for_completion(config_path: str, *, backup_only: bool) -> list[str]:
    """Load service names from the JSON config for shell completion."""
    try:
        with Path(config_path).open() as f:
            raw: Any = json.load(f)
    except (OSError, json.JSONDecodeError):
        return []

    if not isinstance(raw, dict):
        return []

    data = cast("dict[str, Any]", raw)
    raw_services: Any = data.get("services") or {}
    if not isinstance(raw_services, dict):
        return []

    services_obj = cast("dict[str, Any]", raw_services)

    if not backup_only:
        return list(services_obj.keys())

    services: list[str] = []
    for name, spec in services_obj.items():
        if not isinstance(spec, dict):
            continue
        spec_dict = cast("dict[str, Any]", spec)
        backup_obj = spec_dict.get("backup")
        if not isinstance(backup_obj, dict):
            continue
        backup = cast("dict[str, Any]", backup_obj)
        if bool(backup.get("enable", False)):
            services.append(name)
    return services


def _complete_services(
    ctx: typer.Context,
    incomplete: str,
    *,
    allow_all: bool,
) -> list[str]:
    """Return configured backup service names matching the partial value."""
    params = ctx.find_root().params or {}
    config_param = params.get("config")
    config_path = config_param if isinstance(config_param, str) else "/etc/svc/services.json"
    services = _load_services_for_completion(config_path, backup_only=True)
    if allow_all:
        services.append("all")
    return sorted({service for service in services if service.startswith(incomplete)})


def _complete_backup_service(ctx: typer.Context, incomplete: str) -> list[str]:
    """Complete the name of a backup-enabled service."""
    return _complete_services(ctx, incomplete, allow_all=False)


def _complete_backup_service_or_all(ctx: typer.Context, incomplete: str) -> list[str]:
    """Complete a backup-enabled service name or the `all` selector."""
    return _complete_services(ctx, incomplete, allow_all=True)


app = typer.Typer(context_settings={"help_option_names": ["-h", "--help"]})


@app.callback()
def cli(
    ctx: typer.Context,
    config: Annotated[
        str,
        typer.Option("--config", "-c", help="Path to services JSON config", show_default=True),
    ] = "/etc/svc/services.json",
    verbose: Annotated[
        bool,
        typer.Option("--verbose", "-v", help="Enable verbose output"),
    ] = False,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", "-n", help="Show actions without executing"),
    ] = False,
) -> None:
    """Manage backup and restore operations for homeserver services."""
    setup_logging(verbose=verbose)
    ctx.obj = GlobalOptions(config=config, verbose=verbose, dry_run=dry_run)


register_restic_command(app)


@app.command("list")
def list_cmd(
    ctx: typer.Context,
    backup_env: Annotated[
        BackupEnvironment,
        typer.Option(
            "--backup-env",
            case_sensitive=False,
            help="Which systemd backup unit to check for last result",
            show_default=True,
        ),
    ] = BackupEnvironment.local,
) -> None:
    """List services and their backup status."""
    run_command(ctx, ListCommand(), ListArgs(backup_env=backup_env.value))


@app.command("list-backups")
def list_backups_cmd(
    ctx: typer.Context,
    env: Annotated[BackupEnvironment, typer.Argument(case_sensitive=False)],
    service: Annotated[str, typer.Argument(autocompletion=_complete_backup_service)],
) -> None:
    """List restic snapshots for a service."""
    run_command(ctx, ListBackupsCommand(), ListBackupsArgs(env=env.value, service=service))


@app.command("logs")
def logs_cmd(
    env: Annotated[BackupEnvironment, typer.Argument(case_sensitive=False)],
) -> None:
    """Show logs for scheduled backups."""
    unit = "backup.service" if env is BackupEnvironment.local else "backup-remote.service"
    try:
        exit_code = asyncio.run(SystemctlController().logs(unit))
        raise typer.Exit(code=exit_code)
    except (KeyboardInterrupt, asyncio.CancelledError):
        raise typer.Exit(code=130) from None


@app.command("backup")
def backup_cmd(
    ctx: typer.Context,
    env: Annotated[BackupEnvironment, typer.Argument(case_sensitive=False)],
    service: Annotated[str, typer.Argument(autocompletion=_complete_backup_service_or_all)],
) -> None:
    """Run backups"""
    run_command(ctx, BackupCommand(), BackupArgs(env=env.value, service=service))


@app.command("restore")
def restore_cmd(
    ctx: typer.Context,
    env: Annotated[BackupEnvironment, typer.Argument(case_sensitive=False)],
    service: Annotated[str, typer.Argument(autocompletion=_complete_backup_service)],
    snapshot: Annotated[str, typer.Argument()] = "latest",
    *,
    verify_includes: Annotated[
        bool,
        typer.Option(
            "--verify-includes",
            help="Check snapshot contains each configured path/PVC before restoring",
        ),
    ] = False,
) -> None:
    """Restore a service from a snapshot (default: `latest`)."""
    run_command(
        ctx,
        RestoreCommand(),
        RestoreArgs(
            env=env.value,
            service=service,
            snapshot=snapshot,
            verify_includes=verify_includes,
        ),
    )
