from typing import Dict, List, Optional
import os
import yaml
from ilio import write

from components.base.component_types import Component
from components.base.constants import GENERATED_SKAFFOLD_TMP_DIR
from components.base.utils import get_chart_path
from components.cloudflare_tunnel.constants import (
    CLOUDFLARE_TUNNEL_DEFAULT_IMAGE,
    CLOUDFLARE_TUNNEL_DEFAULT_TAG
)


def create_cloudflare_tunnel(
    slug: str,
    namespace: str,
    token: str,
    replicas: int = 2,
    image_repository: str = CLOUDFLARE_TUNNEL_DEFAULT_IMAGE,
    image_tag: str = CLOUDFLARE_TUNNEL_DEFAULT_TAG,
    env_vars: Optional[Dict[str, str]] = None,
    depends_on: Optional[List[Component]] = None
) -> Component:
    """
    Deploy a Cloudflare Tunnel using Helm.
    
    Args:
        slug: Unique identifier for the deployment
        namespace: Kubernetes namespace to deploy the component
        token: Cloudflare Tunnel token
        replicas: Number of replicas for the deployment
        image_repository: Docker image repository
        image_tag: Docker image tag
        env_vars: Additional environment variables
        depends_on: List of dependencies for Fleet
        
    Returns:
        Component object with metadata about the deployment
    """
    # Create directory structure
    dir_name = f"{slug}-cloudflare-tunnel"
    output_dir = f'{GENERATED_SKAFFOLD_TMP_DIR}/{dir_name}'
    os.makedirs(output_dir, exist_ok=True)
    manifests_dir = f"{output_dir}/manifests"
    os.makedirs(manifests_dir, exist_ok=True)
    
    # Generate Helm values
    helm_values = {
        "nameOverride": slug,
        "fullnameOverride": f"{slug}-cloudflared",
        "namespace": namespace,
        "image": {
            "repository": image_repository,
            "tag": image_tag
        },
        "replicas": replicas,
        "token": token,
        "envVars": env_vars or {}
    }
    
    # Write values file
    with open(f"{output_dir}/values.yaml", "w") as file:
        yaml.dump(helm_values, file, default_flow_style=False)
    
    # Generate secret manifest for token
    token_secret = {
        "apiVersion": "v1",
        "kind": "Secret",
        "metadata": {
            "name": f"{slug}-cloudflare-tunnel-token",
            "namespace": namespace
        },
        "type": "Opaque",
        "stringData": {
            "token": token
        }
    }
    
    # Write secret manifest
    with open(f"{manifests_dir}/token-secret.yaml", "w") as file:
        yaml.dump(token_secret, file, default_flow_style=False)
    
    # Generate skaffold.yaml
    skaffold_config = {
        "apiVersion": "skaffold/v3",
        "kind": "Config",
        "deploy": {
            "kubectl": {
                "defaultNamespace": namespace,
            }
        },
        "manifests": {
            "helm": {
                "releases": [
                    {
                        "name": f"{slug}-cloudflare-tunnel",
                        "chartPath": get_chart_path("./charts/cloudflare-tunnel"),
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
                f"./manifests/token-secret.yaml",
            ],
        },
    }
    
    skaffold_yaml = yaml.dump(skaffold_config, default_flow_style=False)
    write(f"{output_dir}/skaffold-cloudflare-tunnel.yaml", skaffold_yaml)
    
    # Generate fleet.yaml for dependencies
    fleet_config = {
        "dependsOn": [
            c.as_fleet_dependency for c in depends_on
        ] if depends_on else [],
        "helm": {
            "releaseName": f"{slug}-cloudflare-tunnel",
        },
        "labels": {
            "name": f"{slug}-cloudflare-tunnel"
        }
    }
    
    fleet_yaml = yaml.dump(fleet_config, default_flow_style=False)
    write(f"{output_dir}/fleet.yaml", fleet_yaml)
    
    # Return Component object
    return Component(
        slug=slug,
        namespace=namespace,
        dir_name=dir_name,
        fleet_name=f"{slug}-cloudflare-tunnel",
    )
