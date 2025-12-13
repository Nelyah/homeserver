#!/usr/bin/env python3
"""
svc - Service backup and restore CLI tool

Commands:
  svc backup <local|remote> <service|all>
  svc restore <local|remote> <service> [latest|SNAPSHOT_ID]
  svc list
  svc list-backups <local|remote> <service>
  svc start <service|all>
  svc stop <service|all>
  svc restart <service|all>
  svc logs <service> [--no-follow] [--tail N] [--timestamps]
"""

import logging
import sys

import click

from svc.cli import cli
from svc.exceptions import EXIT_CONFIG_ERROR, EXIT_USAGE_ERROR, SvcError


def setup_logging(verbose: bool) -> None:
    """Configure logging based on verbosity."""
    level = logging.DEBUG if verbose else logging.INFO

    try:
        from rich.logging import RichHandler

        if sys.stderr.isatty():
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
    except ImportError:
        pass

    fmt = (
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
        if verbose
        else "%(levelname)s: %(message)s"
    )
    logging.basicConfig(level=level, format=fmt, datefmt="%Y-%m-%d %H:%M:%S")


def reorder_global_options(argv: list[str]) -> list[str]:
    """Move global options (-c/-v/-n) before the subcommand.

    Argparse allowed these flags anywhere; click does not, so we normalize argv
    to keep the same CLI affordances.
    """
    globals_: list[str] = []
    rest: list[str] = []

    i = 0
    while i < len(argv):
        arg = argv[i]

        if arg in {"-v", "--verbose", "-n", "--dry-run"}:
            globals_.append(arg)
            i += 1
            continue

        if arg in {"-c", "--config"}:
            globals_.append(arg)
            if i + 1 < len(argv):
                globals_.append(argv[i + 1])
                i += 2
            else:
                i += 1
            continue

        if arg.startswith("--config="):
            globals_.append(arg)
            i += 1
            continue

        rest.append(arg)
        i += 1

    return globals_ + rest


def main() -> int:
    """Main entry point."""
    try:
        argv = reorder_global_options(sys.argv[1:])

        # Parse just the global flags for logging setup.
        # (click will parse them again, but it doesn't hurt.)
        verbose = ("-v" in argv) or ("--verbose" in argv)
        setup_logging(verbose)

        cli.main(args=argv, prog_name="svc", standalone_mode=False)
        return 0
    except click.exceptions.Exit as e:
        return int(getattr(e, "exit_code", 0))
    except click.exceptions.Abort:
        logging.info("Interrupted by user")
        return 130
    except click.ClickException as e:
        e.show()
        return EXIT_USAGE_ERROR
    except SvcError as e:
        logging.error(str(e))
        return e.exit_code
    except KeyboardInterrupt:
        logging.info("Interrupted by user")
        return 130
    except Exception as e:
        logging.exception(f"Unexpected error: {e}")
        return EXIT_CONFIG_ERROR


if __name__ == "__main__":
    sys.exit(main())
