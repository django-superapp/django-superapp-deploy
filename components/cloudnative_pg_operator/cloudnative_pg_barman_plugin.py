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

def create_cloudnative_pg_barman_plugin(
        slug: str,
        namespace: str = 'cnpg-system',
        depends_on: Optional[List[Component]] = None
) -> Component:
    """
    Deploy the CloudNative PostgreSQL Barman Plugin using Helm.

    Args:
        slug: Unique identifier for the deployment
        namespace: Kubernetes namespace to deploy the plugin
        depends_on: List of dependencies for Fleet

    Returns:
        Component instance with deployment configuration
    """
    # Create directory structure
    dir_name = f"{slug}-cloudnative-pg-barman-plugin"
    output_dir = f'{GENERATED_SKAFFOLD_TMP_DIR}/{dir_name}'
    os.makedirs(output_dir, exist_ok=True)

    # Barman plugin values - always installed for backup best practices
    barman_values = {
        "namespace": namespace,
        "replicaCount": 1,
        "image": {
            "repository": "ghcr.io/cloudnative-pg/plugin-barman-cloud",
            "tag": "v0.5.0",
            "pullPolicy": "IfNotPresent"
        },
        "sidecar": {
            "image": "ghcr.io/cloudnative-pg/plugin-barman-cloud-sidecar:v0.5.0"
        },
        "logLevel": "info",
        "certManager": {
            "enabled": True
        },
        "resources": {
            "requests": {
                "cpu": "50m",
                "memory": "64Mi"
            },
            "limits": {
                "cpu": "100m",
                "memory": "128Mi"
            }
        }
    }

    # Generate Skaffold configuration
    skaffold_config = {
        "apiVersion": "skaffold/v3",
        "kind": "Config",
        "manifests": {
            "helm": {
                "releases": [
                    {
                        "name": f"{slug}-barman-plugin",
                        "namespace": namespace,
                        "chartPath": get_chart_path("./charts/cloudnative-pg-barman-plugin"),
                        "createNamespace": False,
                        "valuesFiles": [
                            "./barman-values.yaml"
                        ]
                    }
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
            "releaseName": f"{slug}-barman-plugin",
        },
        "labels": {
            "name": f"{slug}-barman-plugin",
        },
    }

    # Write all configuration files
    write(f"{output_dir}/barman-values.yaml",
          yaml.dump(barman_values, default_flow_style=False))

    write(f"{output_dir}/skaffold-barman-plugin.yaml",
          yaml.dump(skaffold_config, default_flow_style=False))

    write(f"{output_dir}/fleet.yaml",
          yaml.dump(fleet_config, default_flow_style=False))

    return Component(
        slug=slug,
        namespace=namespace,
        dir_name=dir_name,
        fleet_name=f"{slug}-barman-plugin",
        depends_on=depends_on
    )
