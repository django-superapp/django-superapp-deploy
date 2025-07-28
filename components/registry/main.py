import base64
import json
from typing import List, Optional

from ilio import write

from .component_types import RegistryComponent
from ..base.component_types import Component
from ..base.constants import *


def create_registry(
    slug: str,
    namespace: str,
    registry_url: str,
    registry_username: str,
    registry_password: str,
    insecure_registries: Optional[List[str]] = None,
    depends_on: Optional[List[Component]] = None
) -> RegistryComponent:
    """
    Create a Kubernetes secret for Docker registry authentication.
    
    Args:
        slug: Unique identifier for the deployment
        namespace: Kubernetes namespace to create the secret in
        registry_url: URL of the Docker registry
        registry_username: Username for registry authentication
        registry_password: Password for registry authentication
        insecure_registries: List of insecure registries
        depends_on: List of dependencies for Fleet
        
    Returns:
        Directory name where the configuration is generated
    """
    # Create directory structure
    dir_name = f"{slug}-registry"
    output_dir = f'{GENERATED_SKAFFOLD_TMP_DIR}/{dir_name}'
    manifests_dir = f'{output_dir}/manifests'
    secret_name = f"{slug}-registry-secret"
    kaniko_secret_name = f"{slug}-registry-kaniko-secret"
    
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
    # TODO: the below secret is not sealed correctly
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
    
    # Create kaniko opaque secret with registry credentials
    # Note: Skaffold expects an Opaque secret with config.json for Kaniko builds
    kaniko_registry_secret = {
        "apiVersion": "v1",
        "kind": "Secret",
        "metadata": {
            "name": kaniko_secret_name,
            "namespace": namespace
        },
        "data": {
            "registry_url": base64.b64encode(registry_url.encode()).decode(),
            "registry_username": base64.b64encode(registry_username.encode()).decode(),
            "registry_password": base64.b64encode(registry_password.encode()).decode(),
            "config.json": base64.b64encode(json.dumps(docker_config).encode()).decode()
        },
        "type": "Opaque"
    }
    
    # Write registry secret manifests
    write(f"{manifests_dir}/registry-secret.yaml", 
          yaml.dump(registry_secret, default_flow_style=False))
    write(f"{manifests_dir}/registry-kaniko-secret.yaml", 
          yaml.dump(kaniko_registry_secret, default_flow_style=False))
    
    # Generate skaffold.yaml
    skaffold_config = {
        "apiVersion": "skaffold/v3",
        "kind": "Config",
        "manifests": {
            "rawYaml": [
                "./manifests/registry-secret.yaml",
                "./manifests/registry-kaniko-secret.yaml",
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
        "dependsOn": [
            c.as_fleet_dependency for c in depends_on
        ] if depends_on else [],
        "helm": {
            "releaseName": f"{slug}-registry",
        },
        "labels": {
            "name": f"{slug}-registry",
        }
    }
    
    fleet_yaml = yaml.dump(fleet_config, default_flow_style=False)
    write(f"{output_dir}/fleet.yaml", fleet_yaml)
    
    return RegistryComponent(
        slug=slug,
        namespace=namespace,
        dir_name=dir_name,
        registry_url=registry_url,
        secret_name=secret_name,
        kaniko_secret_name=kaniko_secret_name,
        kaniko_namespace=namespace,
        fleet_name=f"{slug}-registry",
        depends_on=depends_on
    )
