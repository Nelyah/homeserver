#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")"

export KUBECONFIG="${KUBECONFIG:-$HOME/.kube/config}"

./bootstrap.sh
./build-local-images.sh
helmfile --file helmfile.yaml --selector name=vault sync
./configure-vault-k8s-auth.py
helmfile --file helmfile.yaml --selector 'name!=vault' sync
