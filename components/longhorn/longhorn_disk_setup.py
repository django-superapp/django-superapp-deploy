"""
Longhorn Disk Setup Component

This module provides functionality to set up disks before installing
the Longhorn storage operator and patch Longhorn nodes with disk configurations.
"""
from typing import Any, Dict, List, Optional, TypedDict, Literal
import os
import hashlib
import json

import yaml
from ilio import write

from ..base.component_types import Component
from ..base.constants import *


class LonghornDisk(TypedDict, total=False):
    """Configuration for a Longhorn disk."""
    name: str  # Required name for the disk
    node_selector: Dict[str, str]
    disk_path: str  # Full disk path (e.g., /dev/disk/by-uuid/..., /dev/disk/by-label/..., /dev/disk/by-id/...)
    tags: List[str]
    allow_scheduling: bool


def generate_disk_setup_script(node_name: str, disks: List[LonghornDisk], all_nodes_config: Dict[str, Any]) -> str:
    """
    Generate a bash script to set up disks with LVM and patch Longhorn nodes.
    Even if no disks are configured, the script will still patch nodes to ensure
    they are properly configured in Longhorn.

    Args:
        node_name: The specific node this script is for
        disks: List of disk configurations for this node
        all_nodes_config: Configuration for all nodes' disks for patching

    Returns:
        Bash script as a string
    """
    # Create a script that will run on each node to set up disks with LVM
    setup_script = """#!/bin/bash
set -eE  # Exit on error and inherit ERR trap

# Global error handler
error_handler() {
    local exit_code=$?
    local line_number=$1
    echo "================================================"
    echo "ERROR: Script failed with exit code ${exit_code} at line ${line_number}"
    echo "Last command: ${BASH_COMMAND}"
    echo "Stack trace:"
    local frame=0
    while caller $frame; do
        ((frame++))
    done
    echo "================================================"
    exit ${exit_code}
}

# Set up error handling for the entire script
trap 'error_handler ${LINENO}' ERR

# Function to log messages with timestamp
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"
}

# Function to run commands with logging
run_cmd() {
    local cmd="$*"
    log "Running: ${cmd}"
    if ! eval "${cmd}"; then
        log "ERROR: Command failed: ${cmd}"
        return 1
    fi
}

log "Starting Longhorn disk setup script..."

# Install required Longhorn dependencies
log "Checking and installing required Longhorn dependencies..."

# List of required packages
REQUIRED_PACKAGES="open-iscsi nfs-common cryptsetup dmsetup"
PACKAGES_TO_INSTALL=""

# Check which packages need to be installed
for package in $REQUIRED_PACKAGES; do
    if ! chroot /host dpkg -l | grep -q "^ii  $package "; then
        log "Package $package is not installed"
        PACKAGES_TO_INSTALL="$PACKAGES_TO_INSTALL $package"
    else
        log "Package $package is already installed"
    fi
done

# Install missing packages if any
if [ -n "$PACKAGES_TO_INSTALL" ]; then
    log "Installing missing packages:$PACKAGES_TO_INSTALL"
    
    # Update package list first
    log "Updating package list..."
    if ! chroot /host apt-get update; then
        log "ERROR: Failed to update package list"
        return 1
    fi
    
    # Install the packages
    log "Installing packages..."
    if ! chroot /host apt-get install -y $PACKAGES_TO_INSTALL; then
        log "ERROR: Failed to install required packages"
        return 1
    fi
    
    log "SUCCESS: All required packages installed"
else
    log "All required packages are already installed"
fi

# Enable and start iscsid service if not already running
log "Checking iSCSI service..."
if ! chroot /host systemctl is-active --quiet iscsid; then
    log "Starting iSCSI service..."
    run_cmd "chroot /host systemctl enable iscsid"
    run_cmd "chroot /host systemctl start iscsid"
    log "iSCSI service started"
else
    log "iSCSI service is already running"
fi

# Function to set up a disk with LVM
setup_disk() {
    local disk_path="$1"
    local disk_name="$2"
    local tags="$3"
    local mount_path="/var/lib/longhorn/disks/$disk_name"
    local vg_name="longhorn_$disk_name"
    local lv_name="data"
    
    log "Setting up disk $disk_name using $disk_path"
    
    # List all available disks for debugging
    log "Available disks:"
    ls -la /dev/disk/by-id/ 2>/dev/null || true
    ls -la /dev/disk/by-uuid/ 2>/dev/null || true
    ls -la /dev/disk/by-label/ 2>/dev/null || true
    
    # Check if disk exists
    if [ ! -e "$disk_path" ]; then
        log "ERROR: Disk $disk_path not found"
        return 1
    fi
    
    # Create mount directory
    mkdir -p "$mount_path"
    
    # Check if already mounted
    if mount | grep -q "$mount_path"; then
        log "Disk already mounted at $mount_path"
        return 0
    fi
    
    # Check if LVM tools are installed in the host
    if ! chroot /host command -v pvcreate &> /dev/null || ! chroot /host command -v vgcreate &> /dev/null; then
        log "Installing LVM tools on the host..."
        if ! chroot /host apt-get update; then
            log "ERROR: Failed to update package list"
            return 1
        fi
        if ! chroot /host apt-get install -y lvm2; then
            log "ERROR: Failed to install lvm2"
            return 1
        fi
    fi
    
    # Check if the disk is already part of a volume group
    local existing_vg=$(chroot /host pvs --noheadings -o vg_name "$disk_path" 2>/dev/null | tr -d ' ')
    if [ -n "$existing_vg" ]; then
        if [ "$existing_vg" = "$vg_name" ]; then
            log "Physical volume $disk_path is already in the correct volume group $vg_name"
        else
            log "WARNING: Physical volume $disk_path is already in volume group '$existing_vg'"
            log "Attempting to clean up and reuse the disk..."
            
            # Try to remove the disk from the existing volume group
            if chroot /host vgreduce "$existing_vg" "$disk_path" 2>/dev/null; then
                log "Successfully removed $disk_path from volume group $existing_vg"
                # Remove the physical volume
                if chroot /host pvremove -f "$disk_path" 2>/dev/null; then
                    log "Successfully removed physical volume from $disk_path"
                    # Now recreate the PV and VG
                    log "Creating new physical volume on $disk_path"
                    if ! chroot /host pvcreate -f "$disk_path"; then
                        log "ERROR: Failed to create physical volume on $disk_path"
                        return 1
                    fi
                    log "Creating volume group $vg_name"
                    if ! chroot /host vgcreate -f "$vg_name" "$disk_path"; then
                        log "ERROR: Failed to create volume group $vg_name"
                        return 1
                    fi
                else
                    log "ERROR: Failed to remove physical volume from $disk_path"
                    return 1
                fi
            else
                log "ERROR: Failed to remove $disk_path from volume group $existing_vg"
                log "This might be because the volume group is in use or has active logical volumes"
                return 1
            fi
        fi
    else
        # Create physical volume only if not already a PV
        if ! chroot /host pvs "$disk_path" &>/dev/null; then
            log "Creating physical volume on $disk_path"
            if ! chroot /host pvcreate -f "$disk_path"; then
                log "ERROR: Failed to create physical volume on $disk_path"
                return 1
            fi
        else
            log "Physical volume already exists on $disk_path"
        fi
        
        # Create volume group if it doesn't exist
        if ! chroot /host vgs "$vg_name" &>/dev/null; then
            log "Creating volume group $vg_name"
            if ! chroot /host vgcreate -f "$vg_name" "$disk_path"; then
                log "ERROR: Failed to create volume group $vg_name"
                return 1
            fi
        fi
    fi
    
    # Check if logical volume already exists
    if chroot /host lvs "$vg_name/$lv_name" &>/dev/null; then
        log "Logical volume $vg_name/$lv_name already exists"
    else
        # Create logical volume using 100% of the volume group
        log "Creating logical volume $lv_name in $vg_name"
        if ! chroot /host lvcreate -l 100%FREE -n "$lv_name" "$vg_name"; then
            log "ERROR: Failed to create logical volume $lv_name in $vg_name"
            return 1
        fi
        
        # Format the logical volume with ext4
        log "Formatting logical volume with ext4"
        if ! chroot /host mkfs.ext4 "/dev/$vg_name/$lv_name"; then
            log "ERROR: Failed to format logical volume"
            return 1
        fi
        
        # Refresh disk UUID and ensure changes are propagated
        log "Refreshing disk UUID and synchronizing changes..."
        
        # Run partprobe to inform the kernel of partition table changes
        if chroot /host command -v partprobe &> /dev/null; then
            log "Running partprobe to refresh partition table..."
            chroot /host partprobe "$disk_path" 2>/dev/null || true
            chroot /host partprobe "/dev/$vg_name/$lv_name" 2>/dev/null || true
        fi
        
        # Trigger udev to update device information
        if chroot /host command -v udevadm &> /dev/null; then
            log "Triggering udev to update device information..."
            chroot /host udevadm trigger --subsystem-match=block || true
            chroot /host udevadm settle --timeout=30 || true
        fi
        
        # Force kernel to re-read disk information
        if [ -e "$disk_path" ]; then
            log "Forcing kernel to re-read disk information..."
            chroot /host blockdev --rereadpt "$disk_path" 2>/dev/null || true
        fi
        
        # Sync filesystem to ensure all writes are flushed
        log "Syncing filesystem..."
        sync
        
        # Small delay to ensure all services see the changes
        log "Waiting for changes to propagate..."
        sleep 3
    fi
    
    # Add to host's fstab if not already there
    if ! grep -q "$mount_path" /host/etc/fstab; then
        log "Adding logical volume to host's fstab"
        echo "/dev/$vg_name/$lv_name $mount_path ext4 defaults 0 0" >> /host/etc/fstab
    fi
    
    # Reload systemd to recognize new fstab entries
    log "Reloading systemd daemon in host namespace"
    nsenter --target 1 --mount --uts --ipc --net --pid -- systemctl daemon-reload || true
    
    # Mount the logical volume using nsenter to access host's mount namespace
    log "Mounting logical volume in host namespace"
    if ! nsenter --target 1 --mount --uts --ipc --net --pid -- mount "/dev/$vg_name/$lv_name" "$mount_path"; then
        log "ERROR: Failed to mount logical volume"
        return 1
    fi
    
    # Set permissions using nsenter
    if ! nsenter --target 1 --mount --uts --ipc --net --pid -- chown -R 1000:1000 "$mount_path"; then
        log "WARNING: Failed to set ownership on $mount_path"
    fi
    if ! nsenter --target 1 --mount --uts --ipc --net --pid -- chmod 700 "$mount_path"; then
        log "WARNING: Failed to set permissions on $mount_path"
    fi
    
    # Write partition information to a JSON file
    log "Writing partition information to JSON file..."
    local partition_info_file="$mount_path/.partition_info.json"
    local created_at=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
    
    # Get partition UUID if available
    local partition_uuid=""
    if command -v blkid &> /dev/null; then
        partition_uuid=$(nsenter --target 1 --mount --uts --ipc --net --pid -- blkid -s UUID -o value "/dev/$vg_name/$lv_name" 2>/dev/null || echo "")
    fi
    
    # Get filesystem type
    local fs_type=$(nsenter --target 1 --mount --uts --ipc --net --pid -- blkid -s TYPE -o value "/dev/$vg_name/$lv_name" 2>/dev/null || echo "ext4")
    
    # Get disk size in bytes
    local disk_size_bytes=$(nsenter --target 1 --mount --uts --ipc --net --pid -- blockdev --getsize64 "/dev/$vg_name/$lv_name" 2>/dev/null || echo "0")
    
    # Create JSON with partition information
    nsenter --target 1 --mount --uts --ipc --net --pid -- bash -c "cat > '$partition_info_file' << EOF
{
  \"name\": \"$disk_name\",
  \"partition_type\": \"lvm\",
  \"filesystem_type\": \"$fs_type\",
  \"device_path\": \"/dev/$vg_name/$lv_name\",
  \"mount_path\": \"$mount_path\",
  \"volume_group\": \"$vg_name\",
  \"logical_volume\": \"$lv_name\",
  \"disk_path\": \"$disk_path\",
  \"uuid\": \"$partition_uuid\",
  \"size_bytes\": $disk_size_bytes,
  \"created_at\": \"$created_at\",
  \"hostname\": \"$HOSTNAME\"
}
EOF"
    
    # Set permissions on the info file
    nsenter --target 1 --mount --uts --ipc --net --pid -- chown 1000:1000 "$partition_info_file" || true
    nsenter --target 1 --mount --uts --ipc --net --pid -- chmod 644 "$partition_info_file" || true
    
    log "Partition information written to $partition_info_file"
    
    log "SUCCESS: Disk $disk_name successfully set up at $mount_path using LVM"
    return 0
}

# Function to patch Longhorn node with disk configuration
patch_longhorn_node() {
    local node_name="$1"
    local nodes_config="$2"
    
    log "Starting Longhorn node patching for node $node_name"
    
    # Install kubectl if not already installed
    if ! command -v kubectl &> /dev/null; then
        log "Installing kubectl..."
        apt-get update -qq
        apt-get install -y curl
        curl -LO "https://dl.k8s.io/release/$(curl -L -s https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl"
        install -o root -g root -m 0755 kubectl /usr/local/bin/kubectl
        rm kubectl
    fi
    
    # Install jq if not already installed
    if ! command -v jq &> /dev/null; then
        log "Installing jq..."
        apt-get update -qq
        apt-get install -y jq
    fi
    
    # Wait for Longhorn CRDs to be available
    log "Waiting for Longhorn CRDs to be available..."
    local max_retries=60
    local retry_count=0
    while [ $retry_count -lt $max_retries ]; do
        if kubectl get crd nodes.longhorn.io &>/dev/null; then
            log "Longhorn CRDs are available"
            break
        fi
        log "Waiting for Longhorn CRDs... (attempt $((retry_count + 1))/$max_retries)"
        sleep 5
        ((retry_count++))
    done
    
    if [ $retry_count -eq $max_retries ]; then
        log "WARNING: Longhorn CRDs not available after $max_retries attempts"
        log "Skipping node patching for now"
        return 0
    fi
    
    # Wait for the specific Longhorn node to exist
    log "Waiting for Longhorn node $node_name to be created..."
    retry_count=0
    while [ $retry_count -lt $max_retries ]; do
        if kubectl get node.longhorn.io "$node_name" -n longhorn-system &>/dev/null; then
            log "Longhorn node $node_name exists"
            break
        fi
        log "Waiting for Longhorn node $node_name... (attempt $((retry_count + 1))/$max_retries)"
        sleep 5
        ((retry_count++))
    done
    
    if [ $retry_count -eq $max_retries ]; then
        log "WARNING: Longhorn node $node_name not found after $max_retries attempts"
        log "Skipping node patching for now"
        return 0
    fi
    
    # Get current disk configuration
    log "Getting current disk configuration for $node_name..."
    CURRENT_DISKS=$(kubectl get node.longhorn.io "$node_name" -n longhorn-system -o json | jq -r '.spec.disks // {}')
    
    # Get new disk configuration for this node
    NEW_DISKS=$(echo "$nodes_config" | jq -r --arg node "$node_name" '.[$node] // {}')
    
    # Log configurations
    log "Current disk configuration:"
    echo "$CURRENT_DISKS" | jq '.'
    
    log "New disk configuration:"
    echo "$NEW_DISKS" | jq '.'
    
    # Merge current and new disk configurations
    log "Merging disk configurations..."
    MERGED_DISKS=$(echo "$CURRENT_DISKS" | jq --argjson new "$NEW_DISKS" '. + $new')
    
    log "Merged disk configuration:"
    echo "$MERGED_DISKS" | jq '.'
    
    # Check if configurations are different after merge
    if [ "$(echo "$CURRENT_DISKS" | jq -S .)" = "$(echo "$MERGED_DISKS" | jq -S .)" ]; then
        log "Disk configuration unchanged for $node_name after merge, skipping..."
        return 0
    fi
    
    # Create the patch with merged disks
    log "Creating patch for $node_name..."
    PATCH=$(jq -n --argjson disks "$MERGED_DISKS" '{"spec": {"disks": $disks}}')
    
    # Log the patch for debugging
    log "Patch to apply:"
    echo "$PATCH" | jq '.'
    
    # Apply the patch
    log "Patching Longhorn node $node_name..."
    if kubectl patch node.longhorn.io "$node_name" -n longhorn-system --type=merge -p "$PATCH"; then
        log "SUCCESS: Node $node_name patched successfully"
        
        # Verify the patch
        log "Verifying patch..."
        UPDATED_DISKS=$(kubectl get node.longhorn.io "$node_name" -n longhorn-system -o json | jq -r '.spec.disks // {}')
        
        log "Updated disk configuration:"
        echo "$UPDATED_DISKS" | jq '.'
    else
        log "ERROR: Failed to patch node $node_name"
        return 1
    fi
    
    return 0
}


# Get hostname from the host
HOSTNAME=$(chroot /host hostname)
log "Running on host: ${HOSTNAME}"

# Main execution with error handling
main() {
    log "Starting disk configuration..."
    
    # Process each disk for this specific node
"""

    # Add disk setup commands for this node's disks
    for disk in disks:
        disk_name = disk["name"]
        disk_path = disk["disk_path"]
        tags = disk.get("tags", [])
        tags_str = ",".join(tags) if tags else ""

        setup_script += f"""
    log "Setting up disk {disk_name} on node $HOSTNAME"
    if ! setup_disk "{disk_path}" "{disk_name}" "{tags_str}"; then
        log "ERROR: Failed to setup disk {disk_name}"
        exit 1
    fi
"""

    # Close the main function and add execution
    if not disks:
        setup_script += """
    log "No disks configured for node $HOSTNAME"
    log "Node is ready for Longhorn but no additional disks were added"
    """
    
    # Add node patching logic
    nodes_config_json = json.dumps(all_nodes_config, indent=2)
    setup_script += f"""
    
    # Patch Longhorn node with disk configuration
    log "Preparing to patch Longhorn node..."
    NODES_CONFIG='{nodes_config_json}'
    
    if ! patch_longhorn_node "$HOSTNAME" "$NODES_CONFIG"; then
        log "WARNING: Failed to patch Longhorn node, but disk setup completed"
        # Don't fail the job if patching fails - disks are still set up
    fi
    
    log "Disk setup completed successfully"
}}

# Execute main function with error handling
log "============================================"
log "Longhorn Disk Setup Script Starting"
log "============================================"

if main; then
    log "============================================"
    log "Script completed successfully"
    log "============================================"
    exit 0
else
    log "============================================"
    log "Script failed with errors"
    log "============================================"
    exit 1
fi
"""

    return setup_script


