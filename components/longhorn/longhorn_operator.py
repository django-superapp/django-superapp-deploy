"""
Longhorn Storage Operator Component

This module provides functionality to deploy the Longhorn operator
for Kubernetes distributed storage system.
"""
from typing import Any, Dict, List, Optional
import os

import yaml
from ilio import write

from ..base.component_types import Component
from ..base.constants import *
from ..base.utils import get_chart_path


def create_longhorn_operator(
        slug: str,
        namespace: str = 'longhorn-system',
        ingress_enabled: bool = False,
        ingress_host: Optional[str] = None,
        ingress_tls_secret: Optional[str] = None,
        ingress_class_name: str = 'nginx',
        depends_on: Optional[List[Component]] = None
) -> Component:
    """
    Deploy the Longhorn operator using Helm.
    
    Args:
        slug: Unique identifier for the deployment
        namespace: Kubernetes namespace to deploy Longhorn
        ingress_enabled: Whether to enable the Longhorn UI ingress
        ingress_host: Hostname for the Longhorn UI ingress
        ingress_tls_secret: Name of the TLS secret for the ingress
        ingress_class_name: Ingress class to use
        depends_on: List of dependencies for Fleet
        
    Returns:
        Component instance for the Longhorn operator
    """
    # Validate required parameters if ingress is enabled
    if ingress_enabled and not ingress_host:
        raise ValueError("ingress_host is required when ingress_enabled is True")
        
    # Create directory structure
    dir_name = f"{slug}-longhorn-operator"
    output_dir = f'{GENERATED_SKAFFOLD_TMP_DIR}/{dir_name}'
    os.makedirs(output_dir, exist_ok=True)

    # Generate Helm values for Longhorn operator
    longhorn_values = {
        "persistence": {
            "enabled": False,  # Disable default persistence
            "defaultClass": False,  # Don't create default storage class
            "defaultClassReplicaCount": 3,
        },
        "defaultSettings": {
            "createDefaultDiskLabeledNodes": True,
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
                        "name": f"{slug}-longhorn-operator",
                        "namespace": namespace,
                        "chartPath": get_chart_path(f"./charts/longhorn"),
                        "createNamespace": True,
                        "valuesFiles": [
                            "./longhorn-values.yaml"
                        ]
                    },
                ]
            }
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
        "helm": {
            "releaseName": f"{slug}-longhorn-operator",
        },
        "labels": {
            "name": f"{slug}-longhorn-operator",
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

    # Write all configuration files
    write(f"{output_dir}/longhorn-values.yaml", 
          yaml.dump(longhorn_values, default_flow_style=False))
    
    write(f"{output_dir}/skaffold-longhorn-operator.yaml", 
          yaml.dump(skaffold_config, default_flow_style=False))
    
    write(f"{output_dir}/fleet.yaml", 
          yaml.dump(fleet_config, default_flow_style=False))

    return Component(
        slug=slug,
        namespace=namespace,
        dir_name=dir_name,
        fleet_name=f"{slug}-longhorn-operator",
        depends_on=depends_on
    )