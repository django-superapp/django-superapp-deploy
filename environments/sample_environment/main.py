import os
import shutil
import subprocess
import sys
import yaml
import json
import pprint
from components.whatsapp_waha.main import create_whatsapp_waha
from components.postgresql_operator.main import create_postgresql_operator_crds, create_postgresql_operator
from components.postgresql_instance.main import create_postgres_instance as create_postgres_instance_base

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
    CONFIG
)
from components.base.generate_skaffolds import generate_skaffolds
from components.cert_manager_operator.main import create_cert_manager_operator
from components.namespace.main import create_namespace
from components.cert_manager_issuer.main import create_cert_manager_issuer
from components.cert_manager_certificate.main import create_cert_manager_certificate
from components.rancher.main import create_rancher
from components.ingress_nginx.main import create_ingress_nginx
from components.longhorn.main import create_longhorn
from components.increase_fs_watchers_limit.main import create_increase_fs_watchers_limit
from components.intellij_skaffolds_run_configurations.main import generate_intelij_skaffolds_run_configurations
from components.metallb.main import create_metallb


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
    
    # Core infrastructure
    increase_fs_watchers_limit = create_increase_fs_watchers_limit(
        slug="increase-fs-watchers-limit",
        namespace="kube-system"
    )

    # Cert-manager
    cert_manager_namespace = create_namespace(
        slug="cert-manager",
        namespace="cert-manager",
        depends_on=[]
    )
    cert_manager_operator = create_cert_manager_operator(
        slug="cert-manager",
        namespace="cert-manager",
        depends_on=[
            cert_manager_namespace,
        ]
    )

    # Platform services
    # MetalLB
    metallb_namespace = create_namespace(
        slug="metallb",
        namespace="metallb-system",
        depends_on=[]
    )
    metallb = create_metallb(
        slug="metallb",
        namespace="metallb-system",
        address_pools=[
            {
                "name": "default",
                "protocol": "layer2",
                "addresses": ["10.3.0.100-10.3.255.254"]  # Adjust this range to your network
            }
        ],
        depends_on=[
            metallb_namespace,
        ]
    )
    # Ingress Nginx
    ingress_nginx_namespace = create_namespace(
        slug="ingress-nginx",
        namespace="ingress-nginx",
        depends_on=[]
    )
    ingress_nginx = create_ingress_nginx(
        slug="ingress",
        namespace="ingress-nginx",
        metallb_address_pool="default",
        depends_on=[
            ingress_nginx_namespace,
            metallb,
        ]
    )

    # Longhorn
    longhorn_config = config['components']['longhorn']
    longhorn_namespace = create_namespace(
        slug="longhorn",
        namespace="longhorn-system",
        depends_on=[]
    )
    longhorn_cert_manager_issuer = create_cert_manager_issuer(
        slug="longhorn",
        namespace="longhorn-system",
        cloudflare_email=env_vars['CLOUDFLARE_EMAIL'],
        cloudflare_api_token=env_vars['CLOUDFLARE_API_TOKEN'],
        depends_on=[
            longhorn_namespace,
            cert_manager_operator
        ]
    )

    longhorn_root_domain = '.'.join(longhorn_config['LONGHORN_DOMAIN_NAME'].split('.')[1:])
    longhorn_cert_manager_certificate = create_cert_manager_certificate(
        slug="longhorn",
        namespace="longhorn-system",
        domain_name=longhorn_root_domain,
        issuer_secret_name=longhorn_cert_manager_issuer.issuer_secret_name,
        certificate_dns_names=[
            longhorn_root_domain,
            f"*.{longhorn_root_domain}",
        ],
        depends_on=[
            longhorn_namespace,
            longhorn_cert_manager_issuer,
        ]
    )
    # Get disk configurations from config
    longhorn_disks = longhorn_config.get('LONGHORN_DISKS', [])
    
    # Ensure each disk has the correct node selector format
    for disk in longhorn_disks:
        if 'node_selector' not in disk and 'kubernetes.io/hostname' not in disk.get('node_selector', {}):
            # If node name is specified but not in the correct format, fix it
            if 'node' in disk:
                disk['node_selector'] = {'kubernetes.io/hostname': disk['node']}
    
    # Define storage classes for different performance tiers
    longhorn_storage_classes = [
        {
            "name": "longhorn-nvme",
            "replica_count": 2,
            "disk_selector": ["nvme"],
            "is_default": True,
            "reclaim_policy": "Retain",
            "fs_type": "ext4"
        },
        {
            "name": "longhorn-ssd",
            "replica_count": 3,
            "disk_selector": ["ssd"],
            "is_default": False,
            "reclaim_policy": "Retain",
            "fs_type": "ext4"
        },
        {
            "name": "longhorn-hdd",
            "replica_count": 1,
            "disk_selector": ["hdd"],
            "is_default": False,
            "reclaim_policy": "Retain",
            "fs_type": "ext4"
        }
    ]
    
    longhorn = create_longhorn(
        slug="longhorn",
        namespace="longhorn-system",
        ingress_enabled=True,
        ingress_host=longhorn_config['LONGHORN_DOMAIN_NAME'],
        ingress_class_name="nginx",
        ingress_tls_secret=longhorn_cert_manager_certificate.certificate_secret_name,
        disks=longhorn_disks,
        storage_classes=longhorn_storage_classes,
        depends_on=[
            longhorn_namespace,
            ingress_nginx,
            longhorn_cert_manager_certificate,
        ]
    )

    # Rancher
    rancher_config = config['components']['rancher']
    rancher_namespace = create_namespace(
        slug="rancher",
        namespace="rancher",
        depends_on=[]
    )
    rancher_cert_manager_issuer = create_cert_manager_issuer(
        slug="rancher",
        namespace="rancher",
        cloudflare_email=env_vars['CLOUDFLARE_EMAIL'],
        cloudflare_api_token=env_vars['CLOUDFLARE_API_TOKEN'],
        depends_on=[
            rancher_namespace,
            cert_manager_operator
        ]
    )

    rancher_root_domain = '.'.join(rancher_config['RANCHER_DOMAIN_NAME'].split('.')[1:])
    rancher_cert_manager_certificate = create_cert_manager_certificate(
        slug="rancher",
        namespace="rancher",
        domain_name=rancher_root_domain,
        issuer_secret_name=rancher_cert_manager_issuer.issuer_secret_name,
        certificate_dns_names=[
            rancher_root_domain,
            f"*.{rancher_root_domain}",
        ],
        depends_on=[
            rancher_namespace,
            rancher_cert_manager_issuer,
        ]
    )
    rancher = create_rancher(
        slug="rancher",
        namespace="rancher",
        hostname=rancher_config['RANCHER_DOMAIN_NAME'],
        replicas=3,
        bootstrap_password=rancher_config['RANCHER_BOOTSTRAP_PASSWORD'],
        certificate_secret_name=rancher_cert_manager_certificate.certificate_secret_name,
        ingress_class_name="nginx",
        extra_env_vars=[],
        depends_on=[
            rancher_namespace,
            rancher_cert_manager_issuer,
            rancher_cert_manager_certificate,
            ingress_nginx,
            longhorn,
        ]
    )

    # PostgreSQL Operator
    postgresql_namespace_name = "postgresql-system"
    postgresql_namespace = create_namespace(
        slug="postgresql",
        namespace=postgresql_namespace_name,
        depends_on=[]
    )
    
    postgresql_operator_crds = create_postgresql_operator_crds(
        slug="postgresql-crds",
        namespace=postgresql_namespace_name,
        depends_on=[
            postgresql_namespace
        ]
    )
    
    postgresql_operator = create_postgresql_operator(
        slug="postgresql-operator",
        namespace=postgresql_namespace_name,
        depends_on=[
            postgresql_namespace,
            postgresql_operator_crds
        ]
    )
    
    
    # Whatsapp WAHA
    whatsapp_waha_config = config['components']['whatsapp_waha']
    
    # WhatsApp WAHA PostgreSQL Instance
    whatsapp_db_config = whatsapp_waha_config.get('postgres_db', {})
    whatsapp_db_name = whatsapp_db_config.get('db_name', 'whatsapp_db')
    whatsapp_db_superuser = whatsapp_db_config.get('superuser', 'postgres')
    whatsapp_db_superuser_password = whatsapp_db_config.get('superuser_password', 'postgres')
    whatsapp_db_username = whatsapp_db_config.get('username', 'whatsapp_user')
    whatsapp_db_password = whatsapp_db_config.get('password', 'whatsapp_password')
    
    whatsapp_waha_namespace_name = "whatsapp"

    whatsapp_waha_namespace = create_namespace(
        slug=whatsapp_waha_namespace_name,
        namespace=whatsapp_waha_namespace_name,
        depends_on=[]
    )
    
    whatsapp_waha_postgres_instance = create_postgres_instance_base(
        slug="whatsapp-db",
        namespace=whatsapp_waha_namespace_name,
        db_name=whatsapp_db_name,
        superuser=whatsapp_db_superuser,
        superuser_password=whatsapp_db_superuser_password,
        username=whatsapp_db_username,
        user_password=whatsapp_db_password,
        replicas=whatsapp_db_config.get('replicas', 1),
        storage_size=whatsapp_db_config.get('storage_size', '5Gi'),
        wal_storage_size=whatsapp_db_config.get('wal_storage_size', '1Gi'),
        repo_storage_size=whatsapp_db_config.get('repo_storage_size', '2Gi'),
        s3_backup=whatsapp_db_config.get('s3_backup', None),
        s3_bootstrap=whatsapp_db_config.get('s3_bootstrap', None),
        service_type=whatsapp_db_config.get('service_type', 'LoadBalancer'),
        service_annotations=whatsapp_db_config.get('service_annotations', {}),
        depends_on=[
            whatsapp_waha_namespace,  # Depend on WhatsApp namespace
            postgresql_operator_crds,
            postgresql_operator
        ]
    )
    whatsapp_waha_domain_name=whatsapp_waha_config['domain_name']
    whatsapp_waha_root_domain = '.'.join(whatsapp_waha_domain_name.split('.')[1:])

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
        postgres_uri=whatsapp_waha_postgres_instance.normal_user_postgres_uri,
        s3_storage=whatsapp_waha_config.get('s3_storage', None),
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
            whatsapp_waha_postgres_instance,
        ]
    )

    # registry = create_registry(
    #     slug="registry",
    #     namespace="registry",
    #     registry_url=env_vars['REGISTRY_URL'],
    #     registry_username=env_vars['REGISTRY_USERNAME'],
    #     registry_password=env_vars['REGISTRY_PASSWORD'],
    #     depends_on=["common-namespace"]
    # )

    # TODO: make sure to generate skaffolds only when the component is included in components

    # Collect all components
    components = [
        # PostgreSQL Operator
        postgresql_namespace,
        postgresql_operator_crds,
        postgresql_operator,
        
        # WhatsApp WAHA
        whatsapp_waha_namespace,
        whatsapp_waha_cert_manager_issuer,
        whatsapp_waha_cert_manager_certificate,
        whatsapp_waha_postgres_instance,
        whatsapp_waha,
    ]
    
    # Generate skaffold configurations
    generate_skaffolds(
        components=components,
    )
    
    # Generate IntelliJ run configurations if enabled
    if INTELLIJ_RUN_CONFIGURATIONS_ENABLED or env_vars['INTELLIJ_RUN_CONFIGURATIONS_ENABLED'].lower() == 'true':
        generate_intelij_skaffolds_run_configurations()
    
    # Sync generated files to the final directory
    subprocess.call(["rsync", "-rcvu", "--delete", f"{GENERATED_SKAFFOLD_TMP_DIR}/", f"{GENERATED_SKAFFOLD_DIR}/"])
    subprocess.call(["rm", "-rf", f"{GENERATED_SKAFFOLD_TMP_DIR}/"])


if __name__ == '__main__':
    generate_all_skaffolds()
