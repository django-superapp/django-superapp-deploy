#!/bin/bash
set -e;

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"
SKAFFOLD_ROOT_DIR="$SCRIPT_DIR/.."

source "$SKAFFOLD_ROOT_DIR/scripts/common-env.sh";

bash "$SKAFFOLD_ROOT_DIR/scripts/generate-skaffolds.sh";

cd "$GENERATED_SKAFFOLD_DIR";
if [ -n "$REMOTE_DOCKER_HOST" ]; then
  export DOCKER_CONTEXT=remote;
fi
skaffold build --filename skaffold--main--all.yaml --default-repo "$REGISTRY_URL" --verbosity info

