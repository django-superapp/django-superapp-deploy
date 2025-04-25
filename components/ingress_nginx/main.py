"""
Ingress NGINX Controller Component

This module provides functionality to deploy the NGINX ingress controller
which handles ingress traffic routing in Kubernetes.
"""
from typing import Any, List, Optional
import os

import yaml
from ilio import write

from ..base.component_types import Component
from ..base.constants import *
from ..base.utils import get_chart_path


def create_ingress_nginx(
        slug: str,
        namespace: str = 'ingress-nginx',
        metallb_address_pool: Optional[str] = None,
        depends_on: Optional[List[Component]] = None
) -> Component:
    """
    Deploy the NGINX ingress controller using Helm.
    
    Args:
        slug: Unique identifier for the deployment
        namespace: Kubernetes namespace to deploy the ingress controller
        metallb_address_pool: MetalLB address pool to use for the LoadBalancer service
        depends_on: List of dependencies for Fleet
        
    Returns:
        Directory name where the configuration is generated
    """
    # Create directory structure
    dir_name = f"{slug}-ingress-nginx"
    output_dir = f'{GENERATED_SKAFFOLD_TMP_DIR}/{dir_name}'
    os.makedirs(output_dir, exist_ok=True)

    # Generate Helm values for ingress-nginx
    ingress_nginx_values = {
        "controller": {
            "ingressClassResource": {
                "name": "nginx",
                "enabled": True,
                "default": True,
            },
            "service": {
                "type": "LoadBalancer",
                "externalTrafficPolicy": "Local",
                "annotations": {
                    "metallb.universe.tf/address-pool": metallb_address_pool
                } if metallb_address_pool else {},
            },
            "config": {
                "use-forwarded-headers": "true",
                "compute-full-forwarded-for": "true",
                "use-proxy-protocol": "false",
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
        },
        "defaultBackend": {
            "enabled": True,
            "resources": {
                "requests": {
                    "cpu": "10m",
                    "memory": "20Mi"
                },
                "limits": {
                    "cpu": "50m",
                    "memory": "50Mi"
                }
            },
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
                        "name": f"{slug}-ingress-nginx",
                        "namespace": namespace,
                        "chartPath": get_chart_path(f"./charts/ingress-nginx"),
                        "createNamespace": False,
                        "valuesFiles": [
                            "./ingress-nginx-values.yaml"
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
        "namespace": namespace,
        "dependsOn": [
            c.as_fleet_dependency for c in depends_on
        ] if depends_on else [],
        "labels": {
            "name": f"{slug}-ingress-nginx"
        },
        "diff": {}
    }

    # Write all configuration files
    write(f"{output_dir}/ingress-nginx-values.yaml", 
          yaml.dump(ingress_nginx_values, default_flow_style=False))
    
    write(f"{output_dir}/skaffold-ingress-nginx.yaml", 
          yaml.dump(skaffold_config, default_flow_style=False))
    
    write(f"{output_dir}/fleet.yaml", 
          yaml.dump(fleet_config, default_flow_style=False))

    return Component(
        slug=slug,
        namespace=namespace,
        dir_name=dir_name,
        fleet_name=f"{slug}-ingress-nginx"
    )
