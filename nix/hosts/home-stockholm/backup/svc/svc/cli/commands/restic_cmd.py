"""Direct Restic command passthrough."""

from dataclasses import dataclass

import click

from ...config import load_restic_env
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


@click.command(
    "restic",
    context_settings={
        "allow_extra_args": True,
        "allow_interspersed_args": False,
        "ignore_unknown_options": True,
    },
)
@click.argument("env", type=click.Choice(["local", "remote"], case_sensitive=False))
@click.pass_context
def restic_cli(ctx: click.Context, env: str) -> None:
    """Run Restic directly against a configured repository."""
    if not ctx.args:
        message = "Missing Restic command."
        raise click.UsageError(message, ctx)
    run_command(ctx, ResticCommand(), ResticArgs(env=env, command=tuple(ctx.args)))
