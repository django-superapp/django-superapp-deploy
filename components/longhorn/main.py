"""
Longhorn Storage Component

This module provides functionality to deploy the Longhorn distributed
storage system for Kubernetes.
"""
from typing import Any, Dict, List, Optional, Union, TypedDict, Literal
import os

import yaml
from ilio import write

from ..base.component_types import Component
from ..base.constants import *
from ..base.utils import get_chart_path


class LonghornDisk(TypedDict, total=False):
    """Configuration for a Longhorn disk."""
    name: str  # Required name for the disk
    node_selector: Dict[str, str]
    disk_id: str  # Disk ID from /dev/disk/by-id/ for stable identification (required)
    tags: List[str]
    allow_scheduling: bool


class LonghornStorageClass(TypedDict, total=False):
    """Configuration for a Longhorn storage class."""
    name: str
    replica_count: int
    disk_selector: List[str]
    node_selector: List[str]
    is_default: bool
    reclaim_policy: Literal["Delete", "Retain"]
    fs_type: str

def generate_disk_setup_script(disks: List[LonghornDisk]) -> str:
    """
    Generate a bash script to set up disks with LVM.
    
    Args:
        disks: List of disk configurations
        
    Returns:
        Bash script as a string
    """
    # Create a script that will run on each node to set up disks with LVM
    setup_script = """#!/bin/bash
set -e

# Function to set up a disk with LVM
setup_disk() {
    local disk_id="$1"
    local disk_name="$2"
    local mount_path="/var/lib/longhorn/disks/$disk_name"
    local vg_name="longhorn_$disk_name"
    local lv_name="data"
    
    echo "Setting up disk $disk_name using /dev/disk/by-id/$disk_id"
    
    # List all available disks for debugging
    echo "Available disks in /dev/disk/by-id/:"
    ls -la /dev/disk/by-id/
    
    # Check if disk exists
    if [ ! -e "/dev/disk/by-id/$disk_id" ]; then
        echo "Error: Disk /dev/disk/by-id/$disk_id not found"
        return 1
    fi
    
    # Create mount directory
    mkdir -p "$mount_path"
    
    # Check if already mounted
    if mount | grep -q "$mount_path"; then
        echo "Disk already mounted at $mount_path"
        return 0
    fi
    
    # Check if LVM tools are installed in the host
    if ! chroot /host command -v pvcreate &> /dev/null || ! chroot /host command -v vgcreate &> /dev/null; then
        echo "Installing LVM tools on the host..."
        chroot /host apt-get update && chroot /host apt-get install -y lvm2
    fi
    
    # Check if volume group already exists
    if chroot /host vgs | grep -q "$vg_name"; then
        echo "Volume group $vg_name already exists"
    else
        # Create physical volume with force to automatically accept any prompts
        echo "Creating physical volume on /dev/disk/by-id/$disk_id"
        chroot /host pvcreate -f "/dev/disk/by-id/$disk_id"
        
        # Create volume group with force to automatically accept any prompts
        echo "Creating volume group $vg_name"
        chroot /host vgcreate -f "$vg_name" "/dev/disk/by-id/$disk_id"
    fi
    
    # Check if logical volume already exists
    if chroot /host lvs | grep -q "$vg_name/$lv_name"; then
        echo "Logical volume $vg_name/$lv_name already exists"
    else
        # Create logical volume using 100% of the volume group
        echo "Creating logical volume $lv_name in $vg_name"
        chroot /host lvcreate -l 100%FREE -n "$lv_name" "$vg_name"
        
        # Format the logical volume with ext4
        echo "Formatting logical volume with ext4"
        chroot /host mkfs.ext4 "/dev/$vg_name/$lv_name"
    fi
    
    # Add to fstab if not already there
    if ! grep -q "$mount_path" /etc/fstab; then
        echo "Adding logical volume to fstab"
        echo "/dev/$vg_name/$lv_name $mount_path ext4 defaults 0 0" >> /etc/fstab
    fi
    
    # Reload systemd to recognize new fstab entries
    echo "Reloading systemd daemon"
    chroot /host systemctl daemon-reload
    
    # Mount the logical volume and all entries in fstab
    echo "Mounting logical volume to $mount_path"
    chroot /host mount "/dev/$vg_name/$lv_name" "$mount_path"
    chroot /host mount -a
    
    # Set permissions
    chroot /host chown -R 1000:1000 "$mount_path"
    chroot /host chmod 700 "$mount_path"
    
    echo "Disk $disk_name successfully set up at $mount_path using LVM"
}

# Get hostname from the host
HOSTNAME=$(chroot /host hostname)

# Process each disk based on node selector
"""
    
    # Add disk setup commands for each node
    for disk in disks:
        disk_name = disk["name"]
        disk_id = disk["disk_id"]
        node_selector = disk.get("node_selector", {})
        
        # Create a condition to check if this is the right node
        node_condition = ""
        for key, value in node_selector.items():
            if key == "kubernetes.io/hostname":
                node_condition = f'if [ "$HOSTNAME" = "{value}" ]; then'
                break
        
        if node_condition:
            setup_script += f"""
{node_condition}
    echo "Setting up disk {disk_name} on node {list(node_selector.values())[0]}"
    setup_disk "{disk_id}" "{disk_name}"
fi
"""
    
    return setup_script


