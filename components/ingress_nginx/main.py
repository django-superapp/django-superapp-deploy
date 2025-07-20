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
        replicas: int = 3,
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
            "replicaCount": replicas,
            "ingressClassResource": {
                "name": "nginx",
                "enabled": True,
                "default": True,
            },
            "service": {
                "type": "LoadBalancer",
                # "externalTrafficPolicy": "Local",
                "annotations": {
                    "metallb.universe.tf/address-pool": metallb_address_pool
                } if metallb_address_pool else {},
            },
            "config": {
                # "log-level": "debug",
                # "error-log-level": "debug",
                # "use-forwarded-headers": "false",
                # "compute-full-forwarded-for": "true",
                # "use-proxy-protocol": "false",

                # Enable compression
                "use-gzip": "true",
                "gzip-level": "6",
                "gzip-types": "application/atom+xml application/javascript application/x-javascript application/json application/rss+xml application/vnd.ms-fontobject application/x-font-ttf application/x-web-app-manifest+json application/xhtml+xml application/xml font/opentype image/svg+xml image/x-icon text/css text/javascript text/plain text/x-component",

                # Enable brotli compression
                "use-brotli": "true",
                "brotli-level": "6",
                "brotli-types": "application/atom+xml application/javascript application/x-javascript application/json application/rss+xml application/vnd.ms-fontobject application/x-font-ttf application/x-web-app-manifest+json application/xhtml+xml application/xml font/opentype image/svg+xml image/x-icon text/css text/javascript text/plain text/x-component",

                # Enable zstd compression
                "use-zstd": "true",
                "zstd-level": "3",
                "zstd-types": "application/atom+xml application/javascript application/x-javascript application/json application/rss+xml application/vnd.ms-fontobject application/x-font-ttf application/x-web-app-manifest+json application/xhtml+xml application/xml font/opentype image/svg+xml image/x-icon text/css text/javascript text/plain text/x-component",

                # Enable HTTP/2
                "use-http2": "true",

                # Enable HTTP/3
                "use-http3": "true",
            },
            # "extraArgs": {
            #     "v": 5,
            # },
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
        "dependsOn": [
            c.as_fleet_dependency for c in depends_on
        ] if depends_on else [],
       "helm": {
            "releaseName": f"{slug}-ingress-nginx",
        },
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
