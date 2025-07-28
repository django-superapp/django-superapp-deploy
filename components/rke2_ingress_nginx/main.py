"""
Ingress NGINX Controller Component

This module provides functionality to deploy the NGINX ingress controller
which handles ingress traffic routing in Kubernetes using a HelmChartConfig.
"""
from typing import Dict, List, Optional, Any

from ilio import write

from ..base.component_types import Component
from ..base.constants import *


def create_rke2_ingress_nginx(
        slug: str,
        namespace: str = "kube-system",
        host_port_enabled: bool = False,
        service_type: str = "LoadBalancer",
        metallb_address_pool: Optional[str] = None,
        replicas: int = 3,
        resources: Optional[Dict[str, Any]] = None,
        extra_values: Optional[Dict[str, Any]] = None,
        depends_on: Optional[List[Component]] = None
) -> Component:
    """
    Configure NGINX ingress controller using HelmChartConfig.
    
    Args:
        slug: Unique identifier for the deployment
        namespace: Kubernetes namespace for the HelmChartConfig (usually kube-system)
        host_port_enabled: Whether to enable host ports
        service_type: Type of service (LoadBalancer, NodePort, etc.)
        metallb_address_pool: MetalLB address pool to use for the LoadBalancer service
        replicas: Number of controller replicas
        resources: Resource requests and limits
        extra_values: Additional values to include in the HelmChartConfig
        depends_on: List of dependencies for Fleet
        
    Returns:
        Component object with metadata about the deployment
    """
    # Create directory structure
    dir_name = f"{slug}-ingress-nginx"
    output_dir = f'{GENERATED_SKAFFOLD_TMP_DIR}/{dir_name}'
    os.makedirs(output_dir, exist_ok=True)
    
    # Default resources if not provided
    if resources is None:
        resources = {
            "requests": {
                "cpu": "100m",
                "memory": "128Mi"
            },
            "limits": {
                "cpu": "500m",
                "memory": "512Mi"
            }
        }
    
    # Generate service annotations
    service_annotations = {}
    if metallb_address_pool:
        service_annotations["metallb.universe.tf/address-pool"] = metallb_address_pool
    
    # Base controller values
    controller_values = {
        "hostPort": {
            "enabled": host_port_enabled
        },
        "service": {
            "enabled": True,
            "type": service_type,
            "annotations": service_annotations
        },
        "replicaCount": replicas,
        "resources": resources,
        "ingressClassResource": {
            "name": "nginx",
            "enabled": True,
            "default": True,
        }
    }
    
    # Merge with extra values if provided
    if extra_values:
        # Deep merge would be better, but this is a simple approach
        if "controller" in extra_values:
            for k, v in extra_values["controller"].items():
                controller_values[k] = v
    
    # Create the HelmChartConfig manifest
    helm_chart_config = {
        "apiVersion": "helm.cattle.io/v1",
        "kind": "HelmChartConfig",
        "metadata": {
            "name": "rke2-ingress-nginx",
            "namespace": namespace
        },
        "spec": {
            "valuesContent": yaml.dump({
                "controller": controller_values,
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
                    }
                },
                **(extra_values or {})
            }, default_flow_style=False)
        }
    }
    
    # Write the manifest to a file
    with open(f"{output_dir}/ingress-nginx-helmchartconfig.yaml", "w") as file:
        yaml.dump(helm_chart_config, file, default_flow_style=False)
    
    # Generate Skaffold configuration
    skaffold_config = {
        "apiVersion": "skaffold/v3",
        "kind": "Config",
        "manifests": {
            "rawYaml": [
                "./ingress-nginx-helmchartconfig.yaml"
            ]
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
            "name": f"{slug}-ingress-nginx"
        }
    }

    # Write configuration files
    write(f"{output_dir}/skaffold-ingress-nginx.yaml", 
          yaml.dump(skaffold_config, default_flow_style=False))
    
    write(f"{output_dir}/fleet.yaml", 
          yaml.dump(fleet_config, default_flow_style=False))

    return Component(
        slug=slug,
        namespace=namespace,
        dir_name=dir_name,
        fleet_name=f"{slug}-ingress-nginx",
        depends_on=depends_on
    )
