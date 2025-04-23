import os
from typing import Any, Dict, List, Optional

import yaml
from ilio import write

from ..base.component_types import Component
from ..base.constants import *


def create_namespace(
    slug: str,
    namespace: str,
    labels: Optional[Dict[str, str]] = None,
    annotations: Optional[Dict[str, str]] = None,
    depends_on: Optional[List[Component]] = None
) -> Component:
    """
    Create a Kubernetes namespace.
    
    Args:
        slug: Unique identifier for the deployment
        namespace: Name of the namespace to create
        labels: Optional labels to add to the namespace
        annotations: Optional annotations to add to the namespace
        depends_on: List of dependencies for Fleet
        
    Returns:
        Directory name where the configuration is generated
    """
    # Create directory structure
    dir_name = f"{slug}-namespace"
    output_dir = f'{GENERATED_SKAFFOLD_TMP_DIR}/{dir_name}'
    manifests_dir = f'{output_dir}/manifests'
    
    os.makedirs(output_dir, exist_ok=True)
    os.makedirs(manifests_dir, exist_ok=True)
    
    # Create namespace manifest
    namespace_manifest = {
        "apiVersion": "v1",
        "kind": "Namespace",
        "metadata": {
            "name": namespace
        }
    }
    
    # Add labels if provided
    if labels:
        namespace_manifest["metadata"]["labels"] = labels
    
    # Add annotations if provided
    if annotations:
        namespace_manifest["metadata"]["annotations"] = annotations
    
    # Write namespace manifest
    write(f"{manifests_dir}/namespace.yaml", 
          yaml.dump(namespace_manifest, default_flow_style=False))
    
    # Generate skaffold.yaml
    skaffold_config = {
        "apiVersion": "skaffold/v3",
        "kind": "Config",
        "requires": [
            c.as_skaffold_dependency for c in depends_on
        ] if depends_on else [],
        "manifests": {
            "rawYaml": [
                "./manifests/namespace.yaml",
            ],
        },
        "deploy": {
            "kubectl": {
                "defaultNamespace": namespace,
            },
        },
    }
    
    skaffold_yaml = yaml.dump(skaffold_config, default_flow_style=False)
    write(f"{output_dir}/skaffold-namespace.yaml", skaffold_yaml)
    
    # Generate fleet.yaml for dependencies
    fleet_config = {
        "namespace": namespace,
        "dependsOn": [
            c.as_fleet_dependency for c in depends_on
        ] if depends_on else [],
        "labels": {
            "name": f"{slug}-namespace"
        },
    }
    
    fleet_yaml = yaml.dump(fleet_config, default_flow_style=False)
    write(f"{output_dir}/fleet.yaml", fleet_yaml)

    return Component(
        slug=slug,
        namespace=namespace,
        dir_name=dir_name,
        fleet_name=f"{slug}-namespace",
    )
