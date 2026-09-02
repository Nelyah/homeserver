"""Shared Typer command execution helpers."""

from __future__ import annotations

import asyncio
import logging
import signal
import sys
from dataclasses import dataclass
from typing import TypeVar

import typer

from ..config import load_config
from .commands.base import AppContext, Command
from .renderer import create_renderer

TArgs = TypeVar("TArgs")

try:
    from rich.logging import RichHandler
except ImportError:  # pragma: no cover
    RichHandler = None  # type: ignore[assignment]


@dataclass(frozen=True)
class GlobalOptions:
    """Global options parsed by Typer."""

    config: str
    verbose: bool
    dry_run: bool


def setup_logging(*, verbose: bool) -> None:
    """Configure logging based on verbosity."""
    level = logging.DEBUG if verbose else logging.INFO

    if RichHandler is not None and sys.stderr.isatty():
        logging.basicConfig(
            level=level,
            format="%(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
            handlers=[
                RichHandler(
                    rich_tracebacks=verbose,
                    show_time=verbose,
                    show_level=True,
                    show_path=False,
                )
            ],
        )
        return

    fmt = (
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
        if verbose
        else "%(levelname)s: %(message)s"
    )
    logging.basicConfig(level=level, format=fmt, datefmt="%Y-%m-%d %H:%M:%S")


def _get_app_ctx(ctx: typer.Context) -> AppContext:
    """Create the application context from global Typer options."""
    options = ctx.ensure_object(GlobalOptions)
    config = load_config(options.config)
    renderer = create_renderer()
    return AppContext(
        config=config,
        renderer=renderer,
        dry_run=options.dry_run,
        verbose=options.verbose,
    )


async def _execute_command(command: Command[TArgs], args: TArgs, app_ctx: AppContext) -> int:
    """Execute a command while translating SIGTERM into graceful cancellation."""
    loop = asyncio.get_running_loop()
    task = asyncio.current_task()
    signal_handler_installed = False

    if task is not None:

        def cancel_command() -> None:
            if task.cancelling() == 0:
                task.cancel()

        try:
            loop.add_signal_handler(signal.SIGTERM, cancel_command)
            signal_handler_installed = True
        except NotImplementedError:  # pragma: no cover - Unix-only production path
            pass

    try:
        return await command.execute(args, app_ctx)
    finally:
        if signal_handler_installed:
            loop.remove_signal_handler(signal.SIGTERM)


def run_command(ctx: typer.Context, command: Command[TArgs], args: TArgs) -> None:
    """Run a command object using an isolated asyncio event loop."""
    app_ctx = _get_app_ctx(ctx)
    try:
        exit_code = asyncio.run(_execute_command(command, args, app_ctx))
        raise typer.Exit(code=exit_code)
    except (KeyboardInterrupt, asyncio.CancelledError):
        raise typer.Exit(code=130) from None
