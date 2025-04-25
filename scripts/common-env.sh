#!/usr/bin/env bash

set -e;

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"
export SKAFFOLD_ROOT_DIR=$(realpath "$SCRIPT_DIR/..")

source "$SKAFFOLD_ROOT_DIR/scripts/setup-venv.sh";

# Use the components/base/constants.py file with proper path handling
env_variables="$(python3 -c "
import sys, os
# Add the repository root to sys.path
sys.path.insert(0, os.path.abspath('$SKAFFOLD_ROOT_DIR'))
# Set the config path environment variable
os.environ['CONFIG_YAML_PATH'] = './secrets/config_env.yaml'
# Import constants directly from the module
from components.base.constants import *
# Export all uppercase variables
for key, value in locals().copy().items():
    if key.isupper():
        print(f'export {key}=\"{value}\"')
")";
eval "$env_variables";
