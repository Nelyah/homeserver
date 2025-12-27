#!/bin/sh
set -euo pipefail

KEY_SOURCE="/home/app/.ssh/deploy_key"
KEY_LOCAL="/home/app/.ssh/deploy_key.local"

if [ ! -f "$KEY_SOURCE" ]; then
  echo "Missing SSH key at $KEY_SOURCE" >&2
  exit 1
fi

# Copy root-only bind mount into app-owned file (do not touch read-only mounts)
install -m 0400 -o app -g app "$KEY_SOURCE" "$KEY_LOCAL"

exec su-exec app "$@"
