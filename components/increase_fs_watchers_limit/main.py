import os
from typing import Any, Dict, List, Optional

import yaml
from ilio import write

from ..base.component_types import Component
from ..base.constants import *


def create_increase_fs_watchers_limit(
    slug: str,
    namespace: str,
    max_user_watches: int = 2099999999,
    max_user_instances: int = 2099999999,
    max_queued_events: int = 2099999999,
    depends_on: Optional[List[Component]] = None
) -> Component:
    """
    Deploy a DaemonSet to increase file system watchers limit on all nodes.
    
    Args:
        slug: Unique identifier for the deployment
        namespace: Kubernetes namespace to deploy the DaemonSet
        max_user_watches: Maximum number of file watches per user
        max_user_instances: Maximum number of inotify instances per user
        max_queued_events: Maximum number of queued events per instance
        depends_on: List of dependencies for Fleet
        
    Returns:
        Directory name where the configuration is generated
    """
    # Create directory structure
    dir_name = f"{slug}-fs-watchers"
    output_dir = f'{GENERATED_SKAFFOLD_TMP_DIR}/{dir_name}'
    manifests_dir = f'{output_dir}/manifests'
    
    os.makedirs(output_dir, exist_ok=True)
    os.makedirs(manifests_dir, exist_ok=True)
    
    # Create DaemonSet manifest
    daemonset_manifest = {
        "apiVersion": "apps/v1",
        "kind": "DaemonSet",
        "metadata": {
            "name": "more-fs-watchers",
            "namespace": namespace,
            "labels": {
                "app": "more-fs-watchers",
                "k8s-app": "more-fs-watchers"
            }
        },
        "spec": {
            "selector": {
                "matchLabels": {
                    "k8s-app": "more-fs-watchers"
                }
            },
            "template": {
                "metadata": {
                    "labels": {
                        "name": "more-fs-watchers",
                        "k8s-app": "more-fs-watchers"
                    },
                    "annotations": {
                        "seccomp.security.alpha.kubernetes.io/defaultProfileName": "runtime/default",
                        "apparmor.security.beta.kubernetes.io/defaultProfileName": "runtime/default"
                    }
                },
                "spec": {
                    "nodeSelector": {
                        "kubernetes.io/os": "linux"
                    },
                    "initContainers": [
                        {
                            "name": "sysctl",
                            "image": "alpine:3",
                            "command": [
                                "/bin/sh",
                                "-c",
                                f"sysctl -w fs.inotify.max_user_watches={max_user_watches} && "
                                f"sysctl -w fs.inotify.max_user_instances={max_user_instances} && "
                                f"sysctl -w fs.inotify.max_queued_events={max_queued_events}"
                            ],
                            "resources": {
                                "requests": {
                                    "cpu": "10m",
                                    "memory": "10Mi"
                                },
                                "limits": {
                                    "cpu": "50m",
                                    "memory": "50Mi"
                                }
                            },
                            "securityContext": {
                                "runAsUser": 0,
                                "privileged": True,
                                "readOnlyRootFilesystem": True,
                                "capabilities": {
                                    "drop": [
                                        "ALL"
                                    ]
                                }
                            }
                        }
                    ],
                    "containers": [
                        {
                            "name": "pause",
                            "image": "k8s.gcr.io/pause:3.5",
                            "command": [
                                "/pause"
                            ],
                            "resources": {
                                "requests": {
                                    "cpu": "10m",
                                    "memory": "1Mi"
                                },
                                "limits": {
                                    "cpu": "50m",
                                    "memory": "5Mi"
                                }
                            },
                            "securityContext": {
                                "runAsNonRoot": True,
                                "runAsUser": 65535,
                                "allowPrivilegeEscalation": False,
                                "privileged": False,
                                "readOnlyRootFilesystem": True,
                                "capabilities": {
                                    "drop": [
                                        "ALL"
                                    ]
                                }
                            }
                        }
                    ],
                    "terminationGracePeriodSeconds": 5
                }
            }
        }
    }
    
    # Write DaemonSet manifest
    write(f"{manifests_dir}/increase-fs-watchers-limit.yaml", 
          yaml.dump(daemonset_manifest, default_flow_style=False))
    
    # Generate skaffold.yaml
    skaffold_config = {
        "apiVersion": "skaffold/v3",
        "kind": "Config",
        "requires": [
            c.as_skaffold_dependency for c in depends_on
        ] if depends_on else [],
        "manifests": {
            "rawYaml": [
                "./manifests/increase-fs-watchers-limit.yaml",
            ],
        },
        "deploy": {
            "kubectl": {
                "defaultNamespace": namespace,
            },
        },
    }
    
    skaffold_yaml = yaml.dump(skaffold_config, default_flow_style=False)
    write(f"{output_dir}/skaffold-fs-watchers.yaml", skaffold_yaml)
    
    # Generate fleet.yaml for dependencies
    fleet_config = {
        "namespace": namespace,
        "dependsOn": [
            c.as_fleet_dependency for c in depends_on
        ] if depends_on else [],
        "labels": {
            "name": f"{slug}-fs-watchers"
        },
    }
    
    fleet_yaml = yaml.dump(fleet_config, default_flow_style=False)
    write(f"{output_dir}/fleet.yaml", fleet_yaml)

    return Component(
        slug=slug,
        namespace=namespace,
        dir_name=dir_name,
        fleet_name=f"{slug}-fs-watchers"
    )
