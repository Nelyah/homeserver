#!/usr/bin/env python3
"""
svc - Service backup and restore CLI tool

Commands:
  svc backup <local|remote> <service|all>
  svc logs <local|remote>
  svc restore <local|remote> <service> [latest|SNAPSHOT_ID]
  svc list
  svc list-backups <local|remote> <service>
"""

import logging
import sys

import click

from svc.cli import cli
from svc.exceptions import EXIT_CONFIG_ERROR, EXIT_USAGE_ERROR, SvcError

logger = logging.getLogger("svc")


def main() -> int:
    """Main entry point."""
    try:
        cli.main(args=sys.argv[1:], prog_name="svc", standalone_mode=False)
    except click.exceptions.Exit as e:
        return int(getattr(e, "exit_code", 0))
    except (click.exceptions.Abort, KeyboardInterrupt):
        logger.info("Interrupted by user")
        return 130
    except click.ClickException as e:
        e.show()
        return EXIT_USAGE_ERROR
    except SvcError as e:
        logger.error("%s", e)
        return e.exit_code
    except Exception:
        logger.exception("Unexpected error")
        return EXIT_CONFIG_ERROR
    else:
        return 0


if __name__ == "__main__":
    sys.exit(main())
