#! /bin/bash

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"
SKAFFOLD_ROOT_DIR="$SCRIPT_DIR/.."

source "$SKAFFOLD_ROOT_DIR/scripts/common-env.sh";

SOCKET=/tmp/docker.remote.sock
CONTEXT_NAME="remote"

# Cleanup proxy'ed socket
function onexit() {
  echo "Deleting old socket ..."
  rm -f $SOCKET;
  docker context use default;
  docker context rm -f $CONTEXT_NAME;
}
docker context use default

# Cleanup when Ctrl-C is pressed
trap onexit EXIT
# Delete old socket file if it exists
if [ -f "$SOCKET" ]; then
  onexit
fi

echo "Proxying docker on '$SOCKET' ..."
# Forward remote docker socket to your host
ssh -nNT -L $SOCKET:/var/run/docker.sock $REMOTE_DOCKER_HOST &
SSH_PID=$!

docker context rm -f $CONTEXT_NAME
docker context create $CONTEXT_NAME --docker host=unix://$SOCKET
#docker context use $CONTEXT_NAME

wait $SSH_PID

