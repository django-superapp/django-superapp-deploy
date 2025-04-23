#!/bin/bash
set -e;

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"
SKAFFOLD_ROOT_DIR="$SCRIPT_DIR/.."

source "$SKAFFOLD_ROOT_DIR/scripts/common-env.sh";

bash "$SKAFFOLD_ROOT_DIR/scripts/generate-manifests.sh";

cd "$GENERATED_MANIFESTS_DIR";
for f in $(find . -type f -name '*.yml'| grep 'namespace'); do
  echo "Applying $f";
  kubectl apply --server-side --force-conflicts -f "$f" || true;
  echo "$f applied";
done
for f in $(find . -type f -name '*.yml'| grep -vE 'fleet|skaffold' | grep 'common'); do
  echo "Applying $f";
  kubectl apply --server-side --force-conflicts -f "$f" || true;
  echo "$f applied";
done
for f in $(find . -type f -name '*.yml'| grep -vE 'fleet|skaffold|common'); do
  echo "Applying $f";
  kubectl apply --server-side --force-conflicts -f "$f";
  echo "$f applied";
done
