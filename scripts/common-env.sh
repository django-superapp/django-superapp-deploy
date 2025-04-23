#!/usr/bin/env bash

set -e;

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"
export SKAFFOLD_ROOT_DIR=$(realpath "$SCRIPT_DIR/..")

# Detect environment from the current directory or use default
CURRENT_ENV=$(basename $(find "$SKAFFOLD_ROOT_DIR/environments" -type d -mindepth 1 -maxdepth 1 | head -1))

# Use the components/base/constants.py file with proper path handling
env_variables="$(python3 -c "
import sys, os
# Add the repository root to sys.path
sys.path.insert(0, os.path.abspath('$SKAFFOLD_ROOT_DIR'))
# Set the config path environment variable
os.environ['CONFIG_YAML_PATH'] = os.path.abspath('$SKAFFOLD_ROOT_DIR/environments/$CURRENT_ENV/secrets/config_env.yaml')
# Import constants directly from the module
from components.base.constants import *
# Export all uppercase variables
for key, value in locals().copy().items():
    if key.isupper():
        print(f'export {key}=\"{value}\"')
")";
eval "$env_variables";