def generate_disk_setup_jobs(slug: str, namespace: str, disks: List[LonghornDisk]) -> tuple[
    List[Dict[str, Any]], List[Dict[str, Any]], Dict[str, Any], Dict[str, Any], Dict[str, Any], Dict[str, Any], Dict[str, Any]]:
    """
    Generate Jobs to mount disks and configure fstab on all nodes, then patch Longhorn nodes.
    Creates one Job per node to ensure proper execution.

    Args:
        slug: Unique identifier for the deployment
        namespace: Kubernetes namespace
        disks: List of disk configurations

    Returns:
        Tuple of (List of Job manifests, List of ConfigMap manifests, ServiceAccount manifest, Role manifest, RoleBinding manifest, ClusterRole manifest, ClusterRoleBinding manifest)
    """
    
    # Create ServiceAccount for disk setup pods
    service_account = {
        "apiVersion": "v1",
        "kind": "ServiceAccount",
        "metadata": {
            "name": f"{slug}-disk-setup",
            "namespace": namespace
        }
    }
    
    # Create Role with permissions to patch Longhorn nodes
    role = {
        "apiVersion": "rbac.authorization.k8s.io/v1",
        "kind": "Role",
        "metadata": {
            "name": f"{slug}-disk-setup",
            "namespace": namespace
        },
        "rules": [
            {
                "apiGroups": ["longhorn.io"],
                "resources": ["nodes"],
                "verbs": ["get", "list", "patch", "update"]
            }
        ]
    }
    
    # Create ClusterRole for CRD access (CRDs are cluster-scoped)
    cluster_role = {
        "apiVersion": "rbac.authorization.k8s.io/v1",
        "kind": "ClusterRole",
        "metadata": {
            "name": f"{slug}-disk-setup-crd-reader"
        },
        "rules": [
            {
                "apiGroups": ["apiextensions.k8s.io"],
                "resources": ["customresourcedefinitions"],
                "verbs": ["get", "list"]
            }
        ]
    }
    
    # Create RoleBinding to bind the role to the service account
    role_binding = {
        "apiVersion": "rbac.authorization.k8s.io/v1",
        "kind": "RoleBinding",
        "metadata": {
            "name": f"{slug}-disk-setup",
            "namespace": namespace
        },
        "roleRef": {
            "apiGroup": "rbac.authorization.k8s.io",
            "kind": "Role",
            "name": f"{slug}-disk-setup"
        },
        "subjects": [
            {
                "kind": "ServiceAccount",
                "name": f"{slug}-disk-setup",
                "namespace": namespace
            }
        ]
    }
    
    # Create ClusterRoleBinding for CRD access
    cluster_role_binding = {
        "apiVersion": "rbac.authorization.k8s.io/v1",
        "kind": "ClusterRoleBinding",
        "metadata": {
            "name": f"{slug}-disk-setup-crd-reader"
        },
        "roleRef": {
            "apiGroup": "rbac.authorization.k8s.io",
            "kind": "ClusterRole",
            "name": f"{slug}-disk-setup-crd-reader"
        },
        "subjects": [
            {
                "kind": "ServiceAccount",
                "name": f"{slug}-disk-setup",
                "namespace": namespace
            }
        ]
    }

    # Group disks by node and build node configuration for patching
    disks_by_node = {}
    all_nodes_config = {}
    
    for disk in disks:
        node_selector = disk.get("node_selector", {})
        node_name = node_selector.get("kubernetes.io/hostname")
        
        if node_name:
            if node_name not in disks_by_node:
                disks_by_node[node_name] = []
                all_nodes_config[node_name] = {}
            
            disks_by_node[node_name].append(disk)
            
            # Build disk configuration for Longhorn node patching
            disk_name = disk["name"]
            disk_path = f"/var/lib/longhorn/disks/{disk_name}"
            tags = disk.get("tags", [])
            allow_scheduling = disk.get("allow_scheduling", True)
            storage_reserved = 53687091200  # 50GB in bytes
            
            all_nodes_config[node_name][disk_name] = {
                "path": disk_path,
                "allowScheduling": allow_scheduling,
                "storageReserved": storage_reserved,
                "diskType": "filesystem",
                "tags": tags
            }
    
    # If no disks are configured, return empty lists
    if not disks_by_node:
        return [], [], service_account, role, role_binding, cluster_role, cluster_role_binding
    
    # Create a Job and ConfigMap for each node
    jobs = []
    config_maps = []
    
    for node_name, node_disks in disks_by_node.items():
        # Generate the setup script for this specific node with patching logic
        setup_script = generate_disk_setup_script(node_name, node_disks, all_nodes_config)
        
        # Calculate a deterministic hash of the setup script content
        script_hash = hashlib.sha256(setup_script.encode('utf-8')).hexdigest()[:16]
        
        # Create ConfigMap for this node's setup script
        config_map_name = f"{slug}-disk-setup-{node_name}-script"
        config_map = {
            "apiVersion": "v1",
            "kind": "ConfigMap",
            "metadata": {
                "name": config_map_name,
                "namespace": namespace,
                "labels": {
                    "app": f"{slug}-disk-setup",
                    "node": node_name,
                }
            },
            "data": {
                "setup.sh": setup_script
            }
        }
        config_maps.append(config_map)
        
        # Create a job name for this node
        job_name = f"{slug}-disk-setup-{node_name}"
        
        job = {
            "apiVersion": "batch/v1",
            "kind": "Job",
            "metadata": {
                "name": job_name,
                "namespace": namespace,
                "labels": {
                    "app": f"{slug}-disk-setup",
                    "node": node_name,
                },
            },
            "spec": {
                "ttlSecondsAfterFinished": 3600,  # Clean up after 1 hour
                "template": {
                    "metadata": {
                        "labels": {
                            "app": f"{slug}-disk-setup",
                            "node": node_name
                        },
                        "annotations": {
                            # This forces pod restart when the setup script changes
                            "setup-script-checksum": script_hash
                        }
                    },
                    "spec": {
                        "serviceAccountName": f"{slug}-disk-setup",
                        "hostPID": True,
                        "hostIPC": True,
                        "hostNetwork": True,
                        "restartPolicy": "OnFailure",
                        "containers": [
                            {
                                "name": "disk-setup",
                                "image": "ubuntu:22.04",
                                "command": ["/bin/bash", "/scripts/setup.sh"],
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
                                "name": "setup-script",
                                "configMap": {
                                    "name": config_map_name,
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
                        ],
                        "nodeSelector": {
                            "kubernetes.io/hostname": node_name
                        }
                    }
                }
            }
        }
        
        jobs.append(job)

    return jobs, config_maps, service_account, role, role_binding, cluster_role, cluster_role_binding


def create_longhorn_disk_setup(
        slug: str,
        namespace: str = 'longhorn-system',
        disks: Optional[List[LonghornDisk]] = None,
        depends_on: Optional[List[Component]] = None
) -> Component:
    """
    Create a separate component for Longhorn disk setup that runs before the operator.
    This component also patches Longhorn nodes with disk configurations after setup.
    
    Args:
        slug: Unique identifier for the deployment
        namespace: Kubernetes namespace
        disks: List of disk configurations
        depends_on: List of dependencies for Fleet
        
    Returns:
        Component instance for the disk setup
    """
    # Initialize disks if not provided
    disks = disks or []

    # Create directory structure
    dir_name = f"{slug}-disk-setup"
    output_dir = f'{GENERATED_SKAFFOLD_TMP_DIR}/{dir_name}'
    os.makedirs(output_dir, exist_ok=True)

    # Generate jobs for disk setup (one per node with disks)
    jobs, config_maps, service_account, role, role_binding, cluster_role, cluster_role_binding = generate_disk_setup_jobs(slug, namespace, disks)

    # Generate Skaffold configuration
    skaffold_config = {
        "apiVersion": "skaffold/v3",
        "kind": "Config",
        "build": {
            **SKAFFOLD_DEFAULT_BUILD,
            "artifacts": [],
        },
        "manifests": {
            "rawYaml": [
                "./disk-setup-rbac.yaml",
                "./disk-setup-cluster-rbac.yaml",
                "./disk-setup-configmaps.yaml",
                "./disk-setup-jobs.yaml"
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
            "name": f"{slug}-disk-setup",
        },
        "diff": {
            "comparePatches": [
                {
                    "apiVersion": "batch/v1",
                    "kind": "Job",
                    "jsonPointers": [
                        "/metadata/resourceVersion",
                        "/metadata/uid"
                    ]
                }
            ]
        }
    }

    # Write configuration files
    # Write RBAC resources (namespaced)
    rbac_resources = [service_account, role, role_binding]
    write(f"{output_dir}/disk-setup-rbac.yaml",
          yaml.dump_all(rbac_resources, default_flow_style=False))
    
    # Write cluster-scoped RBAC resources
    cluster_rbac_resources = [cluster_role, cluster_role_binding]
    write(f"{output_dir}/disk-setup-cluster-rbac.yaml",
          yaml.dump_all(cluster_rbac_resources, default_flow_style=False))
    
    write(f"{output_dir}/disk-setup-jobs.yaml",
          yaml.dump_all(jobs, default_flow_style=False))

    write(f"{output_dir}/disk-setup-configmaps.yaml",
          yaml.dump_all(config_maps, default_flow_style=False))

    write(f"{output_dir}/skaffold-disk-setup.yaml",
          yaml.dump(skaffold_config, default_flow_style=False))

    write(f"{output_dir}/fleet.yaml",
          yaml.dump(fleet_config, default_flow_style=False))

    return Component(
        slug=f"{slug}-disk-setup",
        namespace=namespace,
        dir_name=dir_name,
        fleet_name=f"{slug}-disk-setup",
    )