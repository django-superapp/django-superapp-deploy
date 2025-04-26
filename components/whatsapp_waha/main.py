import os
from typing import Dict, List, Optional, Any, TypedDict
import yaml
import base64

from ilio import write

from components.base.component_types import Component
from components.base.constants import GENERATED_SKAFFOLD_TMP_DIR
from components.base.utils import get_chart_path


class S3StorageConfig(TypedDict, total=False):
    """
    Configuration for S3 storage in WhatsApp WAHA.
    
    Attributes:
        region: S3 region (e.g., 'eu-west-1')
        bucket: S3 bucket name
        access_key_id: S3 access key
        secret_access_key: S3 secret key
        endpoint: S3 endpoint URL (optional, for non-AWS S3)
        force_path_style: Whether to force path style (optional, for non-AWS S3)
        proxy_files: Whether to proxy media files through WAHA (optional, default False)
    """
    region: str
    bucket: str
    access_key_id: str
    secret_access_key: str
    endpoint: Optional[str]
    force_path_style: Optional[bool]
    proxy_files: Optional[bool]


def create_whatsapp_waha(
    slug: str,
    namespace: str,
    image_repository: str = "devlikeapro/waha",
    image_tag: str = "latest",
    replicas: int = 1,
    env_vars: Optional[Dict[str, str]] = None,
    postgres_uri: Optional[str] = None,
    s3_storage: Optional[S3StorageConfig] = None,
    ingress_enabled: bool = False,
    ingress_host: Optional[str] = None,
    ingress_class_name: str = "nginx",
    ingress_tls_secret: Optional[str] = None,
    basic_auth_enabled: bool = False,
    username: Optional[str] = None,
    password: Optional[str] = None,
    basic_auth_realm: str = "Authentication Required",
    depends_on: Optional[List[Component]] = None
) -> Component:
    """
    Deploy WhatsApp WAHA (WhatsApp HTTP API) using Helm.
    
    Args:
        slug: Unique identifier for the deployment
        namespace: Kubernetes namespace to deploy the component
        image_repository: Docker image repository for WAHA
        image_tag: Docker image tag for WAHA
        replicas: Number of replicas to deploy
        env_vars: Environment variables to pass to the container
        postgres_uri: PostgreSQL connection URI for session storage
        s3_storage: S3StorageConfig with S3 storage configuration
        ingress_enabled: Whether to enable ingress
        ingress_host: Hostname for the ingress
        ingress_class_name: Ingress class name
        ingress_tls_secret: TLS secret name for HTTPS
        basic_auth_enabled: Whether to enable basic auth for ingress
        username: Username for basic auth (required if basic_auth_enabled is True)
        password: Password for basic auth (required if basic_auth_enabled is True)
        basic_auth_realm: Realm for basic auth
        depends_on: List of dependencies for Fleet
        
    Returns:
        Component object with metadata about the deployment
    """
    # Create directory structure
    dir_name = f"{slug}-whatsapp-waha"
    output_dir = f'{GENERATED_SKAFFOLD_TMP_DIR}/{dir_name}'
    os.makedirs(output_dir, exist_ok=True)
    manifests_dir = f"{output_dir}/manifests"
    os.makedirs(manifests_dir, exist_ok=True)
    
    # Validate basic auth parameters
    if basic_auth_enabled:
        if not username or not password:
            raise ValueError("Username and password are required when basic_auth_enabled is True")
    
    # Generate basic auth secret name
    basic_auth_secret = f"{slug}-basic-auth"
    
    # Prepare environment variables
    environment_vars = env_vars or {}
    
    # Add PostgreSQL configuration if provided
    if postgres_uri:
        environment_vars["WHATSAPP_SESSIONS_POSTGRESQL_URL"] = postgres_uri
    
    # Add S3 storage configuration if provided
    if s3_storage:
        environment_vars["WAHA_MEDIA_STORAGE"] = "S3"
        
        if "region" in s3_storage:
            environment_vars["WAHA_S3_REGION"] = s3_storage["region"]
        
        if "bucket" in s3_storage:
            environment_vars["WAHA_S3_BUCKET"] = s3_storage["bucket"]
        
        if "access_key_id" in s3_storage:
            environment_vars["WAHA_S3_ACCESS_KEY_ID"] = s3_storage["access_key_id"]
        
        if "secret_access_key" in s3_storage:
            environment_vars["WAHA_S3_SECRET_ACCESS_KEY"] = s3_storage["secret_access_key"]
        
        if "endpoint" in s3_storage:
            environment_vars["WAHA_S3_ENDPOINT"] = s3_storage["endpoint"]
        
        if "force_path_style" in s3_storage:
            environment_vars["WAHA_S3_FORCE_PATH_STYLE"] = str(s3_storage["force_path_style"])
        
        if "proxy_files" in s3_storage:
            environment_vars["WAHA_S3_PROXY_FILES"] = str(s3_storage["proxy_files"])
    
    # Generate Helm values
    helm_values = {
        "nameOverride": slug,
        "replicaCount": replicas,
        "image": {
            "repository": image_repository,
            "tag": image_tag
        },
        "service": {
            "type": "ClusterIP",
            "port": 80,
            "targetPort": 3000
        },
        "env": environment_vars,
        "ingress": {
            "enabled": ingress_enabled,
            "className": ingress_class_name
        },
        "basicAuth": {
            "enabled": basic_auth_enabled,
            "secretName": basic_auth_secret,
            "realm": basic_auth_realm
        }
    }
    
    # Configure ingress if enabled
    if ingress_enabled and ingress_host:
        helm_values["ingress"]["hosts"] = [
            {
                "host": ingress_host,
                "paths": [
                    {
                        "path": "/",
                        "pathType": "Prefix"
                    }
                ]
            }
        ]
        
        # Configure TLS if a secret is provided
        if ingress_tls_secret:
            helm_values["ingress"]["tls"] = [
                {
                    "secretName": ingress_tls_secret,
                    "hosts": [ingress_host]
                }
            ]
    
    # Write values file
    with open(f"{output_dir}/values.yaml", "w") as file:
        yaml.dump(helm_values, file, default_flow_style=False)
    

    # Create basic auth secret if enabled
    if basic_auth_enabled and username and password:
        # Create htpasswd-like string: username:hashed_password
        auth_string = f"{username}:{password}"
        auth_base64 = base64.b64encode(auth_string.encode()).decode()
        
        # Create secret manifest
        basic_auth_manifest = {
            "apiVersion": "v1",
            "kind": "Secret",
            "metadata": {
                "name": basic_auth_secret,
                "namespace": namespace
            },
            "type": "Opaque",
            "data": {
                "auth": auth_base64
            }
        }
        
        # Write secret manifest
        with open(f"{manifests_dir}/basic-auth-secret.yaml", "w") as file:
            yaml.dump(basic_auth_manifest, file, default_flow_style=False)

    # Generate skaffold.yaml
    skaffold_config = {
        "apiVersion": "skaffold/v3",
        "kind": "Config",
        "manifests": {
            "helm": {
                "releases": [
                    {
                        "name": f"{slug}-whatsapp-waha",
                        "chartPath": get_chart_path("./charts/whatsapp-waha"),
                        "valuesFiles": [
                            f"./values.yaml"
                        ],
                        "namespace": namespace,
                        "createNamespace": True,
                        "wait": True,
                        "upgradeOnChange": True
                    }
                ],
            },
            "rawYaml": [
                f"./manifests/basic-auth-secret.yaml",
            ],
        },
        "deploy": {
            "kubectl": {
                "defaultNamespace": namespace,
            },
        },
    }

    skaffold_yaml = yaml.dump(skaffold_config, default_flow_style=False)
    write(f"{output_dir}/skaffold-whatsapp-waha.yaml", skaffold_yaml)

    # Generate fleet.yaml for dependencies
    fleet_config = {
        "dependsOn": [
            c.as_fleet_dependency for c in depends_on
        ] if depends_on else [],
        "helm": {
            "releaseName": f"{slug}-whatsapp-waha",
        },
        "labels": {
            "name": f"{slug}-whatsapp-waha"
        }
    }

    fleet_yaml = yaml.dump(fleet_config, default_flow_style=False)
    write(f"{output_dir}/fleet.yaml", fleet_yaml)

    # Return Component object
    return Component(
        slug=slug,
        namespace=namespace,
        dir_name=dir_name,
        fleet_name=f"{slug}-whatsapp-waha",
    )
