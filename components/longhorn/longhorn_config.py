"""
Longhorn Storage Configuration Component

This module provides functionality to configure Longhorn storage classes
after the operator has been installed.
"""
from typing import Any, Dict, List, Optional, TypedDict, Literal

from ilio import write

from ..base.component_types import Component
from ..base.constants import *


class LonghornStorageClass(TypedDict, total=False):
    """Configuration for a Longhorn storage class."""
    name: str
    replica_count: int
    disk_selector: List[str]
    node_selector: List[str]
    is_default: bool
    reclaim_policy: Literal["Delete", "Retain"]
    fs_type: str


def generate_storage_class_manifest(sc: LonghornStorageClass, namespace: str) -> Dict[str, Any]:
    """
    Generate a Kubernetes StorageClass manifest for Longhorn.
    
    Args:
        sc: Storage class configuration
        namespace: Kubernetes namespace
        
    Returns:
        StorageClass manifest
    """
    name = sc.get("name", "longhorn")
    replica_count = sc.get("replica_count", 3)
    disk_selector = sc.get("disk_selector", [])
    node_selector = sc.get("node_selector", [])
    is_default = sc.get("is_default", False)
    reclaim_policy = sc.get("reclaim_policy", "Delete")
    fs_type = sc.get("fs_type", "ext4")
    
    # Create the StorageClass manifest
    storage_class = {
        "apiVersion": "storage.k8s.io/v1",
        "kind": "StorageClass",
        "metadata": {
            "name": name,
            "annotations": {}
        },
        "provisioner": "driver.longhorn.io",
        "parameters": {
            "numberOfReplicas": str(replica_count),
            "staleReplicaTimeout": "30",
            "fromBackup": "",
            "fsType": fs_type
        },
        "reclaimPolicy": reclaim_policy,
        "allowVolumeExpansion": True
    }
    
    # Add selectors if provided
    if disk_selector:
        storage_class["parameters"]["diskSelector"] = ",".join(disk_selector)
    
    if node_selector:
        storage_class["parameters"]["nodeSelector"] = ",".join(node_selector)
    
    # Set as default storage class if specified
    if is_default:
        storage_class["metadata"]["annotations"]["storageclass.kubernetes.io/is-default-class"] = "true"
    
    return storage_class


def create_longhorn_config(
        slug: str,
        namespace: str = 'longhorn-system',
        storage_classes: Optional[List[LonghornStorageClass]] = None,
        depends_on: Optional[List[Component]] = None
) -> Component:
    """
    Configure Longhorn storage classes.
    
    This component creates storage classes for different disk tiers.
    Node disk patching is now handled by the disk setup component.
    
    Args:
        slug: Unique identifier for the deployment
        namespace: Kubernetes namespace where Longhorn is deployed
        storage_classes: List of LonghornStorageClass configurations
        depends_on: List of dependencies for Fleet (should include disk setup)
        
    Returns:
        Component instance for the Longhorn configuration
    """
    # Initialize storage classes if not provided
    storage_classes = storage_classes or []
    
    # Create directory structure
    dir_name = f"{slug}-longhorn-config"
    output_dir = f'{GENERATED_SKAFFOLD_TMP_DIR}/{dir_name}'
    os.makedirs(output_dir, exist_ok=True)

    # Generate Skaffold configuration
    skaffold_config = {
        "apiVersion": "skaffold/v3",
        "kind": "Config",
        "build": {
            **SKAFFOLD_DEFAULT_BUILD,
            "artifacts": [],
        },
        "manifests": {
            "rawYaml": []
        },
        "deploy": {
            "kubectl": {
                "defaultNamespace": namespace,
            },
        },
    }
    
    # Generate Fleet configuration
    fleet_config = {
        "dependsOn": [
            c.as_fleet_dependency for c in depends_on
        ] if depends_on else [],
        "labels": {
            "name": f"{slug}-longhorn-config",
        }
    }

    # Create storage class manifests
    if storage_classes:
        sc_manifests = []
        for sc in storage_classes:
            sc_manifest = generate_storage_class_manifest(sc, namespace)
            sc_manifests.append(sc_manifest)
        
        write(f"{output_dir}/longhorn-storage-classes.yaml", 
              yaml.dump_all(sc_manifests, default_flow_style=False))
        
        # Add the storage classes to the manifests
        skaffold_config["manifests"]["rawYaml"].append("./longhorn-storage-classes.yaml")

    # Write configuration files
    write(f"{output_dir}/skaffold-longhorn-config.yaml", 
          yaml.dump(skaffold_config, default_flow_style=False))
    
    write(f"{output_dir}/fleet.yaml", 
          yaml.dump(fleet_config, default_flow_style=False))

    return Component(
        slug=slug,
        namespace=namespace,
        dir_name=dir_name,
        fleet_name=f"{slug}-longhorn-config",
    )