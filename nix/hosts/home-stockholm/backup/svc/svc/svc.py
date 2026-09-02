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

from svc.cli import app
from svc.exceptions import EXIT_CONFIG_ERROR, SvcError

logger = logging.getLogger("svc")


def main() -> int:
    """Main entry point."""
    try:
        app(prog_name="svc")
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
        return 130
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
