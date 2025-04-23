#!/bin/bash
set -e;

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"
SKAFFOLD_ROOT_DIR="$SCRIPT_DIR/.."

source "$SKAFFOLD_ROOT_DIR/scripts/common-env.sh";

$SKAFFOLD_ROOT_DIR/scripts/build-all-docker-images.sh;

$SKAFFOLD_ROOT_DIR/scripts/generate-manifests.sh;

echo "The deployment is ready"