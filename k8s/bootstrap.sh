#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

wait_for_crd() {
  local crd="$1"
  local timeout_seconds="${2:-180}"
  local elapsed=0

  until kubectl get "crd/${crd}" >/dev/null 2>&1; do
    if [ "$elapsed" -ge "$timeout_seconds" ]; then
      echo "Timed out waiting for CRD ${crd}" >&2
      return 1
    fi

    sleep 2
    elapsed=$((elapsed + 2))
  done
}

kubectl get nodes

kubectl apply -f persistentVolume/

kubectl apply -f dns/
kubectl -n kube-system rollout restart deployment/coredns

kubectl apply -f vault/operator/

wait_for_crd vaultconnections.secrets.hashicorp.com
wait_for_crd vaultauthglobals.secrets.hashicorp.com

kubectl wait --for=condition=Established \
  crd/vaultconnections.secrets.hashicorp.com \
  --timeout=180s
kubectl wait --for=condition=Established \
  crd/vaultauthglobals.secrets.hashicorp.com \
  --timeout=180s

kubectl apply -f vault/global/
kubectl apply -f image-refresh/

echo "Base k3s resources are applied."
