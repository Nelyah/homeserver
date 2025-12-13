"""Click-based CLI for svc.

This replaces the previous argparse+argcomplete implementation while keeping the
same commands/options and dynamic completion of service names.
"""

from __future__ import annotations

import argparse
import asyncio
import json
from dataclasses import dataclass
from typing import Any, cast

import click

from ..config import load_config
from .commands import (
    BackupCommand,
    DockerHealthCommand,
    ListBackupsCommand,
    ListCommand,
    LogsCommand,
    PruneImagesCommand,
    PruneOrphansCommand,
    RestartCommand,
    RestoreCommand,
    StartCommand,
    StopCommand,
)
from .commands.base import AppContext
from .commands.base import Command
from .renderer import create_renderer

from click.shell_completion import CompletionItem


@dataclass(frozen=True)
class GlobalOptions:
    config: str
    verbose: bool
    dry_run: bool


def _load_services_for_completion(
    config_path: str, *, backup_only: bool
) -> list[str]:
    try:
        with open(config_path) as f:
            raw: Any = json.load(f)
    except Exception:
        return []

    if not isinstance(raw, dict):
        return []

    data = cast(dict[str, Any], raw)
    raw_services: Any = data.get("services") or {}
    if not isinstance(raw_services, dict):
        return []

    services_obj = cast(dict[str, Any], raw_services)

    if not backup_only:
        return list(services_obj.keys())

    services: list[str] = []
    for name, spec in services_obj.items():
        if not isinstance(spec, dict):
            continue
        spec_dict = cast(dict[str, Any], spec)
        backup_obj = spec_dict.get("backup")
        if not isinstance(backup_obj, dict):
            continue
        backup = cast(dict[str, Any], backup_obj)
        if bool(backup.get("enable", False)):
            services.append(name)
    return services


class ServiceNameParam(click.ParamType):
    name = "service"

    def __init__(self, *, backup_only: bool, allow_all: bool):
        super().__init__()
        self._backup_only = backup_only
        self._allow_all = allow_all

    def shell_complete(
        self, ctx: click.Context, param: click.Parameter, incomplete: str
    ) -> list[CompletionItem]:
        params = ctx.find_root().params or {}
        config_param = params.get("config")
        config_path = (
            config_param if isinstance(config_param, str) else "/etc/svc/services.json"
        )
        services = _load_services_for_completion(
            config_path, backup_only=self._backup_only
        )
        if self._allow_all:
            services.append("all")
        matches = sorted({s for s in services if s.startswith(incomplete)})
        return [CompletionItem(m) for m in matches]


def _get_app_ctx(ctx: click.Context) -> AppContext:
    options: GlobalOptions = ctx.ensure_object(GlobalOptions)  # type: ignore[assignment]
    config = load_config(options.config)
    renderer = create_renderer()
    return AppContext(
        config=config,
        renderer=renderer,
        dry_run=options.dry_run,
        verbose=options.verbose,
    )


def _run_command(ctx: click.Context, command: Command, args: argparse.Namespace) -> None:
    app_ctx = _get_app_ctx(ctx)
    try:
        exit_code: int = asyncio.run(command.execute(args, app_ctx))
        raise click.exceptions.Exit(exit_code)
    except (KeyboardInterrupt, asyncio.CancelledError):
        raise click.exceptions.Exit(130)


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
    args = argparse.Namespace(backup_env=backup_env)
    _run_command(ctx, ListCommand(), args)


@cli.command("list-backups")
@click.argument("env", type=click.Choice(["local", "remote"], case_sensitive=False))
@click.argument("service", type=ServiceNameParam(backup_only=True, allow_all=False))
@click.pass_context
def list_backups_cmd(ctx: click.Context, env: str, service: str) -> None:
    """List restic snapshots for a service."""
    args = argparse.Namespace(env=env, service=service)
    _run_command(ctx, ListBackupsCommand(), args)


@cli.command("backup")
@click.argument("env", type=click.Choice(["local", "remote"], case_sensitive=False))
@click.argument("service", type=ServiceNameParam(backup_only=True, allow_all=True))
@click.pass_context
def backup_cmd(ctx: click.Context, env: str, service: str) -> None:
    """Run backups"""
    args = argparse.Namespace(env=env, service=service)
    _run_command(ctx, BackupCommand(), args)