def generate_disk_setup_daemonset(slug: str, namespace: str, disks: List[LonghornDisk]) -> Dict[str, Any]:
    """
    Generate a DaemonSet to mount disks and configure fstab.
    
    Args:
        slug: Unique identifier for the deployment
        namespace: Kubernetes namespace
        disks: List of disk configurations
        
    Returns:
        DaemonSet manifest
    """
    # Generate the setup script
    setup_script = generate_disk_setup_script(disks)
    
    # Create ConfigMap for the setup script
    config_map = {
        "apiVersion": "v1",
        "kind": "ConfigMap",
        "metadata": {
            "name": f"{slug}-disk-setup-script",
            "namespace": namespace
        },
        "data": {
            "setup.sh": setup_script
        }
    }
    
    # Create the DaemonSet manifest
    daemonset = {
        "apiVersion": "apps/v1",
        "kind": "DaemonSet",
        "metadata": {
            "name": f"{slug}-disk-setup",
            "namespace": namespace,
            "labels": {
                "app": f"{slug}-disk-setup"
            }
        },
        "spec": {
            "selector": {
                "matchLabels": {
                    "app": f"{slug}-disk-setup"
                }
            },
            "template": {
                "metadata": {
                    "labels": {
                        "app": f"{slug}-disk-setup"
                    }
                },
                "spec": {
                    "hostPID": True,
                    "hostIPC": True,
                    "hostNetwork": True,
                    "initContainers": [
                        {
                            "name": "disk-setup-init",
                            "image": "ubuntu:22.04",
                            "command": ["/bin/sh", "-c"],
                            "args": [
                                "cp /scripts/setup.sh /tmp/setup.sh && chmod +x /tmp/setup.sh && echo 'Running disk setup script...' && /tmp/setup.sh && echo 'Setup complete.'"
                            ],
                            "securityContext": {
                                "privileged": True,
                                "runAsUser": 0,
                                "runAsGroup": 0
                            },
                            "volumeMounts": [
                                {
                                    "name": "host",
                                    "mountPath": "/host"
                                },
                                {
                                    "name": "dev",
                                    "mountPath": "/dev"
                                },
                                {
                                    "name": "longhorn-dir",
                                    "mountPath": "/var/lib/longhorn"
                                },
                                {
                                    "name": "etc",
                                    "mountPath": "/etc"
                                },
                                {
                                    "name": "setup-script",
                                    "mountPath": "/scripts"
                                }
                            ]
                        }
                    ],
                    "containers": [
                        {
                            "name": "disk-setup-shell",
                            "image": "ubuntu:22.04",
                            "command": ["/bin/sh", "-c"],
                            "args": [
                                "echo 'Container is running. Use kubectl exec to run bash commands.' && sleep infinity"
                            ],
                            "securityContext": {
                                "privileged": True,
                                "runAsUser": 0,
                                "runAsGroup": 0
                            },
                            "volumeMounts": [
                                {
                                    "name": "host",
                                    "mountPath": "/host"
                                },
                                {
                                    "name": "dev",
                                    "mountPath": "/dev"
                                },
                                {
                                    "name": "longhorn-dir",
                                    "mountPath": "/var/lib/longhorn"
                                },
                                {
                                    "name": "etc",
                                    "mountPath": "/etc"
                                },
                                {
                                    "name": "setup-script",
                                    "mountPath": "/scripts"
                                }
                            ]
                        }
                    ],
                    "volumes": [
                        {
                            "name": "host",
                            "hostPath": {
                                "path": "/"
                            }
                        },
                        {
                            "name": "dev",
                            "hostPath": {
                                "path": "/dev"
                            }
                        },
                        {
                            "name": "longhorn-dir",
                            "hostPath": {
                                "path": "/var/lib/longhorn"
                            }
                        },
                        {
                            "name": "etc",
                            "hostPath": {
                                "path": "/etc"
                            }
                        },
                        {
                            "name": "setup-script",
                            "configMap": {
                                "name": f"{slug}-disk-setup-script",
                                "defaultMode": 0o755
                            }
                        }
                    ],
                    "tolerations": [
                        {
                            "key": "node-role.kubernetes.io/master",
                            "operator": "Exists",
                            "effect": "NoSchedule"
                        },
                        {
                            "key": "node-role.kubernetes.io/control-plane",
                            "operator": "Exists",
                            "effect": "NoSchedule"
                        }
                    ]
                }
            }
        }
    }
    
    return daemonset, config_map


