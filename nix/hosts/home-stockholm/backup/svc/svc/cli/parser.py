"""
Click-based CLI for svc.

This replaces the previous argparse+argcomplete implementation while keeping the
same commands/options and dynamic completion of service names.
"""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

import click
from click.shell_completion import CompletionItem

from ..config import load_config
from .args import (
    BackupArgs,
    ListArgs,
    ListBackupsArgs,
    RestoreArgs,
)
from .commands import (
    BackupCommand,
    ListBackupsCommand,
    ListCommand,
    RestoreCommand,
)
from .commands.base import AppContext, Command
from .renderer import create_renderer


@dataclass(frozen=True)
class GlobalOptions:
    """Global options parsed by click."""

    config: str
    verbose: bool
    dry_run: bool


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


class ServiceNameParam(click.ParamType):
    """click ParamType with dynamic service-name completion."""

    name = "service"

    def __init__(self, *, backup_only: bool, allow_all: bool):
        super().__init__()
        self._backup_only = backup_only
        self._allow_all = allow_all

    def shell_complete(
        self, ctx: click.Context, param: click.Parameter, incomplete: str
    ) -> list[CompletionItem]:
        """Return completion candidates for the `service` argument."""
        _ = param
        params = ctx.find_root().params or {}
        config_param = params.get("config")
        config_path = config_param if isinstance(config_param, str) else "/etc/svc/services.json"
        services = _load_services_for_completion(config_path, backup_only=self._backup_only)
        if self._allow_all:
            services.append("all")
        matches = sorted({s for s in services if s.startswith(incomplete)})
        return [CompletionItem(m) for m in matches]


def _get_app_ctx(ctx: click.Context) -> AppContext:
    """Create the AppContext from global click options."""
    options: GlobalOptions = ctx.ensure_object(GlobalOptions)  # type: ignore[assignment]
    config = load_config(options.config)
    renderer = create_renderer()
    return AppContext(
        config=config,
        renderer=renderer,
        dry_run=options.dry_run,
        verbose=options.verbose,
    )


def _run_command(ctx: click.Context, command: Command[Any], args: Any) -> None:
    """Run a command object using an isolated asyncio event loop."""
    app_ctx = _get_app_ctx(ctx)
    try:
        exit_code: int = asyncio.run(command.execute(args, app_ctx))
        raise click.exceptions.Exit(exit_code)
    except (KeyboardInterrupt, asyncio.CancelledError):
        raise click.exceptions.Exit(130) from None


@click.group(context_settings={"help_option_names": ["-h", "--help"]})
@click.option(
    "--config",
    "-c",
    default="/etc/svc/services.json",
    show_default=True,
    help="Path to services JSON config",
)
@click.option("--verbose", "-v", is_flag=True, help="Enable verbose output")
@click.option("--dry-run", "-n", is_flag=True, help="Show actions without executing")
@click.pass_context
def cli(ctx: click.Context, config: str, verbose: bool, dry_run: bool) -> None:
    """Manage backup and restore operations for homeserver services."""
    ctx.obj = GlobalOptions(config=config, verbose=verbose, dry_run=dry_run)


@cli.command("list")
@click.option(
    "--backup-env",
    type=click.Choice(["local", "remote"], case_sensitive=False),
    default="local",
    show_default=True,
    help="Which systemd backup unit to check for last result",
)
@click.pass_context
def list_cmd(ctx: click.Context, backup_env: str) -> None:
    """List services and their backup status."""
    _run_command(ctx, ListCommand(), ListArgs(backup_env=backup_env))


@cli.command("list-backups")
@click.argument("env", type=click.Choice(["local", "remote"], case_sensitive=False))
@click.argument("service", type=ServiceNameParam(backup_only=True, allow_all=False))
@click.pass_context
def list_backups_cmd(ctx: click.Context, env: str, service: str) -> None:
    """List restic snapshots for a service."""
    _run_command(ctx, ListBackupsCommand(), ListBackupsArgs(env=env, service=service))


@cli.command("backup")
@click.argument("env", type=click.Choice(["local", "remote"], case_sensitive=False))
@click.argument("service", type=ServiceNameParam(backup_only=True, allow_all=True))
@click.pass_context
def backup_cmd(ctx: click.Context, env: str, service: str) -> None:
    """Run backups"""
    _run_command(ctx, BackupCommand(), BackupArgs(env=env, service=service))


@cli.command("restore")
@click.argument("env", type=click.Choice(["local", "remote"], case_sensitive=False))
@click.argument("service", type=ServiceNameParam(backup_only=True, allow_all=False))
@click.argument("snapshot", required=False, default="latest")
@click.option(
    "--verify-includes",
    is_flag=True,
    help="Check snapshot contains each configured path/PVC before restoring",
)
@click.pass_context
def restore_cmd(
    ctx: click.Context,
    env: str,
    service: str,
    snapshot: str,
    verify_includes: bool,
) -> None:
    """Restore a service from a snapshot (default: `latest`)."""
    _run_command(
        ctx,
        RestoreCommand(),
        RestoreArgs(
            env=env,
            service=service,
            snapshot=snapshot,
            verify_includes=verify_includes,
        ),
    )
