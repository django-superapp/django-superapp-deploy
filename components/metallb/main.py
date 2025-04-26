import os
from typing import Any, Dict, List, Optional

import yaml
from ilio import write

from ..base.component_types import Component
from ..base.constants import *
from ..base.utils import get_chart_path


def create_metallb(
    slug: str,
    namespace: str = 'metallb-system',
    address_pools: Optional[List[Dict[str, Any]]] = None,
    depends_on: Optional[List[Component]] = None
) -> Component:
    """
    Deploy MetalLB using Helm.
    
    Args:
        slug: Unique identifier for the deployment
        namespace: Kubernetes namespace to deploy MetalLB
        address_pools: List of address pools configurations
        depends_on: List of dependencies for Fleet
        
    Returns:
        Directory name where the configuration is generated
    """
    # Create directory structure
    dir_name = f"{slug}-metallb"
    output_dir = f'{GENERATED_SKAFFOLD_TMP_DIR}/{dir_name}'
    os.makedirs(output_dir, exist_ok=True)
    
    # Create values for Helm chart, using only values that exist in the chart's values.yaml
    values = {
        "crds": {
            "enabled": True
        },
        "prometheus": {
            "serviceMonitor": {
                "enabled": False
            }
        },
        "controller": {
            "resources": {
                "limits": {
                    "cpu": "100m",
                    "memory": "100Mi"
                },
                "requests": {
                    "cpu": "50m",
                    "memory": "50Mi"
                }
            }
        },
        "speaker": {
            "resources": {
                "limits": {
                    "cpu": "100m",
                    "memory": "100Mi"
                },
                "requests": {
                    "cpu": "50m",
                    "memory": "50Mi"
                }
            },
            "tolerateMaster": True
        }
    }
    
    # Generate values file for Helm chart
    values_yaml = yaml.dump(values, default_flow_style=False)
    write(f"{output_dir}/metallb-values.yaml", values_yaml)
    
    # Generate skaffold.yaml
    skaffold_config = {
        "apiVersion": "skaffold/v3",
        "kind": "Config",
        "manifests": {
            "helm": {
                "releases": [
                    {
                        "name": f"{slug}-metallb",
                        "chartPath": get_chart_path("./charts/metallb"),
                        "valuesFiles": [
                            f"./metallb-values.yaml"
                        ],
                        "namespace": namespace,
                        "createNamespace": True,
                        "wait": True,
                        "upgradeOnChange": True
                    }
                ]
            }
        },
        "deploy": {
            "kubectl": {
                "defaultNamespace": namespace
            }
        }
    }
    
    # Create address pool manifests if provided
    if address_pools:
        manifests_dir = f"{output_dir}/manifests"
        os.makedirs(manifests_dir, exist_ok=True)
        
        for i, pool in enumerate(address_pools):
            pool_name = pool.get("name", f"pool-{i}")
            addresses = pool.get("addresses", [])
            
            ip_address_pool = {
                "apiVersion": "metallb.io/v1beta1",
                "kind": "IPAddressPool",
                "metadata": {
                    "name": pool_name,
                    "namespace": namespace
                },
                "spec": {
                    "addresses": addresses
                }
            }
            
            # Add auto-assign if specified
            if "autoAssign" in pool:
                ip_address_pool["spec"]["autoAssign"] = pool["autoAssign"]
            
            # Add avoid buggy IPs if specified
            if "avoidBuggyIPs" in pool:
                ip_address_pool["spec"]["avoidBuggyIPs"] = pool["avoidBuggyIPs"]
            
            pool_yaml = yaml.dump(ip_address_pool, default_flow_style=False)
            write(f"{manifests_dir}/ipaddresspool-{pool_name}.yaml", pool_yaml)
            
            # Create L2Advertisement for this pool
            l2_advertisement = {
                "apiVersion": "metallb.io/v1beta1",
                "kind": "L2Advertisement",
                "metadata": {
                    "name": f"l2-{pool_name}",
                    "namespace": namespace
                },
                "spec": {
                    "ipAddressPools": [pool_name]
                }
            }
            
            l2_yaml = yaml.dump(l2_advertisement, default_flow_style=False)
            write(f"{manifests_dir}/l2advertisement-{pool_name}.yaml", l2_yaml)
        
        # Add manifests to skaffold config using rawYaml
        if "manifests" not in skaffold_config:
            skaffold_config["manifests"] = {}
        
        skaffold_config["manifests"]["rawYaml"] = [
            "./manifests/*.yaml"
        ]
    
    skaffold_yaml = yaml.dump(skaffold_config, default_flow_style=False)
    write(f"{output_dir}/skaffold-metallb.yaml", skaffold_yaml)
    
    # Generate fleet.yaml for dependencies
    fleet_config = {
        "dependsOn": [
            c.as_fleet_dependency for c in depends_on
        ] if depends_on else [],
        "helm": {
            "helm": {
            "releaseName": f"{slug}-metallb",
        },
            "chart": "./deploy/components/metallb/charts/metallb",
            "values": f"./{dir_name}/metallb-values.yaml"
        }
    }

    fleet_yaml = yaml.dump(fleet_config, default_flow_style=False)
    write(f"{output_dir}/fleet.yaml", fleet_yaml)

    return Component(
        slug=slug,
        namespace=namespace,
        dir_name=dir_name,
        fleet_name=f"{slug}-metallb",
    )
