#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")"

export KUBECONFIG="${KUBECONFIG:-$HOME/.kube/config}"
vault_token_file="${VAULT_TOKEN_FILE:-/var/lib/secrets/vault/access-token}"

./bootstrap.sh
./build-local-images.sh
helmfile --file helmfile.yaml --selector name=vault sync
if [ "$(id -u)" -eq 0 ] || [ -n "${VAULT_TOKEN:-}" ] || [ -r "$vault_token_file" ]; then
  ./configure-vault-k8s-auth.py --kubeconfig "$KUBECONFIG"
else
  sudo_env=(
    "PATH=$PATH"
    "KUBECONFIG=$KUBECONFIG"
    "VAULT_TOKEN_FILE=$vault_token_file"
  )
  if [ -n "${VAULT_ADDR:-}" ]; then
    sudo_env+=("VAULT_ADDR=$VAULT_ADDR")
  fi
  sudo env "${sudo_env[@]}" ./configure-vault-k8s-auth.py --kubeconfig "$KUBECONFIG"
fi
helmfile --file helmfile.yaml --selector 'name!=vault' sync
