#!/bin/bash
set -e;

test -d venv || virtualenv venv
touch venv/touchfile

# ——— Auto-activate virtualenv if it exists ———
if [[ -z "${VIRTUAL_ENV:-}" ]]; then
  if [[ -f "$SKAFFOLD_ROOT_DIR/venv/bin/activate" ]]; then
    # shellcheck source=/dev/null
    source "$SKAFFOLD_ROOT_DIR/venv/bin/activate"
    echo "🔋 Activated venv at $SKAFFOLD_ROOT_DIR/venv"
  elif [[ -f "$SKAFFOLD_ROOT_DIR/.venv/bin/activate" ]]; then
    # shellcheck source=/dev/null
    source "$SKAFFOLD_ROOT_DIR/.venv/bin/activate"
    echo "🔋 Activated venv at $SKAFFOLD_ROOT_DIR/.venv"
  fi
fi
