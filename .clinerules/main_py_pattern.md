# Main.py Pattern

When creating or modifying `main.py` files in environment directories, follow these conventions:

## Required Structure

1. **Setup**: Set config path, add repo root to Python path
2. **Imports**: Use absolute imports from components
3. **Generation Function**: Implement `generate_all_skaffolds()`
4. **Component Creation**: Create in dependency order
5. **Configuration**: Load from `secrets/config_env.yaml`

## Example Pattern

```python
import os
import shutil
import subprocess
import sys
import yaml
from components.whatsapp_waha.main import create_whatsapp_waha

# Set config path before imports
current_dir = os.path.dirname(os.path.abspath(__file__))
config_path = os.path.join(current_dir, 'secrets/config_env.yaml')
os.environ['CONFIG_YAML_PATH'] = config_path

# Add the repository root to the Python path to enable absolute imports
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)

# Use absolute imports
from components.base.constants import (
    GENERATED_SKAFFOLD_TMP_DIR,
    GENERATED_SKAFFOLD_DIR,
    INTELLIJ_RUN_CONFIGURATIONS_ENABLED,
)
from components.base.generate_skaffolds import generate_skaffolds
from components.namespace.main import create_namespace
from components.cert_manager_issuer.main import create_cert_manager_issuer
from components.cert_manager_certificate.main import create_cert_manager_certificate
from components.intellij_skaffolds_run_configurations.main import generate_intelij_skaffolds_run_configurations


# ===== MAIN GENERATION FUNCTION =====

def generate_all_skaffolds():
    """Generate all configurations for the environment"""
    # Clean up and create temporary directory
    shutil.rmtree(f"{GENERATED_SKAFFOLD_TMP_DIR}", ignore_errors=True)
    os.makedirs(f'{GENERATED_SKAFFOLD_TMP_DIR}', exist_ok=True)

    # Create an empty .gitkeep file
    with open(f'{GENERATED_SKAFFOLD_TMP_DIR}/.gitkeep', 'w') as f:
        f.write("")

    # Load secrets
    # Load configuration from YAML
    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)
    env_vars = config.get('env', {})

    # Create components in dependency order
    # ...

    # Generate skaffold configurations
    generate_skaffolds(components)

    # Generate IntelliJ run configurations if enabled
    if INTELLIJ_RUN_CONFIGURATIONS_ENABLED or env_vars['INTELLIJ_RUN_CONFIGURATIONS_ENABLED'].lower() == 'true':
        generate_intelij_skaffolds_run_configurations()

    # Sync generated files to the final directory
    subprocess.call(["rsync", "-rcvu", "--delete", f"{GENERATED_SKAFFOLD_TMP_DIR}/", f"{GENERATED_SKAFFOLD_DIR}/"])
    subprocess.call(["rm", "-rf", f"{GENERATED_SKAFFOLD_TMP_DIR}/"])


if __name__ == '__main__':
    generate_all_skaffolds()