@cli.command("restore")
@click.argument("env", type=click.Choice(["local", "remote"], case_sensitive=False))
@click.argument("service", type=ServiceNameParam(backup_only=True, allow_all=False))
@click.argument("snapshot", required=False, default="latest")
@click.option(
    "--verify-includes",
    is_flag=True,
    help="Check snapshot contains each configured volume/path before restoring",
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
    args = argparse.Namespace(
        env=env,
        service=service,
        snapshot=snapshot,
        verify_includes=verify_includes,
    )
    _run_command(ctx, RestoreCommand(), args)


@cli.command("start")
@click.argument("service", type=ServiceNameParam(backup_only=False, allow_all=True))
@click.pass_context
def start_cmd(ctx: click.Context, service: str) -> None:
    """Start a docker-compose services."""
    args = argparse.Namespace(service=service)
    _run_command(ctx, StartCommand(), args)


@cli.command("stop")
@click.argument("service", type=ServiceNameParam(backup_only=False, allow_all=True))
@click.pass_context
def stop_cmd(ctx: click.Context, service: str) -> None:
    """Stop a docker-compose services."""
    args = argparse.Namespace(service=service)
    _run_command(ctx, StopCommand(), args)


@cli.command("restart")
@click.argument("service", type=ServiceNameParam(backup_only=False, allow_all=True))
@click.option(
    "--recreate",
    is_flag=True,
    help="Perform docker compose down/up instead of systemctl restart",
)
@click.pass_context
def restart_cmd(ctx: click.Context, service: str, recreate: bool) -> None:
    """Restart a docker-compose service."""
    args = argparse.Namespace(service=service, recreate=recreate)
    _run_command(ctx, RestartCommand(), args)


@cli.command("logs")
@click.argument("service", type=ServiceNameParam(backup_only=False, allow_all=False))
@click.option(
    "--follow/--no-follow",
    default=True,
    show_default=True,
    help="Follow logs",
)
@click.option("--tail", type=int, default=200, show_default=True, help="Lines to show")
@click.option("--timestamps", is_flag=True, help="Show timestamps in log output")
@click.pass_context
def logs_cmd(
    ctx: click.Context, service: str, follow: bool, tail: int, timestamps: bool
) -> None:
    """Stream docker-compose logs for a service."""
    args = argparse.Namespace(
        service=service,
        follow=follow,
        tail=tail,
        timestamps=timestamps,
    )
    _run_command(ctx, LogsCommand(), args)


# ---------------------------------------------------------------------------
# Docker maintenance commands
# ---------------------------------------------------------------------------


@cli.group("docker")
def docker_group() -> None:
    """Docker maintenance commands."""
    pass


@docker_group.command("health")
@click.pass_context
def docker_health_cmd(ctx: click.Context) -> None:
    """Check health of deployed docker services and containers.

    Reports deployed services with no running container, containers not in
    Up/healthy state, and orphan containers (stopped, no compose label).
    """
    args = argparse.Namespace()
    _run_command(ctx, DockerHealthCommand(), args)


@docker_group.command("prune-images")
@click.pass_context
def docker_prune_images_cmd(ctx: click.Context) -> None:
    """Remove dangling Docker images (tagged <none>:<none>).

    Dangling images are created when you rebuild an image with the same tag.
    The old image loses its tag but remains on disk. These are safe to remove
    as they are not used by any container.
    """
    args = argparse.Namespace()
    _run_command(ctx, PruneImagesCommand(), args)


@docker_group.command("prune-orphans")
@click.pass_context
def docker_prune_orphans_cmd(ctx: click.Context) -> None:
    """Remove orphan containers (stopped, no compose project label).

    Orphan containers are stopped containers that have no docker-compose
    project label. They may be leftover from removed compose stacks or
    one-off test runs. Only stopped containers without labels are removed.
    """
    args = argparse.Namespace()
    _run_command(ctx, PruneOrphansCommand(), args)