def generate_longhorn_node_patch(node_name: str, namespace: str, node_disks: List[LonghornDisk]) -> Dict[str, Any]:
    """
    Generate a Longhorn Node patch to configure disks.
    
    Args:
        node_name: Name of the Kubernetes node
        namespace: Kubernetes namespace
        node_disks: List of disk configurations for this node
        
    Returns:
        Longhorn Node patch manifest
    """
    # Create the Node patch with empty disks
    node_patch = {
        "apiVersion": "longhorn.io/v1beta2",
        "kind": "Node",
        "metadata": {
            "name": node_name,
            "namespace": namespace,
            "labels": {
                "node": node_name
            }
        },
        "spec": {
            "disks": {}
        }
    }
    
    # Add each disk to the node patch
    for disk in node_disks:
        disk_name = disk["name"]
        path = f"/var/lib/longhorn/disks/{disk_name}"
        tags = disk.get("tags", [])
        allow_scheduling = disk.get("allow_scheduling", True)
        
        # Add disk to the node patch using disk name as the key
        node_patch["spec"]["disks"][disk_name] = {
            "path": path,
            "allowScheduling": allow_scheduling,
            "tags": tags,
            "storageReserved": 50 * 1024 * 1024 * 1024,  # Reserve 50GB in bytes
            "diskType": "filesystem"
        }
    
    return node_patch


def generate_storage_class_manifest(sc: LonghornStorageClass, namespace: str) -> Dict[str, Any]:
    """
    Generate a Kubernetes StorageClass manifest for Longhorn.
    
    Args:
        sc: Storage class configuration
        namespace: Kubernetes namespace
        
    Returns:
        StorageClass manifest
    """
    name = sc.get("name", "longhorn")
    replica_count = sc.get("replica_count", 3)
    disk_selector = sc.get("disk_selector", [])
    node_selector = sc.get("node_selector", [])
    is_default = sc.get("is_default", False)
    reclaim_policy = sc.get("reclaim_policy", "Delete")
    fs_type = sc.get("fs_type", "ext4")
    
    # Create the StorageClass manifest
    storage_class = {
        "apiVersion": "storage.k8s.io/v1",
        "kind": "StorageClass",
        "metadata": {
            "name": name,
            "annotations": {}
        },
        "provisioner": "driver.longhorn.io",
        "parameters": {
            "numberOfReplicas": str(replica_count),
            "staleReplicaTimeout": "30",
            "fromBackup": "",
            "fsType": fs_type
        },
        "reclaimPolicy": reclaim_policy,
        "allowVolumeExpansion": True
    }
    
    # Add selectors if provided
    if disk_selector:
        storage_class["parameters"]["diskSelector"] = ",".join(disk_selector)
    
    if node_selector:
        storage_class["parameters"]["nodeSelector"] = ",".join(node_selector)
    
    # Set as default storage class if specified
    if is_default:
        storage_class["metadata"]["annotations"]["storageclass.kubernetes.io/is-default-class"] = "true"
    
    return storage_class


