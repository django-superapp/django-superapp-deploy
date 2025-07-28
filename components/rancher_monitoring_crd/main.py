"""
Rancher Monitoring CRD Component

This module provides functionality to deploy the Rancher Monitoring CRDs
which provide the custom resource definitions needed for monitoring stack.
"""

import os
import yaml
from typing import List, Optional
from ilio import write

from ..base.component_types import Component
from ..base.constants import *


def create_rancher_monitoring_crd(
        slug: str,
        namespace: str = 'cattle-monitoring-system',
        depends_on: Optional[List[Component]] = None
) -> Component:
    """
    Deploy the Rancher Monitoring CRDs using Helm.

    Args:
        slug: Unique identifier for the deployment
        namespace: Kubernetes namespace to deploy monitoring CRDs
        depends_on: List of dependencies for Fleet

    Returns:
        Component instance for tracking dependencies
    """
    # Create directory structure
    dir_name = f"{slug}-rancher-monitoring-crd"
    output_dir = f'{GENERATED_SKAFFOLD_TMP_DIR}/{dir_name}'
    os.makedirs(output_dir, exist_ok=True)


    # No Skaffold configuration - Fleet only deployment

    # Generate Fleet configuration with Helm chart from Rancher repo
    fleet_config = {
        "defaultNamespace": namespace,
        "helm": {
            "releaseName": "rancher-monitoring-crd",
            "repo": "https://charts.rancher.io",
            "chart": "rancher-monitoring-crd",
            "version": "104.1.0+up57.0.3"
        },
        "dependsOn": [
            c.as_fleet_dependency for c in depends_on
        ] if depends_on else [],
        "labels": {
            "name": f"{slug}-rancher-monitoring-crd",
        }
    }

    # Write Fleet configuration file
    write(f"{output_dir}/fleet.yaml",
          yaml.dump(fleet_config, default_flow_style=False))

    return Component(
        slug=slug,
        namespace=namespace,
        dir_name=dir_name,
        fleet_name=f"{slug}-rancher-monitoring-crd",
        depends_on=depends_on
    )
