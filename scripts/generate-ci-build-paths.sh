#!/bin/bash
set -e;


SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"
SKAFFOLD_ROOT_DIR="$SCRIPT_DIR/.."

source "$SKAFFOLD_ROOT_DIR/scripts/common-env.sh";

SKAFFOLD_PATHS=$(find "$GENERATED_SKAFFOLD_DIR" -mindepth 1  -maxdepth 1 -type d -exec basename {} \;);

SKAFFOLD_PATHS_ONE_LINE=$(echo "$SKAFFOLD_PATHS" | jq -Rc -s 'split("\n")[:-1]');

echo "skaffold_names=$SKAFFOLD_PATHS_ONE_LINE";
