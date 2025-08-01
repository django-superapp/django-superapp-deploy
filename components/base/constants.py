import glob
import os
import sys
import yaml

CONSTANTS_FILE_ABOSLUTE_PATH = os.path.dirname(__file__)

# Get CONFIG_YAML_PATH from environment or detect it
if 'CONFIG_YAML_PATH' in os.environ:
    CONFIG_YAML_PATH = os.path.abspath(os.environ['CONFIG_YAML_PATH'])
else:
    # Try to detect the environment from the script path
    script_path = sys.argv[0] if len(sys.argv) > 0 else ''
    env_match = None

    # Check if running from an environment directory
    if 'environments' in script_path:
        for env_dir in glob.glob(os.path.join(CONSTANTS_FILE_ABOSLUTE_PATH, "../environments/*/secrets")):
            env_name = os.path.basename(os.path.dirname(env_dir))
            if env_name in script_path:
                env_match = env_name
                break

    # If environment detected from path, use it
    if env_match:
        CONFIG_YAML_PATH = os.path.abspath(
            os.path.join(CONSTANTS_FILE_ABOSLUTE_PATH, f"../environments/{env_match}/secrets/config_env.yaml")
        )
    else:
        # Find the first available environment as default
        env_dirs = glob.glob(os.path.join(CONSTANTS_FILE_ABOSLUTE_PATH, "../environments/*/secrets"))
        if env_dirs:
            default_env = os.path.basename(os.path.dirname(env_dirs[0]))
            CONFIG_YAML_PATH = os.path.abspath(
                os.path.join(CONSTANTS_FILE_ABOSLUTE_PATH, f"../environments/{default_env}/secrets/config_env.yaml")
            )
        else:
            # Fallback to a default path
            CONFIG_YAML_PATH = os.path.abspath(
                os.path.join(CONSTANTS_FILE_ABOSLUTE_PATH, "../environments/production/secrets/config_env.yaml")
            )

MAKEFILE_PATH = os.environ.get('MAKEFILE_PATH', os.path.join(CONSTANTS_FILE_ABOSLUTE_PATH, "../Makefile"))
CONFIG_YAML_DIR = os.path.dirname(os.path.abspath(CONFIG_YAML_PATH))

# Read the YAML file
with open(CONFIG_YAML_PATH, "r") as file:
    CONFIG = yaml.load(file, Loader=yaml.FullLoader)

ABSOLUTE_PATH_ENV_VARIABLES = [
    'REPO_ROOT',
    'KUBECONFIG',
    'CHARTS_PATH',
    'KUBESEAL_CERTIFICATE_PATH',
    'GENERATED_SKAFFOLD_DIR',
    'GENERATED_MANIFESTS_DIR',
    'GENERATED_SKAFFOLD_TMP_DIR',
]

# Extract the environment variables and set them

if "env" in CONFIG:
    env_vars = CONFIG["env"]
    for key, value in env_vars.items():
        if os.environ.get(key) is None or True:
            if key in ABSOLUTE_PATH_ENV_VARIABLES and value:
                os.environ[key] = os.path.abspath(os.path.join(CONFIG_YAML_DIR, value))
                CONFIG["env"][key] = os.environ[key]
            else:
                os.environ[key] = str(value)

REPO_ROOT = os.environ['REPO_ROOT']
if 'KUBECONFIG' in os.environ:
    KUBECONFIG = os.environ['KUBECONFIG']

if 'KUBESEAL_CERT' in os.environ:
    KUBESEAL_CERT = os.environ['KUBESEAL_CERT']

INTELLIJ_RUN_CONFIGURATIONS_PREFIX = os.environ.get('INTELLIJ_RUN_CONFIGURATIONS_PREFIX', '')
INTELLIJ_RUN_CONFIGURATIONS_ENABLED = os.environ.get('INTELLIJ_RUN_CONFIGURATIONS_ENABLED', 'false') == 'true'

# Generated directories
GENERATED_SKAFFOLD_DIR = os.environ['GENERATED_SKAFFOLD_DIR']
GENERATED_MANIFESTS_DIR = os.environ['GENERATED_MANIFESTS_DIR']
GENERATED_SKAFFOLD_TMP_DIR = os.environ['GENERATED_SKAFFOLD_TMP_DIR']

IMAGES_TAG = os.environ.get('IMAGES_TAG', 'latest')

# Skaffold
REMOTE_DOCKER_HOST = str(os.environ.get('REMOTE_DOCKER_HOST', '')).lower()

# All constants defined in this file will be exported as ENV variables in bash scripts by ./utils/common-env.sh
# Exporting all variables as env variables
if __name__ == '__main__':
    export_variables_bash_script = ""
    # for key, value in os.environ.items():
    #     export_variables_bash_script += f'export {key}="{value}"\n'
    for key, value in locals().copy().items():
        if key.isupper():
            export_variables_bash_script += f'export {key}="{value}"\n'

    print(export_variables_bash_script)
