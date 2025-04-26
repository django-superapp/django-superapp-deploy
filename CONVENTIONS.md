# Environment Configuration Conventions

## Directory Structure

environments/
└── [environment_name]/
├── main.py            # Main deployment configuration
├── secrets/ │   
└── config_env.yaml    # Environment configuration
└── .gitignore         # Ignore generated files


## Main.py Pattern
1. **Setup**: Set config path, add repo root to Python path
2. **Imports**: Use absolute imports from components
3. **Generation Function**: Implement `generate_all_skaffolds()`
4. **Component Creation**: Create in dependency order
5. **Configuration**: Load from `secrets/config_env.yaml`

## Example (simplified)
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
    """Generate all configurations for the production environment"""
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

    # Whatsapp WAHA
    whatsapp_waha_config = config['components']['whatsapp_waha']
    whatsapp_waha_domain_name=whatsapp_waha_config['domain_name']
    whatsapp_waha_root_domain = '.'.join(whatsapp_waha_domain_name.split('.')[1:])
    whatsapp_waha_namespace_name = "whatsapp"

    whatsapp_waha_namespace = create_namespace(
        slug=whatsapp_waha_namespace_name,
        namespace=whatsapp_waha_namespace_name,
        depends_on=[]
    )

    whatsapp_waha_cert_manager_issuer = create_cert_manager_issuer(
        slug="whatsapp-waha-issuer",
        namespace=whatsapp_waha_namespace_name,
        cloudflare_email=env_vars['CLOUDFLARE_EMAIL'],
        cloudflare_api_token=env_vars['CLOUDFLARE_API_TOKEN'],
        depends_on=[
            whatsapp_waha_namespace
        ]
    )

    whatsapp_waha_cert_manager_certificate = create_cert_manager_certificate(
        slug="whatsapp-waha-certificate",
        namespace=whatsapp_waha_namespace_name,
        domain_name=whatsapp_waha_domain_name,
        issuer_secret_name=whatsapp_waha_cert_manager_issuer.issuer_secret_name,
        certificate_dns_names=[
            whatsapp_waha_root_domain,
            f"*.{whatsapp_waha_root_domain}",
        ],
        depends_on=[
            whatsapp_waha_namespace,
            whatsapp_waha_cert_manager_issuer,
        ]
    )
    whatsapp_waha = create_whatsapp_waha(
        slug="whatsapp",
        namespace=whatsapp_waha_namespace_name,
        image_repository="devlikeapro/waha",
        image_tag="latest",
        replicas=1,
        env_vars={},
        ingress_enabled=True,
        ingress_host=whatsapp_waha_domain_name,
        ingress_class_name="nginx",
        ingress_tls_secret=whatsapp_waha_cert_manager_certificate.certificate_secret_name,
        basic_auth_enabled=True,
        username=whatsapp_waha_config['username'],
        password=whatsapp_waha_config['password'],
        depends_on=[
            whatsapp_waha_namespace,
            whatsapp_waha_cert_manager_certificate,
            whatsapp_waha_cert_manager_issuer,
        ]
    )

    # Collect all components
    components = [
        # WhatsApp WAHA
        whatsapp_waha_namespace,
        whatsapp_waha_cert_manager_issuer,
        whatsapp_waha_cert_manager_certificate,
        whatsapp_waha,
    ]

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
                                                                                                                                                                                               
```                                                                                                                                                                                           


Best Practices

• Specify dependencies explicitly with depends_on                                                                                                                                                                         
• Create components in logical order (infrastructure → services)                                                                                                                                                          
• Keep sensitive information in secrets directory                                                                                                                                                                         
• Use absolute imports for components  
• when passing variables to create_XXX_XXX functions, pass directly from XXX_config.get('key')

