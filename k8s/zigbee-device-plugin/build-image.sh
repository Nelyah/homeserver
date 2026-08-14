#!/usr/bin/env bash
set -euo pipefail

plugin_dir="$(cd "$(dirname "$0")" && pwd)"

if [[ $# -ne 1 ]]; then
  echo "Usage: $0 <image-tag>" >&2
  exit 2
fi

plugin_tag="$1"
if [[ ! "$plugin_tag" =~ ^[A-Za-z0-9_][A-Za-z0-9_.-]{0,127}$ ]]; then
  echo "Invalid container image tag: $plugin_tag" >&2
  exit 2
fi

plugin_image="homeserver/zigbee-device-plugin:$plugin_tag"
plugin_archive="$(mktemp --tmpdir zigbee-device-plugin.XXXXXX.tar)"

cleanup() {
  rm -f "$plugin_archive"
}
trap cleanup EXIT

if docker info >/dev/null 2>&1; then
  docker_cmd=(docker)
else
  docker_cmd=(sudo docker)
fi

if [[ -w /run/k3s/containerd/containerd.sock ]]; then
  k3s_cmd=(k3s)
else
  k3s_cmd=(sudo k3s)
fi

if ! containerd_images="$("${k3s_cmd[@]}" ctr images list --quiet)"; then
  echo "Unable to inspect images already imported into k3s; refusing to build." >&2
  exit 1
fi

if grep -Fxq "$plugin_image" <<<"$containerd_images" ||
  grep -Fxq "docker.io/$plugin_image" <<<"$containerd_images"; then
  echo "Refusing to overwrite image already imported into k3s: $plugin_image" >&2
  echo "Choose a new tag and update values.yaml before deploying it." >&2
  exit 1
fi

"${docker_cmd[@]}" build \
  --pull \
  --file "$plugin_dir/Dockerfile.manual" \
  --tag "$plugin_image" \
  "$plugin_dir"

"${docker_cmd[@]}" save --output "$plugin_archive" "$plugin_image"
"${k3s_cmd[@]}" ctr images import "$plugin_archive"

echo "Imported immutable local image: $plugin_image"
echo "The DaemonSet uses imagePullPolicy: Never and OnDelete updates."
