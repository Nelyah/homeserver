#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

docker_image_id() {
  docker image inspect -f '{{.Id}}' "$1" 2>/dev/null || true
}

restart_deployments_using_image() {
  local image="$1"
  local deployments
  local restarted=0

  if ! deployments="$(kubectl get deployments --all-namespaces \
    -o jsonpath='{range .items[*]}{.metadata.namespace}{" "}{.metadata.name}{" "}{range .spec.template.spec.initContainers[*]}{.image}{" "}{end}{range .spec.template.spec.containers[*]}{.image}{" "}{end}{"\n"}{end}' 2>/dev/null)"; then
    echo "Skipping rollout restarts for ${image}; Kubernetes API is not reachable."
    return
  fi

  while read -r namespace deployment images; do
    [ -n "${namespace:-}" ] || continue
    [ -n "${deployment:-}" ] || continue

    for deployment_image in $images; do
      if [ "$deployment_image" = "$image" ]; then
        echo "Restarting ${namespace}/${deployment}; it uses rebuilt ${image}"
        kubectl -n "$namespace" rollout restart "deployment/${deployment}"
        restarted=1
        break
      fi
    done
  done <<< "$deployments"

  if [ "$restarted" -eq 0 ]; then
    echo "No Deployments currently reference ${image}."
  fi
}

build_and_import() {
  local image="$1"
  local context="$2"
  local archive
  local old_id
  local new_id

  archive="$(mktemp --tmpdir "k3s-image-${image//[\/:]/-}.XXXXXX.tar")"
  old_id="$(docker_image_id "$image")"

  echo "Building ${image} from ${context}"
  docker build --pull -t "$image" "$context"
  new_id="$(docker_image_id "$image")"

  echo "Saving ${image} to ${archive}"
  docker save "$image" -o "$archive"

  echo "Importing ${image} into k3s containerd"
  sudo k3s ctr images import "$archive"

  rm -f "$archive"

  if [ "$old_id" != "$new_id" ]; then
    restart_deployments_using_image "$image"
  else
    echo "${image} did not change; skipping rollout restarts."
  fi
}

while IFS= read -r dockerfile; do
  context="$(dirname "$dockerfile")"
  service="$(basename "$context")"
  build_and_import "homeserver/${service}:latest" "$context"
done < <(find k8s -mindepth 2 -maxdepth 2 -name Dockerfile -print | sort)

echo "Local images are built and imported into k3s."
