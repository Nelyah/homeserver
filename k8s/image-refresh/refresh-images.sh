#!/bin/sh
set -eu

SELECTOR='homeserver.nelyah.eu/image-refresh!=false'
EXCLUDED_NAMESPACES=' kube-system kube-public kube-node-lease image-refresh '
PLATFORM_OS="${IMAGE_REFRESH_OS:-linux}"

platform_arch() {
  case "$(uname -m)" in
    x86_64|amd64) printf '%s\n' amd64 ;;
    aarch64|arm64) printf '%s\n' arm64 ;;
    armv7l) printf '%s\n' arm ;;
    *) uname -m ;;
  esac
}

PLATFORM_ARCH="${IMAGE_REFRESH_ARCH:-$(platform_arch)}"

is_excluded_namespace() {
  case "$EXCLUDED_NAMESPACES" in
    *" $1 "*) return 0 ;;
    *) return 1 ;;
  esac
}

normalize_image() {
  image="$1"
  first_component="${image%%/*}"

  if [ "$first_component" = "$image" ]; then
    printf 'docker.io/library/%s\n' "$image"
    return
  fi

  case "$first_component" in
    *.*|*:*|localhost) printf '%s\n' "$image" ;;
    *) printf 'docker.io/%s\n' "$image" ;;
  esac
}

image_id_digest() {
  printf '%s\n' "$1" | sed -n 's/.*\(sha256:[0-9a-fA-F]\{64\}\).*/\1/p' | tail -n 1
}

remote_digest() {
  image="$(normalize_image "$1")"
  skopeo inspect \
    --override-os "$PLATFORM_OS" \
    --override-arch "$PLATFORM_ARCH" \
    --format '{{.Digest}}' \
    "docker://${image}" 2>/dev/null || true
}

deployment_pod() {
  namespace="$1"
  deployment="$2"

  kubectl -n "$namespace" get pods \
    -l "app=${deployment}" \
    --field-selector=status.phase=Running \
    -o jsonpath='{.items[0].metadata.name}' 2>/dev/null || true
}

check_deployment() {
  namespace="$1"
  deployment="$2"

  if is_excluded_namespace "$namespace"; then
    echo "Skipping excluded namespace ${namespace}/${deployment}"
    return
  fi

  pod="$(deployment_pod "$namespace" "$deployment")"
  if [ -z "$pod" ]; then
    echo "Skipping ${namespace}/${deployment}: no running pod found"
    return
  fi

  images_file="$(mktemp)"
  statuses_file="$(mktemp)"

  if ! kubectl -n "$namespace" get deployment "$deployment" \
    -o jsonpath='{range .spec.template.spec.initContainers[*]}{.name}{" "}{.image}{"\n"}{end}{range .spec.template.spec.containers[*]}{.name}{" "}{.image}{"\n"}{end}' \
    > "$images_file"; then
    echo "Skipping ${namespace}/${deployment}: deployment disappeared before it could be checked"
    rm -f "$images_file" "$statuses_file"
    return
  fi

  if ! kubectl -n "$namespace" get pod "$pod" \
    -o jsonpath='{range .status.initContainerStatuses[*]}{.name}{" "}{.imageID}{"\n"}{end}{range .status.containerStatuses[*]}{.name}{" "}{.imageID}{"\n"}{end}' \
    > "$statuses_file"; then
    echo "Skipping ${namespace}/${deployment}: pod ${pod} disappeared before it could be checked"
    rm -f "$images_file" "$statuses_file"
    return
  fi

  changed=0
  checked=0

  while read -r container image; do
    [ -n "${container:-}" ] || continue
    [ -n "${image:-}" ] || continue

    case "$image" in
      *@sha256:*)
        echo "Skipping pinned image ${namespace}/${deployment}/${container}: ${image}"
        continue
        ;;
      homeserver/*)
        echo "Skipping local image ${namespace}/${deployment}/${container}: ${image}"
        continue
        ;;
    esac

    current_image_id="$(awk -v name="$container" '$1 == name {print $2; exit}' "$statuses_file")"
    current_digest="$(image_id_digest "$current_image_id")"
    if [ -z "$current_digest" ]; then
      echo "Skipping ${namespace}/${deployment}/${container}: no running image digest found"
      continue
    fi

    latest_digest="$(remote_digest "$image")"
    if [ -z "$latest_digest" ]; then
      echo "Skipping ${namespace}/${deployment}/${container}: could not read remote digest for ${image}"
      continue
    fi

    checked=$((checked + 1))
    if [ "$latest_digest" != "$current_digest" ]; then
      echo "Changed image ${namespace}/${deployment}/${container}: ${image}"
      echo "  running: ${current_digest}"
      echo "  remote:  ${latest_digest}"
      changed=1
    fi
  done < "$images_file"

  rm -f "$images_file" "$statuses_file"

  if [ "$changed" -eq 1 ]; then
    echo "Restarting ${namespace}/${deployment}"
    kubectl -n "$namespace" rollout restart "deployment/${deployment}"
  elif [ "$checked" -eq 0 ]; then
    echo "No registry-backed mutable images checked for ${namespace}/${deployment}"
  else
    echo "No image changes for ${namespace}/${deployment}"
  fi
}

deployments_file="$(mktemp)"
kubectl get deployments --all-namespaces \
  -l "$SELECTOR" \
  -o jsonpath='{range .items[*]}{.metadata.namespace}{" "}{.metadata.name}{"\n"}{end}' \
  > "$deployments_file"

if [ ! -s "$deployments_file" ]; then
  echo "No Deployments matched selector ${SELECTOR}"
  rm -f "$deployments_file"
  exit 0
fi

while read -r namespace deployment; do
  [ -n "${namespace:-}" ] || continue
  [ -n "${deployment:-}" ] || continue
  check_deployment "$namespace" "$deployment"
done < "$deployments_file"

rm -f "$deployments_file"
