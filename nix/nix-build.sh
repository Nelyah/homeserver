#!/usr/bin/env bash
set -euo pipefail

if [ $# -gt 1 ]; then
  echo "Usage: $0 [hostname]" >&2
  exit 1
fi

host="${1:-$(hostname)}"
platform="$(uname -s)"

if [ "$platform" = "Darwin" ]; then
  cmd=(sudo -H nix run nix-darwin -- switch --flake ".#${host}")
else
  cmd=(sudo nixos-rebuild switch --flake ".#${host}")
fi

echo "Running: ${cmd[*]}" >&2
exec "${cmd[@]}"
