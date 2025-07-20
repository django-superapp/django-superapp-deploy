"""
Longhorn Storage Component

This module provides functionality to deploy the Longhorn distributed
storage system for Kubernetes.
"""
from typing import Any, Dict, List, Optional, Union, TypedDict, Literal
import os

import yaml
from ilio import write

from ..base.component_types import Component
from ..base.constants import *
from ..base.utils import get_chart_path
from .setup_disks import create_disk_setup_jobs
from .types import LonghornDisk, LonghornStorageClass


# generate_longhorn_node_patch moved to setup_disks.py


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


def create_longhorn(
        slug: str,
        namespace: str = 'longhorn-system',
        ingress_enabled: bool = False,
        ingress_host: Optional[str] = None,
        ingress_tls_secret: Optional[str] = None,
        ingress_class_name: str = 'nginx',
        disks: Optional[List[LonghornDisk]] = None,
        storage_classes: Optional[List[LonghornStorageClass]] = None,
        depends_on: Optional[List[Component]] = None
) -> Component:
    """
    Deploy the Longhorn storage system using Helm.

    Args:
        slug: Unique identifier for the deployment
        namespace: Kubernetes namespace to deploy Longhorn
        ingress_enabled: Whether to enable the Longhorn UI ingress
        ingress_host: Hostname for the Longhorn UI ingress
        ingress_tls_secret: Name of the TLS secret for the ingress
        ingress_class_name: Ingress class to use
        disks: List of LonghornDisk configurations to add to Longhorn nodes
        storage_classes: List of LonghornStorageClass configurations
        depends_on: List of dependencies for Fleet

    Returns:
        Directory name where the configuration is generated
    """
    # Validate required parameters if ingress is enabled
    if ingress_enabled and not ingress_host:
        raise ValueError("ingress_host is required when ingress_enabled is True")

    # Initialize disks and storage classes if not provided
    disks = disks or []
    storage_classes = storage_classes or []
    # Create directory structure
    dir_name = f"{slug}-longhorn"
    output_dir = f'{GENERATED_SKAFFOLD_TMP_DIR}/{dir_name}'
    os.makedirs(output_dir, exist_ok=True)

    # Generate Helm values for Longhorn
    longhorn_values = {
        "persistence": {
            "enabled": False,  # Disable default persistence to use our custom configuration
            "defaultClass": len(storage_classes) == 0,  # Only true if no custom storage classes
            "defaultClassReplicaCount": 3,
        },
        "defaultSettings": {
            "defaultReplicaCount": 3,
            "backupstorePollInterval": 300,
            "defaultDataPath": "/var/lib/longhorn/",
            "replicaDiskSoftAntiAffinity": "false",
            "replicaSoftAntiAffinity": "true",
            "replicaAutoBalance": "least-effort",
            "storageOverProvisioningPercentage": 200,
            "storageMinimalAvailablePercentage": 10,
            "guaranteedEngineManagerCPU": 12,
            "guaranteedReplicaManagerCPU": 12,
        },
        "resources": {
            "requests": {
                "cpu": "100m",
                "memory": "128Mi"
            },
            "limits": {
                "cpu": "500m",
                "memory": "512Mi"
            }
        },
        "csi": {
            "attacherReplicaCount": 3,
            "provisionerReplicaCount": 3,
            "resizerReplicaCount": 3,
            "snapshotterReplicaCount": 3
        },
        "longhornManager": {
            "priorityClass": "system-cluster-critical"
        },
        "longhornDriver": {
            "priorityClass": "system-node-critical"
        }
    }

    # Configure ingress if enabled
    if ingress_enabled:
        longhorn_values["ingress"] = {
            "enabled": True,
            "host": ingress_host,
            "ingressClassName": ingress_class_name
        }

        # Add TLS configuration if a secret is provided
        if ingress_tls_secret:
            longhorn_values["ingress"]["tls"] = True
            longhorn_values["ingress"]["tlsSecret"] = ingress_tls_secret

    # Generate Skaffold configuration
    skaffold_config = {
        "apiVersion": "skaffold/v3",
        "kind": "Config",
        "build": {
            **SKAFFOLD_DEFAULT_BUILD,
            "artifacts": [],
        },
        "manifests": {
            "helm": {
                "releases": [
                    {
                        "name": f"{slug}-longhorn",
                        "namespace": namespace,
                        "chartPath": get_chart_path(f"./charts/longhorn"),
                        "createNamespace": True,
                        "valuesFiles": [
                            "./longhorn-values.yaml"
                        ],
                    },
                ]
            }
        },
        "deploy": {
            "helm": {
                "flags": {
                    "install": ["--no-hooks", "--force", "--replace"],
                    "upgrade": ["--no-hooks", "--force", "--replace"]
                }
            },
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
        "helm": {
            "releaseName": f"{slug}-longhorn",
        },
        "labels": {
            "name": f"{slug}-longhorn",
        },
        "diff": {
            "comparePatches": [
                {
                    "apiVersion": "apps/v1",
                    "kind": "Deployment",
                    "jsonPointers": [
                        "/metadata/resourceVersion",
                        "/metadata/uid"
                    ]
                },
                {
                    "apiVersion": "apps/v1",
                    "kind": "DaemonSet",
                    "jsonPointers": [
                        "/metadata/resourceVersion",
                        "/metadata/uid"
                    ]
                },
                {
                    "apiVersion": "v1",
                    "kind": "Service",
                    "jsonPointers": [
                        "/metadata/resourceVersion",
                        "/metadata/uid",
                        "/spec/clusterIP",
                        "/spec/clusterIPs"
                    ]
                },
                {
                    "apiVersion": "longhorn.io/v1beta2",
                    "kind": "Node",
                    "jsonPointers": [
                        "/metadata/resourceVersion",
                        "/metadata/uid",
                        "/metadata/generation"
                    ]
                }
            ]
        }
    }

    # Generate storage class configurations if provided
    if storage_classes:
        longhorn_values["persistence"]["storageClassDevices"] = []

        for sc in storage_classes:
            name = sc.get("name", f"longhorn-{slug}")
            replica_count = sc.get("replica_count", 3)
            disk_selector = sc.get("disk_selector", [])
            node_selector = sc.get("node_selector", [])
            is_default = sc.get("is_default", False)
            reclaim_policy = sc.get("reclaim_policy", "Delete")
            fs_type = sc.get("fs_type", "ext4")

            # Add the storage class configuration
            storage_class_config = {
                "name": name,
                "replicaCount": replica_count,
                "default": is_default,
                "reclaimPolicy": reclaim_policy,
                "fsType": fs_type
            }

            # Add selectors if provided
            if disk_selector:
                storage_class_config["diskSelector"] = ",".join(disk_selector)

            if node_selector:
                storage_class_config["nodeSelector"] = ",".join(node_selector)

            longhorn_values["persistence"]["storageClassDevices"].append(storage_class_config)

    # Create custom manifests for disk configuration and storage classes
    if disks:
        # Validate disk configurations
        for disk in disks:
            if "name" not in disk:
                raise ValueError("Each disk configuration must have a 'name' field")
            if "disk_id" not in disk:
                raise ValueError(f"Disk {disk['name']} must have a 'disk_id' field for identification (from /dev/disk/by-id/)")
            if "node_selector" not in disk:
                print(f"Warning: Disk {disk['name']} does not have a 'node_selector' field, disk setup may fail")

        # Create Jobs to set up disks (replaces DaemonSet approach)
        job_files = create_disk_setup_jobs(slug, namespace, disks, output_dir)

        # Add the Jobs to the manifests
        skaffold_config["manifests"]["rawYaml"] = skaffold_config.get("manifests", {}).get("rawYaml", []) + job_files

        # Node patching is now handled by the disk setup jobs

    # Create storage class manifests
    if storage_classes:
        sc_manifests = []
        for sc in storage_classes:
            sc_manifest = generate_storage_class_manifest(sc, namespace)
            sc_manifests.append(sc_manifest)

        write(f"{output_dir}/longhorn-storage-classes.yaml",
              yaml.dump_all(sc_manifests, default_flow_style=False))

        # Add the storage classes to the manifests
        if "rawYaml" not in skaffold_config["manifests"]:
            skaffold_config["manifests"]["rawYaml"] = []
        skaffold_config["manifests"]["rawYaml"].append("./longhorn-storage-classes.yaml")

    # Write all configuration files
    write(f"{output_dir}/longhorn-values.yaml",
          yaml.dump(longhorn_values, default_flow_style=False))

    write(f"{output_dir}/skaffold-longhorn.yaml",
          yaml.dump(skaffold_config, default_flow_style=False))

    write(f"{output_dir}/fleet.yaml",
          yaml.dump(fleet_config, default_flow_style=False))

    return Component(
        slug=slug,
        namespace=namespace,
        dir_name=dir_name,
        fleet_name=f"{slug}-longhorn",
    )
