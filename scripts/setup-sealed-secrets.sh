#!/bin/bash
set -e;

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"
SKAFFOLD_ROOT_DIR="$SCRIPT_DIR/.."

source "$SKAFFOLD_ROOT_DIR/scripts/common-env.sh";

# Check if there is any file in $$KUBECONFIG
if [ -z "$KUBECONFIG" ]; then
  echo "KUBECONFIG is not set. Please set it to the path of your kubeconfig file."
  exit 1
fi

helm repo add sealed-secrets https://bitnami-labs.github.io/sealed-secrets;
helm upgrade --install --wait sealed-secrets -n kube-system --set-string fullnameOverride=sealed-secrets-controller sealed-secrets/sealed-secrets;

kubeseal --fetch-cert > /tmp/kubeseal-cert.pem;
yq ".env.KUBESEAL_CERT = \"$(cat /tmp/kubeseal-cert.pem)\"" "$CONFIG_YAML_PATH" -i
rm -f /tmp/kubeseal-cert.pem
