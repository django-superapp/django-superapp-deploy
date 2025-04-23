from typing import Dict, List, Optional, Any
import os
import yaml
import base64

from base.component_types import Component
from base.constants import GENERATED_SKAFFOLD_TMP_DIR
from base.utils import get_chart_path


def create_whatsapp_waha(
    slug: str,
    namespace: str,
    image_repository: str = "devlikeapro/waha",
    image_tag: str = "latest",
    replicas: int = 1,
    env_vars: Optional[Dict[str, str]] = None,
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
    
    # Validate basic auth parameters
    if basic_auth_enabled:
        if not username or not password:
            raise ValueError("Username and password are required when basic_auth_enabled is True")
    
    # Generate basic auth secret name
    basic_auth_secret = f"{slug}-basic-auth"
    
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
        "env": env_vars or {},
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
    
    # Generate Fleet configuration
    fleet_config = {
        "namespace": namespace,
        "helm": {
            "chart": get_chart_path("whatsapp-waha"),
            "values": {
                "valuesFiles": ["values.yaml"]
            }
        }
    }
    
    # Write Fleet configuration
    with open(f"{output_dir}/fleet.yaml", "w") as file:
        yaml.dump(fleet_config, file, default_flow_style=False)
    
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
        with open(f"{output_dir}/basic-auth-secret.yaml", "w") as file:
            yaml.dump(basic_auth_manifest, file, default_flow_style=False)
    
    # Return Component object
    return Component(
        slug=slug,
        dir_name=dir_name,
        fleet_name=f"{slug}-whatsapp-waha",
        depends_on=depends_on or []
    )
