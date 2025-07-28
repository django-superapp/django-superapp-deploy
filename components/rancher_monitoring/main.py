"""
Rancher Monitoring Component

This module provides functionality to deploy the Rancher Monitoring stack
which includes Prometheus, Grafana, Alertmanager and monitoring infrastructure.
"""

import os
import yaml
from typing import List, Optional, TypedDict
from ilio import write

from ..base.component_types import Component
from ..base.constants import *
from ..base.utils import get_chart_path


class MonitoringConfig(TypedDict):
    """Configuration for Rancher Monitoring deployment"""
    storage_class: str
    prometheus_storage_size: str
    grafana_storage_size: str
    alertmanager_storage_size: str


def create_rancher_monitoring(
        slug: str,
        monitoring_config: MonitoringConfig,
        namespace: str = 'cattle-monitoring-system',
        depends_on: Optional[List[Component]] = None
) -> Component:
    """
    Deploy the Rancher Monitoring stack using Helm.

    Args:
        slug: Unique identifier for the deployment
        monitoring_config: Configuration for monitoring stack storage and resources
        namespace: Kubernetes namespace to deploy monitoring stack
        depends_on: List of dependencies for Fleet

    Returns:
        Component instance for tracking dependencies
    """
    # Create directory structure
    dir_name = f"{slug}-rancher-monitoring"
    output_dir = f'{GENERATED_SKAFFOLD_TMP_DIR}/{dir_name}'
    os.makedirs(output_dir, exist_ok=True)

    # Get configurable values from CONFIG with defaults
    storage_class = monitoring_config.get('storage_class', 'longhorn')
    prometheus_storage_size = monitoring_config.get('prometheus_storage_size', '50Gi')
    grafana_storage_size = monitoring_config.get('grafana_storage_size', '10Gi')
    alertmanager_storage_size = monitoring_config.get('alertmanager_storage_size', '5Gi')

    # Generate Helm values for rancher-monitoring
    monitoring_values = {
        "global": {
            "cattle": {
                "clusterId": "local",
                "clusterName": "local",
                "systemDefaultRegistry": ""
            }
        },
        "prometheus": {
            "prometheusSpec": {
                "retention": "12h",
                "resources": {
                    "limits": {
                        "cpu": "1000m",
                        "memory": "3000Mi"
                    },
                    "requests": {
                        "cpu": "750m",
                        "memory": "750Mi"
                    }
                },
                "storageSpec": {
                    "volumeClaimTemplate": {
                        "spec": {
                            "accessModes": ["ReadWriteOnce"],
                            "resources": {
                                "requests": {
                                    "storage": prometheus_storage_size
                                }
                            },
                            "storageClassName": storage_class
                        }
                    }
                }
            }
        },
        "grafana": {
            "persistence": {
                "enabled": True,
                "storageClassName": storage_class,
                "size": grafana_storage_size
            },
            "resources": {
                "limits": {
                    "cpu": "200m",
                    "memory": "200Mi"
                },
                "requests": {
                    "cpu": "100m",
                    "memory": "128Mi"
                }
            }
        },
        "alertmanager": {
            "alertmanagerSpec": {
                "storage": {
                    "volumeClaimTemplate": {
                        "spec": {
                            "accessModes": ["ReadWriteOnce"],
                            "resources": {
                                "requests": {
                                    "storage": alertmanager_storage_size
                                }
                            },
                            "storageClassName": storage_class
                        }
                    }
                }
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
                        "name": f"{slug}-rancher-monitoring",
                        "namespace": namespace,
                        "chartPath": get_chart_path("./charts/rancher-monitoring"),
                        "createNamespace": False,
                        "valuesFiles": [
                            "./rancher-monitoring-values.yaml"
                        ]
                    },
                ]
            }
        },
        "deploy": {
            "kubectl": {},
        },
    }

    # Generate Fleet configuration with webhook patches and Prometheus diff patch
    # These patches prevent Fleet from detecting changes in webhook configurations
    # and handle the automountServiceAccountToken modification
    fleet_config = {
        "dependsOn": [
            c.as_fleet_dependency for c in depends_on
        ] if depends_on else [],
        "helm": {
            "releaseName": f"{slug}-rancher-monitoring",
        },
        "labels": {
            "name": f"{slug}-rancher-monitoring",
        },
        "diff": {
            "comparePatches": [
                {
                    "apiVersion": "monitoring.coreos.com/v1",
                    "kind": "Prometheus",
                    "namespace": namespace,
                    "name": "rancher-monitoring-rancher-prometheus",
                    "operations": [
                        {"op": "remove", "path": "/spec/automountServiceAccountToken"}
                    ]
                }
            ]
        },
    }

    # Write all configuration files
    write(f"{output_dir}/rancher-monitoring-values.yaml",
          yaml.dump(monitoring_values, default_flow_style=False))

    write(f"{output_dir}/skaffold-rancher-monitoring.yaml",
          yaml.dump(skaffold_config, default_flow_style=False))

    write(f"{output_dir}/fleet.yaml",
          yaml.dump(fleet_config, default_flow_style=False))

    return Component(
        slug=slug,
        namespace=namespace,
        dir_name=dir_name,
        fleet_name=f"{slug}-rancher-monitoring",
        depends_on=depends_on
    )
