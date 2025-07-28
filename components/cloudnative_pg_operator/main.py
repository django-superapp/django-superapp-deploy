"""
CloudNative PostgreSQL Operator Component

This module provides functionality to deploy the CloudNative PostgreSQL operator
which manages PostgreSQL clusters in Kubernetes using cloud-native patterns.
"""

import os
import yaml
from typing import List, Optional
from ilio import write

from ..base.component_types import Component
from ..base.constants import *
from ..base.utils import get_chart_path


def create_cloudnative_pg_operator(
        slug: str,
        namespace: str = 'cnpg-system',
        depends_on: Optional[List[Component]] = None
) -> Component:
    """
    Deploy the CloudNative PostgreSQL operator using Helm.
    
    Args:
        slug: Unique identifier for the deployment
        namespace: Kubernetes namespace to deploy the operator
        depends_on: List of dependencies for Fleet
        
    Returns:
        Component instance with deployment configuration
    """
    # Create directory structure
    dir_name = f"{slug}-cloudnative-pg-operator"
    output_dir = f'{GENERATED_SKAFFOLD_TMP_DIR}/{dir_name}'
    os.makedirs(output_dir, exist_ok=True)

    # Generate Helm values for CloudNative PG operator
    cnpg_values = {
        "fullnameOverride": "cnpg-controller-manager",
        "crds": {
            "create": True
        },
        "config": {
            "create": True,
            "name": "cnpg-controller-manager-config"
        },
        "webhook": {
            "port": 9443
        },
        "monitoring": {
            "enabled": True,
            "podMonitorEnabled": True
        },
        "image": {
            "repository": "ghcr.io/cloudnative-pg/cloudnative-pg",
            "pullPolicy": "IfNotPresent"
        },
        "replicaCount": 1,
        "resources": {
            "limits": {
                "cpu": "100m",
                "memory": "200Mi"
            },
            "requests": {
                "cpu": "100m",
                "memory": "200Mi"
            }
        }
    }
    
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
                        "name": f"{slug}-cloudnative-pg-operator",
                        "namespace": namespace,
                        "chartPath": get_chart_path("./charts/cloudnative-pg"),
                        "createNamespace": False,
                        "valuesFiles": [
                            "./cnpg-values.yaml"
                        ]
                    },
                ]
            }
        },
        "deploy": {
            "kubectl": {
                # "defaultNamespace": namespace,
            },
        },
    }
    
    # Generate Fleet configuration
    fleet_config = {
        "dependsOn": [
            c.as_fleet_dependency for c in depends_on
        ] if depends_on else [],
        "helm": {
            "releaseName": f"{slug}-cloudnative-pg-operator",
        },
        "labels": {
            "name": f"{slug}-cloudnative-pg-operator",
        },
        "diff": {
            "comparePatches": [
                {
                    "apiVersion": "admissionregistration.k8s.io/v1",
                    "kind": "MutatingWebhookConfiguration",
                    "name": "cnpg-mutating-webhook-configuration",
                    "operations": [
                        {
                            "op": "remove",
                            "path": "/webhooks"
                        },
                    ]
                },
                {
                    "apiVersion": "admissionregistration.k8s.io/v1",
                    "kind": "ValidatingWebhookConfiguration",
                    "name": "cnpg-validating-webhook-configuration",
                    "operations": [
                        {
                            "op": "remove",
                            "path": "/webhooks"
                        },
                    ]
                }
            ]
        }
    }

    # Write all configuration files
    write(f"{output_dir}/cnpg-values.yaml", 
          yaml.dump(cnpg_values, default_flow_style=False))
    
    write(f"{output_dir}/skaffold-cloudnative-pg-operator.yaml", 
          yaml.dump(skaffold_config, default_flow_style=False))
    
    write(f"{output_dir}/fleet.yaml", 
          yaml.dump(fleet_config, default_flow_style=False))

    return Component(
        slug=slug,
        namespace=namespace,
        dir_name=dir_name,
        fleet_name=f"{slug}-cloudnative-pg-operator",
        depends_on=depends_on
    )