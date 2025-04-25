import os
import json
import base64
from typing import Any, Dict, List, Optional

import yaml
from ilio import write

from ..base.component_types import Component
from ..base.constants import *


def create_registry(
    slug: str,
    namespace: str,
    registry_url: str,
    registry_username: str,
    registry_password: str,
    insecure_registries: Optional[List[str]] = None,
    secret_name: str = "registry-secret",
    depends_on: Optional[List[Component]] = None
) -> Component:
    """
    Create a Kubernetes secret for Docker registry authentication.
    
    Args:
        slug: Unique identifier for the deployment
        namespace: Kubernetes namespace to create the secret in
        registry_url: URL of the Docker registry
        registry_username: Username for registry authentication
        registry_password: Password for registry authentication
        insecure_registries: List of insecure registries
        secret_name: Name of the Kubernetes secret
        depends_on: List of dependencies for Fleet
        
    Returns:
        Directory name where the configuration is generated
    """
    # Create directory structure
    dir_name = f"{slug}-registry"
    output_dir = f'{GENERATED_SKAFFOLD_TMP_DIR}/{dir_name}'
    manifests_dir = f'{output_dir}/manifests'
    
    os.makedirs(output_dir, exist_ok=True)
    os.makedirs(manifests_dir, exist_ok=True)
    
    # Extract registry domain from URL
    registry_domain = registry_url.split("/")[0]
    
    # Create registry secret
    docker_config = {
        "auths": {
            registry_domain: {
                "username": registry_username,
                "password": registry_password
            }
        }
    }
    
    # Add insecure registries if provided
    if insecure_registries:
        docker_config["insecure-registries"] = insecure_registries
    
    # Create secret manifest
    registry_secret = {
        "apiVersion": "v1",
        "kind": "Secret",
        "metadata": {
            "name": secret_name,
            "namespace": namespace
        },
        "data": {
            ".dockerconfigjson": base64.b64encode(json.dumps(docker_config).encode()).decode()
        },
        "type": "kubernetes.io/dockerconfigjson"
    }
    
    # Write registry secret manifest
    write(f"{manifests_dir}/registry-secret.yaml", 
          yaml.dump(registry_secret, default_flow_style=False))
    
    # Generate skaffold.yaml
    skaffold_config = {
        "apiVersion": "skaffold/v3",
        "kind": "Config",
        "manifests": {
            "rawYaml": [
                "./manifests/registry-secret.yaml",
            ],
        },
        "deploy": {
            "kubectl": {
                "defaultNamespace": namespace,
            },
        },
    }
    
    skaffold_yaml = yaml.dump(skaffold_config, default_flow_style=False)
    write(f"{output_dir}/skaffold-registry.yaml", skaffold_yaml)
    
    # Generate fleet.yaml for dependencies
    fleet_config = {
        "namespace": namespace,
        "dependsOn": [
            c.as_fleet_dependency for c in depends_on
        ] if depends_on else [],
        "labels": {
            "name": f"{slug}-registry"
        }
    }
    
    fleet_yaml = yaml.dump(fleet_config, default_flow_style=False)
    write(f"{output_dir}/fleet.yaml", fleet_yaml)
    
    return Component(
        slug=slug,
        namespace=namespace,
        dir_name=dir_name,
        fleet_name=f"{slug}-registry",
    )
