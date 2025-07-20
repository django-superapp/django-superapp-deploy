#! /bin/bash

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"
SKAFFOLD_ROOT_DIR="$SCRIPT_DIR/.."

source "$SKAFFOLD_ROOT_DIR/scripts/common-env.sh";

bash "$SKAFFOLD_ROOT_DIR/scripts/generate-skaffolds.sh";

#if [[ "${path}" == *"*"* ]]; then
#	echo "Deploying skaffold files concurrently: ${path}";
#	find ${path} -type f | parallel --tag --jobs 5 --halt soon,fail=1 'make deploy-skaffold path={} kubeconfig=${kubeconfig}';
#    exit 0;
#fi;
#echo "Deploying skaffold file: ${path}";
#cd "$(dirname $path)" || exit;

skaffold run \
  --force=false  \
  --cleanup=false  \
  --port-forward=false \
  --wait-for-deletions-max=2m0s \
  --status-check=true \
  --verbosity info \
	--digest-source='remote' \
	--port-forward=off \
	--kubeconfig "$KUBECONFIG" -f "$GENERATED_SKAFFOLD_DIR/skaffold--main--all.yaml";