def create_longhorn(
        slug: str,
        namespace: str = 'longhorn-system',
        ingress_enabled: bool = False,
        ingress_host: Optional[str] = None,
        ingress_tls_secret: Optional[str] = None,
        ingress_class_name: str = 'nginx',
        disks: Optional[List[LonghornDisk]] = None,
        storage_classes: Optional[List[LonghornStorageClass]] = None,
        depends_on: Optional[List[Component]] = None
) -> Component:
    """
    Deploy the Longhorn storage system using Helm.
    
    Args:
        slug: Unique identifier for the deployment
        namespace: Kubernetes namespace to deploy Longhorn
        ingress_enabled: Whether to enable the Longhorn UI ingress
        ingress_host: Hostname for the Longhorn UI ingress
        ingress_tls_secret: Name of the TLS secret for the ingress
        ingress_class_name: Ingress class to use
        disks: List of LonghornDisk configurations to add to Longhorn nodes
        storage_classes: List of LonghornStorageClass configurations
        depends_on: List of dependencies for Fleet
        
    Returns:
        Directory name where the configuration is generated
    """
    # Validate required parameters if ingress is enabled
    if ingress_enabled and not ingress_host:
        raise ValueError("ingress_host is required when ingress_enabled is True")
        
    # Initialize disks and storage classes if not provided
    disks = disks or []
    storage_classes = storage_classes or []
    # Create directory structure
    dir_name = f"{slug}-longhorn"
    output_dir = f'{GENERATED_SKAFFOLD_TMP_DIR}/{dir_name}'
    os.makedirs(output_dir, exist_ok=True)

    # Generate Helm values for Longhorn
    longhorn_values = {
        "persistence": {
            "enabled": False,  # Disable default persistence to use our custom configuration
            "defaultClass": len(storage_classes) == 0,  # Only true if no custom storage classes
            "defaultClassReplicaCount": 3,
        },
        "defaultSettings": {
            "defaultReplicaCount": 3,
            "backupstorePollInterval": 300,
            "defaultDataPath": "/var/lib/longhorn/",
            "replicaDiskSoftAntiAffinity": "false",
            "replicaSoftAntiAffinity": "true",
            "replicaAutoBalance": "least-effort",
            "storageOverProvisioningPercentage": 200,
            "storageMinimalAvailablePercentage": 10,
            "guaranteedEngineManagerCPU": 12,
            "guaranteedReplicaManagerCPU": 12,
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
        "csi": {
            "attacherReplicaCount": 3,
            "provisionerReplicaCount": 3,
            "resizerReplicaCount": 3,
            "snapshotterReplicaCount": 3
        },
        "longhornManager": {
            "priorityClass": "system-cluster-critical"
        },
        "longhornDriver": {
            "priorityClass": "system-node-critical"
        }
    }
    
    # Configure ingress if enabled
    if ingress_enabled:
        longhorn_values["ingress"] = {
            "enabled": True,
            "host": ingress_host,
            "ingressClassName": ingress_class_name
        }
        
        # Add TLS configuration if a secret is provided
        if ingress_tls_secret:
            longhorn_values["ingress"]["tls"] = True
            longhorn_values["ingress"]["tlsSecret"] = ingress_tls_secret
    
    # Generate Skaffold configuration
    skaffold_config = {
        "apiVersion": "skaffold/v3",
        "kind": "Config",
        "requires": [
            c.as_skaffold_dependency for c in depends_on
        ] if depends_on else [],
        "build": {
            **SKAFFOLD_DEFAULT_BUILD,
            "artifacts": [],
        },
        "manifests": {
            "helm": {
                "releases": [
                    {
                        "name": f"{slug}-longhorn",
                        "namespace": namespace,
                        "chartPath": get_chart_path(f"./charts/longhorn"),
                        "createNamespace": True,
                        "valuesFiles": [
                            "./longhorn-values.yaml"
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
            "name": f"{slug}-longhorn"
        },
        "diff": {
            "comparePatches": [
                {
                    "apiVersion": "apps/v1",
                    "kind": "Deployment",
                    "jsonPointers": [
                        "/metadata/resourceVersion",
                        "/metadata/uid"
                    ]
                },
                {
                    "apiVersion": "apps/v1",
                    "kind": "DaemonSet",
                    "jsonPointers": [
                        "/metadata/resourceVersion",
                        "/metadata/uid"
                    ]
                },
                {
                    "apiVersion": "v1",
                    "kind": "Service",
                    "jsonPointers": [
                        "/metadata/resourceVersion",
                        "/metadata/uid",
                        "/spec/clusterIP",
                        "/spec/clusterIPs"
                    ]
                },
                {
                    "apiVersion": "longhorn.io/v1beta2",
                    "kind": "Node",
                    "jsonPointers": [
                        "/metadata/resourceVersion",
                        "/metadata/uid",
                        "/metadata/generation"
                    ]
                }
            ]
        }
    }
    
    # Generate storage class configurations if provided
    if storage_classes:
        longhorn_values["persistence"]["storageClassDevices"] = []
        
        for sc in storage_classes:
            name = sc.get("name", f"longhorn-{slug}")
            replica_count = sc.get("replica_count", 3)
            disk_selector = sc.get("disk_selector", [])
            node_selector = sc.get("node_selector", [])
            is_default = sc.get("is_default", False)
            reclaim_policy = sc.get("reclaim_policy", "Delete")
            fs_type = sc.get("fs_type", "ext4")
            
            # Add the storage class configuration
            storage_class_config = {
                "name": name,
                "replicaCount": replica_count,
                "default": is_default,
                "reclaimPolicy": reclaim_policy,
                "fsType": fs_type
            }
            
            # Add selectors if provided
            if disk_selector:
                storage_class_config["diskSelector"] = ",".join(disk_selector)
            
            if node_selector:
                storage_class_config["nodeSelector"] = ",".join(node_selector)
                
            longhorn_values["persistence"]["storageClassDevices"].append(storage_class_config)

    # Create custom manifests for disk configuration and storage classes
    if disks:
        # Validate disk configurations
        for disk in disks:
            if "name" not in disk:
                raise ValueError("Each disk configuration must have a 'name' field")
            if "disk_id" not in disk:
                raise ValueError(f"Disk {disk['name']} must have a 'disk_id' field for identification (from /dev/disk/by-id/)")
            if "node_selector" not in disk:
                print(f"Warning: Disk {disk['name']} does not have a 'node_selector' field, disk setup may fail")
        
        # Create a DaemonSet and ConfigMap to mount disks and configure fstab
        disk_setup_daemonset, disk_setup_configmap = generate_disk_setup_daemonset(slug, namespace, disks)
        
        # Write the DaemonSet and ConfigMap to files
        write(f"{output_dir}/disk-setup-daemonset.yaml", 
              yaml.dump(disk_setup_daemonset, default_flow_style=False))
        
        write(f"{output_dir}/disk-setup-configmap.yaml", 
              yaml.dump(disk_setup_configmap, default_flow_style=False))
        
        # Add the DaemonSet and ConfigMap to the manifests
        skaffold_config["manifests"]["rawYaml"] = skaffold_config.get("manifests", {}).get("rawYaml", []) + [
            "./disk-setup-configmap.yaml",
            "./disk-setup-daemonset.yaml"
        ]
        
        # Group disks by node
        disks_by_node = {}
        for disk in disks:
            # Get node name from selector
            node_name = None
            if disk.get("node_selector"):
                for key, value in disk.get("node_selector", {}).items():
                    if key == "kubernetes.io/hostname":
                        node_name = value
                        break
                if not node_name:
                    node_name = list(disk.get("node_selector", {}).values())[0]
            
            # Skip disks without a node name
            if not node_name:
                print(f"Warning: Skipping disk {disk.get('name', 'unknown')} because no node name was selected")
                continue
                
            # Add disk to the node's list
            if node_name not in disks_by_node:
                disks_by_node[node_name] = []
            disks_by_node[node_name].append(disk)
        
        # Create Node patches for Longhorn
        node_patches = []
        for node_name, node_disks in disks_by_node.items():
            node_patch = generate_longhorn_node_patch(node_name, namespace, node_disks)
            node_patches.append(node_patch)
        
        write(f"{output_dir}/longhorn-node-patches.yaml", 
              yaml.dump_all(node_patches, default_flow_style=False))
        
        # Add the node patches to the manifests
        if "rawYaml" not in skaffold_config["manifests"]:
            skaffold_config["manifests"]["rawYaml"] = []
        skaffold_config["manifests"]["rawYaml"].append("./longhorn-node-patches.yaml")
    
    # Create storage class manifests
    if storage_classes:
        sc_manifests = []
        for sc in storage_classes:
            sc_manifest = generate_storage_class_manifest(sc, namespace)
            sc_manifests.append(sc_manifest)
        
        write(f"{output_dir}/longhorn-storage-classes.yaml", 
              yaml.dump_all(sc_manifests, default_flow_style=False))
        
        # Add the storage classes to the manifests
        if "rawYaml" not in skaffold_config["manifests"]:
            skaffold_config["manifests"]["rawYaml"] = []
        skaffold_config["manifests"]["rawYaml"].append("./longhorn-storage-classes.yaml")

    # Write all configuration files
    write(f"{output_dir}/longhorn-values.yaml", 
          yaml.dump(longhorn_values, default_flow_style=False))
    
    write(f"{output_dir}/skaffold-longhorn.yaml", 
          yaml.dump(skaffold_config, default_flow_style=False))
    
    write(f"{output_dir}/fleet.yaml", 
          yaml.dump(fleet_config, default_flow_style=False))

    return Component(
        slug=slug,
        namespace=namespace,
        dir_name=dir_name,
        fleet_name=f"{slug}-longhorn",
    )
