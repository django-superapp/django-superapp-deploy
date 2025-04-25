import os
from typing import Any, Dict, List, Optional

import yaml
from ilio import write

from ..base.component_types import Component
from ..base.constants import *
from ..base.utils import get_chart_path


def create_rancher(
    slug: str,
    namespace: str = 'cattle-system',
    hostname: str = None,
    replicas: int = 3,
    bootstrap_password: str = None,
    certificate_secret_name: str = None,
    ingress_class_name: str = 'nginx',
    extra_env_vars: Optional[List[Dict[str, str]]] = None,
    depends_on: Optional[List[Component]] = None
) -> Component:
    """
    Deploy Rancher using Helm.
    
    Args:
        slug: Unique identifier for the deployment
        namespace: Kubernetes namespace to deploy Rancher
        hostname: Hostname for Rancher UI access
        replicas: Number of Rancher server replicas
        bootstrap_password: Initial admin password
        certificate_secret_name: Name of the TLS secret for ingress (required)
        ingress_class_name: Ingress class to use
        extra_env_vars: Additional environment variables for Rancher
        depends_on: List of dependencies for Fleet
        
    Returns:
        Directory name where the configuration is generated
    """
    # Validate required parameters
    if not hostname:
        raise ValueError("hostname is required for Rancher deployment")
    
    if not certificate_secret_name:
        raise ValueError("certificate_secret_name is required for Rancher deployment")
    
    # Create directory structure
    dir_name = f"{slug}-rancher"
    output_dir = f'{GENERATED_SKAFFOLD_TMP_DIR}/{dir_name}'
    os.makedirs(output_dir, exist_ok=True)
    
    # Create values for Helm chart
    values = {
        "hostname": hostname,
        "replicas": replicas,
        "tls": "ingress",
        "ingress": {
            "ingressClassName": ingress_class_name,
            "tls": {
                "source": "secret",
                "secretName": certificate_secret_name
            }
        },
        "resources": {
            "limits": {
                "cpu": "1000m",
                "memory": "1Gi"
            },
            "requests": {
                "cpu": "250m",
                "memory": "750Mi"
            }
        },
        "auditLog": {
            "level": 0,
            "maxAge": 1,
            "maxBackup": 1,
            "maxSize": 100
        },
        "priorityClassName": "rancher-critical"
    }
    
    # Set bootstrap password if provided
    if bootstrap_password:
        values["bootstrapPassword"] = bootstrap_password
    
    # Add extra environment variables if provided
    if extra_env_vars:
        values["extraEnv"] = extra_env_vars
    
    # Generate values file for Helm chart
    values_yaml = yaml.dump(values, default_flow_style=False)
    write(f"{output_dir}/rancher-values.yaml", values_yaml)
    
    # Generate skaffold.yaml
    skaffold_config = {
        "apiVersion": "skaffold/v4beta13",
        "kind": "Config",
        "deploy": {
            "helm": {
                "flags": {
                    "template": [
                        "--kube-version=v1.31.7",
                    ]
                },
                "releases": [
                    {
                        "name": f"{slug}-rancher",
                        "chartPath": get_chart_path("./charts/rancher"),
                        "valuesFiles": [
                            f"./rancher-values.yaml"
                        ],
                        "namespace": namespace,
                        "createNamespace": True,
                        "wait": True,
                        "upgradeOnChange": True,
                    }
                ]
            }
        }
    }
    
    skaffold_yaml = yaml.dump(skaffold_config, default_flow_style=False)
    write(f"{output_dir}/skaffold-rancher.yaml", skaffold_yaml)
    
    # Generate fleet.yaml for dependencies
    fleet_config = {
        "namespace": namespace,
        "dependsOn": [
            c.as_fleet_dependency for c in depends_on
        ] if depends_on else [],
        "helm": {
            "releaseName": f"{slug}-rancher",
            "chart": "./deploy/components/rancher/charts/rancher",
            "values": f"./{dir_name}/rancher-values.yaml"
        }
    }
    
    if depends_on:
        fleet_config["dependsOn"] = depends_on
    
    fleet_yaml = yaml.dump(fleet_config, default_flow_style=False)
    write(f"{output_dir}/fleet.yaml", fleet_yaml)
    
    return Component(
        slug=slug,
        namespace=namespace,
        dir_name=dir_name,
        fleet_name=f"{slug}-rancher",
    )
