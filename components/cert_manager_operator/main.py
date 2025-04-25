"""
Certificate Manager Operator Component

This module provides functionality to deploy the cert-manager operator
which handles certificate issuance and management in Kubernetes.
"""
from importlib.metadata import requires
from typing import Any, List, Optional
import os

import yaml
from ilio import write

from ..base.component_types import Component
from ..base.constants import *
from ..base.utils import get_chart_path


def create_cert_manager_operator(
        slug: str,
        namespace: str = 'cert-manager',
        depends_on: Optional[List[Component]] = None
) -> Component:
    """
    Deploy the cert-manager operator using Helm.
    
    Args:
        slug: Unique identifier for the deployment
        namespace: Kubernetes namespace to deploy cert-manager
        depends_on: List of dependencies for Fleet
        
    Returns:
        Directory name where the configuration is generated
    """
    # Create directory structure
    dir_name = f"{slug}-cert-manager-operator"
    output_dir = f'{GENERATED_SKAFFOLD_TMP_DIR}/{dir_name}'
    os.makedirs(output_dir, exist_ok=True)

    # Generate Helm values for cert-manager
    cert_manager_values = {
        "installCRDs": True,
        "dns01RecursiveNameserversOnly": True,
        "dns01RecursiveNameservers": "1.1.1.1:53,8.8.8.8:53",
        # Commented out proxy settings - preserved for future use
        # "http_proxy": HTTP_PROXY_WITH_CREDENTIALS if HTTP_PROXY_ENABLED else None,
        # "https_proxy": HTTP_PROXY_WITH_CREDENTIALS if HTTP_PROXY_ENABLED else None,
        # "no_proxy": HTTP_NO_PROXY if HTTP_PROXY_ENABLED else None,
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
                        "name": f"{slug}-cert-manager-operator",
                        "namespace": namespace,
                        "chartPath": get_chart_path("./charts/cert-manager"),
                        "createNamespace": False,
                        "valuesFiles": [
                            "./cert-manager-values.yaml"
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
    
    # Generate Fleet configuration with webhook patches
    # These patches prevent Fleet from detecting changes in webhook configurations
    fleet_config = {
        "namespace": namespace,
        "dependsOn": [
            c.as_fleet_dependency for c in depends_on
        ] if depends_on else [],
        "labels": {
            "name": f"{slug}-cert-manager-operator"
        },
        "diff": {
            "comparePatches": [
                {
                    "apiVersion": "admissionregistration.k8s.io/v1",
                    "kind": "MutatingWebhookConfiguration",
                    "name": "cert-manager-webhook",
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
                    "name": "cert-manager-webhook",
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
    write(f"{output_dir}/cert-manager-values.yaml", 
          yaml.dump(cert_manager_values, default_flow_style=False))
    
    write(f"{output_dir}/skaffold-cert-manager-operator.yaml", 
          yaml.dump(skaffold_config, default_flow_style=False))
    
    write(f"{output_dir}/fleet.yaml", 
          yaml.dump(fleet_config, default_flow_style=False))

    return Component(
        slug=slug,
        namespace=namespace,
        dir_name=dir_name,
        fleet_name=f"{slug}-cert-manager-operator"
    )
