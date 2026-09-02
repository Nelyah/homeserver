"""Direct Restic command passthrough."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated

import typer

from ...config import load_restic_env
from ..args import BackupEnvironment  # noqa: TC001 - Typer resolves annotations at runtime
from ..runtime import run_command
from .base import AppContext, Command


@dataclass(frozen=True)
class ResticArgs:
    """Arguments for `svc restic`."""

    env: str
    command: tuple[str, ...]


class ResticCommand(Command[ResticArgs]):
    """Run an arbitrary Restic command against a configured repository."""

    async def execute(self, args: ResticArgs, ctx: AppContext) -> int:
        """Load the selected repository environment and invoke Restic."""
        env_vars = load_restic_env(ctx.config.paths.secrets_root, args.env)
        restic = ctx.create_restic_runner(env_vars)
        return await restic.run(list(args.command))


def restic_cli(
    ctx: typer.Context,
    env: Annotated[
        BackupEnvironment,
        typer.Argument(case_sensitive=False),
    ],
) -> None:
    """Run Restic directly against a configured repository."""
    if not ctx.args:
        typer.echo("Error: Missing Restic command.", err=True)
        raise typer.Exit(code=2)
    run_command(ctx, ResticCommand(), ResticArgs(env=env.value, command=tuple(ctx.args)))


def register_restic_command(app: typer.Typer) -> None:
    """Register the Restic passthrough while keeping its parsing policy local."""
    app.command(
        "restic",
        context_settings={
            "allow_extra_args": True,
            "allow_interspersed_args": False,
            "ignore_unknown_options": True,
        },
    )(restic_cli)
