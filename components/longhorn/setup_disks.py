"""
Longhorn Storage Component - Jobs Implementation

This module provides Jobs-based functionality to set up Longhorn disks
instead of using DaemonSets. Each job targets a specific server and disk.
"""
from typing import Any, Dict, List, Optional
import os
import hashlib

import yaml
import json
from ilio import write

from .types import LonghornDisk



def generate_disk_setup_job_for_node(
    slug: str, 
    namespace: str, 
    disks: List[LonghornDisk], 
    node_name: str
) -> Dict[str, Any]:
    """
    Generate a Job to mount all disks on a specific node.
    
    Args:
        slug: Unique identifier for the deployment
        namespace: Kubernetes namespace
        disks: List of disk configurations for this node
        node_name: Target node name
        
    Returns:
        Job manifest
    """
    
    # Create disk info for logging
    disk_names = [disk["name"] for disk in disks]
    disk_info = ", ".join(disk_names)
    
    # Generate disk processing code
    disk_processing_code = ""
    for i, disk in enumerate(disks):
        disk_processing_code += f'''    DISK_{i}_NAME="{disk["name"]}"
    DISK_{i}_ID="{disk["disk_id"]}"
    
    log_step "Processing disk {i+1}/$TOTAL_DISKS: $DISK_{i}_NAME"
    
    if setup_disk "$DISK_{i}_ID" "$DISK_{i}_NAME"; then
        log_success "Disk $DISK_{i}_NAME setup completed successfully"
        SUCCESS_DISKS=$((SUCCESS_DISKS + 1))
    else
        log_error "Disk $DISK_{i}_NAME setup failed"
        FAILED_DISKS=$((FAILED_DISKS + 1))
    fi
    
    PROCESSED_DISKS=$((PROCESSED_DISKS + 1))
    log_step "Progress: $PROCESSED_DISKS/$TOTAL_DISKS disks processed"
'''
    
    # Generate disk patch code for Longhorn registration
    disk_patch_code = ""
    for i, disk in enumerate(disks):
        disk_name = disk["name"]
        allow_scheduling = str(disk.get("allow_scheduling", True)).lower()
        tags = json.dumps(disk.get("tags", []))
        
        disk_patch_code += f'''
    # Disk {i+1}: {disk_name}
    log_step "Preparing patch data for disk {disk_name}"
    DISK_{i}_JSON=$(jq -n --arg disk_name "{disk_name}" \\
      --arg path "/var/lib/longhorn/disks/{disk_name}" \\
      --argjson allow_scheduling {allow_scheduling} \\
      --argjson tags '{tags}' \\
      --argjson storage_reserved {50 * 1024 * 1024 * 1024} \\
      '{{
        ($disk_name): {{
          "path": $path,
          "allowScheduling": $allow_scheduling,
          "tags": $tags,
          "storageReserved": $storage_reserved,
          "diskType": "filesystem"
        }}
      }}')
    
    if [ $? -eq 0 ]; then
        log_debug "Patch data for disk {disk_name} prepared successfully"
    else
        log_error "Failed to prepare patch data for disk {disk_name}"
        exit 1
    fi'''
    
    # Generate merge command for all disks
    disk_vars = " ".join([f'"$DISK_{i}_JSON"' for i in range(len(disks))])
    
    # Generate the setup script for all disks on this node
    setup_script = f"""#!/bin/sh
set -e

# Enable verbose logging with enhanced formatting
log_step() {{
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] [INFO] $1"
}}

log_error() {{
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] [ERROR] $1" >&2
}}

log_success() {{
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] [SUCCESS] $1"
}}

log_warning() {{
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] [WARNING] $1"
}}

log_debug() {{
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] [DEBUG] $1"
}}

# Job initialization logging
log_step "Starting disk setup job for node: {node_name}"
log_step "Total disks to process: {len(disks)}"
log_step "Disk list: {disk_info}"

# Function to execute command with logging
exec_with_log() {{
    local cmd="$1"
    local description="$2"
    
    log_step "Executing: $description"
    if eval "$cmd"; then
        local exit_code=$?
        log_success "$description completed (exit code: $exit_code)"
        return $exit_code
    else
        local exit_code=$?
        log_error "$description failed (exit code: $exit_code)"
        return $exit_code
    fi
}}

# Function to set up a disk with LVM
setup_disk() {{
    local disk_id="$1"
    local disk_name="$2"
    local mount_path="/var/lib/longhorn/disks/$disk_name"
    local vg_name="longhorn_$disk_name"
    local lv_name="data"
    local device_path="/dev/disk/by-id/$disk_id"
    
    log_step "Setting up disk $disk_name using $device_path"
    
    # Check if disk exists
    if [ ! -e "$device_path" ]; then
        log_error "Disk $device_path not found"
        return 1
    fi
    log_success "Disk $device_path found"
    
    # Create mount directory on the host
    log_step "Creating mount directory $mount_path on host"
    if ! chroot /host mkdir -p "$mount_path"; then
        log_error "Failed to create mount directory on host"
        return 1
    fi
    log_success "Mount directory created on host"
    
    # Check if already mounted on the host
    if chroot /host mount | grep -q "$mount_path"; then
        log_success "Disk already mounted at $mount_path on host"
        return 0
    fi
    
    # Install LVM tools if needed
    log_step "Ensuring LVM tools are available"
    if ! chroot /host which pvcreate >/dev/null 2>&1; then
        log_step "Installing LVM tools"
        chroot /host apt-get update -qq
        chroot /host apt-get install -y lvm2 e2fsprogs
    fi
    log_success "LVM tools are available"
    
    # Clean up any existing corrupted LVM metadata
    log_step "Checking for existing LVM structures"
    VGS_CMD="vgs"
    LVS_CMD="lvs"
    VGREMOVE_CMD="vgremove"
    PVREMOVE_CMD="pvremove"
    
    # Check if volume group exists and has issues
    if chroot /host $VGS_CMD "$vg_name" >/dev/null 2>&1; then
        log_step "Volume group $vg_name exists, checking logical volumes"
        LV_COUNT=$(chroot /host $VGS_CMD --noheadings -o lv_count "$vg_name" 2>/dev/null | tr -d ' ' || echo "0")
        
        if [ "$LV_COUNT" = "0" ] || ! chroot /host test -e "/dev/$vg_name/$lv_name"; then
            log_warning "Volume group exists but logical volume is missing or inaccessible - cleaning up"
            
            # Remove the corrupted volume group
            log_step "Removing corrupted volume group $vg_name"
            chroot /host $VGREMOVE_CMD -f "$vg_name" >/dev/null 2>&1 || true
            
            # Remove physical volume
            log_step "Removing physical volume from $device_path"
            chroot /host $PVREMOVE_CMD -f "$device_path" >/dev/null 2>&1 || true
            
            # Wipe any remaining LVM signatures
            log_step "Wiping LVM signatures from $device_path"
            chroot /host wipefs -a "$device_path" >/dev/null 2>&1 || true
            
            log_success "Cleaned up corrupted LVM structures"
        else
            log_success "Volume group and logical volume are properly accessible"
            return 0
        fi
    fi
    
    # Create fresh LVM structures
    log_step "Creating physical volume on $device_path"
    if ! chroot /host pvcreate -f "$device_path"; then
        log_error "Failed to create physical volume"
        return 1
    fi
    log_success "Physical volume created"
    
    log_step "Creating volume group $vg_name"
    if ! chroot /host vgcreate "$vg_name" "$device_path"; then
        log_error "Failed to create volume group"
        return 1
    fi
    log_success "Volume group created"
    
    log_step "Creating logical volume $lv_name using all available space"
    if ! chroot /host lvcreate -l 100%FREE -n "$lv_name" "$vg_name"; then
        log_error "Failed to create logical volume"
        return 1
    fi
    log_success "Logical volume created"
    
    # Verify logical volume is accessible
    LV_DEVICE="/dev/$vg_name/$lv_name"
    if ! chroot /host test -e "$LV_DEVICE"; then
        # Try device mapper path
        LV_DEVICE="/dev/mapper/$vg_name-$lv_name"
        if ! chroot /host test -e "$LV_DEVICE"; then
            log_error "Logical volume device not found at either location"
            return 1
        fi
    fi
    log_success "Logical volume device is accessible at $LV_DEVICE"
    
    # Format the logical volume
    log_step "Formatting logical volume with ext4"
    if ! chroot /host mkfs.ext4 -F "$LV_DEVICE"; then
        log_error "Failed to format logical volume"
        return 1
    fi
    log_success "Logical volume formatted with ext4"
    
    # Add to fstab
    log_step "Adding entry to /etc/fstab"
    if ! chroot /host grep -q "$mount_path" /etc/fstab; then
        chroot /host sh -c "echo '$LV_DEVICE $mount_path ext4 defaults 0 0' >> /etc/fstab"
        log_success "Added entry to fstab"
    else
        log_success "Entry already exists in fstab"
    fi
    
    # Note: Individual mounting is skipped here to avoid conflicts
    # All mounting will be done in the post-processing step using mount -a
    log_step "Skipping individual mount - will be handled in post-processing with mount -a"
    log_success "Disk preparation completed successfully"
    
    # Verify logical volume device exists (final check)
    if ! chroot /host test -e "$LV_DEVICE"; then
        log_error "Final verification failed: $LV_DEVICE does not exist"
        return 1
    fi
    log_success "Logical volume device verified: $LV_DEVICE"
    
    # Note: Mount verification, permissions, and write tests will be done in post-processing
    log_step "Individual disk setup complete - mounting and testing will be done in post-processing"
    
    log_success "Disk $disk_name successfully set up at $mount_path"
}}

# Function to get the full path of LVM commands
get_lvm_command_path() {{
    local cmd="$1"
    if chroot /host test -x "/usr/sbin/$cmd"; then
        echo "/usr/sbin/$cmd"
    elif chroot /host test -x "/sbin/$cmd"; then
        echo "/sbin/$cmd"
    else
        echo "$cmd"  # fallback to command name only
    fi
}}

# Get hostname from the host
log_step "Getting hostname from host"
HOSTNAME=$(chroot /host hostname)
log_step "Host hostname: $HOSTNAME"

# Check if this is the correct node
if [ "$HOSTNAME" = "{node_name}" ]; then
    log_step "Node validation successful - proceeding with disk setup"
    
    # Initialize counters for tracking
    TOTAL_DISKS={len(disks)}
    PROCESSED_DISKS=0
    FAILED_DISKS=0
    SUCCESS_DISKS=0
    
    log_step "Processing $TOTAL_DISKS disks on node {node_name}"
    
    # Process each disk sequentially
{disk_processing_code}
    
    # Summary of disk processing
    log_step "Disk processing summary:"
    log_step "  Total disks: $TOTAL_DISKS"
    log_step "  Successfully processed: $SUCCESS_DISKS"
    log_step "  Failed: $FAILED_DISKS"
    
    if [ $FAILED_DISKS -gt 0 ]; then
        log_error "Some disks failed to process. Check logs above for details."
        exit 1
    fi
    
    log_success "All disks processed successfully on node {node_name}"
    
    # Refresh disk cache and mount all fstab entries on the host
    log_step "Refreshing disk cache and mounting all fstab entries on host"
    
    # Refresh device mapper and LVM cache on host
    log_step "Refreshing device mapper and LVM cache on host"
    chroot /host udevadm settle || log_warning "udevadm settle failed, continuing anyway"
    chroot /host partprobe || log_warning "partprobe failed, continuing anyway" 
    chroot /host vgscan --cache || log_warning "vgscan failed, continuing anyway"
    chroot /host vgchange -ay || log_warning "vgchange -ay failed, continuing anyway"
    chroot /host lvscan || log_warning "lvscan failed, continuing anyway"
    
    # Additional wait for device nodes to settle
    log_step "Waiting for device nodes to settle"
    sleep 3
    
    # Reload systemd daemon to pick up any fstab changes
    log_step "Reloading systemd daemon on host"
    chroot /host systemctl daemon-reload
    
    # Check fstab entries before mounting
    LONGHORN_FSTAB_ENTRIES=$(chroot /host grep "longhorn" /etc/fstab | wc -l || echo "0")
    log_step "Found $LONGHORN_FSTAB_ENTRIES Longhorn entries in fstab"
    
    if [ "$LONGHORN_FSTAB_ENTRIES" -gt 0 ]; then
        log_step "Displaying Longhorn fstab entries:"
        chroot /host grep "longhorn" /etc/fstab | while read line; do
            log_step "  $line"
        done
        
        # Create all mount directories first
        log_step "Creating all Longhorn mount directories on host"
        chroot /host grep "longhorn" /etc/fstab | while read device mount_point fs_type options dump pass; do
            if [ -n "$mount_point" ]; then
                chroot /host mkdir -p "$mount_point"
                log_step "Created directory: $mount_point"
            fi
        done
        
        # Use mount -a to mount all fstab entries on host
        log_step "Mounting all fstab entries using mount -a on host"
        if chroot /host mount -a; then
            log_success "Successfully mounted all fstab entries on host"
        else
            log_warning "mount -a had some issues, checking individual mounts"
            
            # Fallback: try to mount each Longhorn entry individually
            log_step "Attempting individual mounting of Longhorn devices"
            chroot /host grep "longhorn" /etc/fstab | while read device mount_point fs_type options dump pass; do
                if [ -n "$device" ] && [ -n "$mount_point" ]; then
                    if ! chroot /host mount | grep -q "$mount_point"; then
                        log_step "Attempting to mount $device at $mount_point"
                        if chroot /host mount "$device" "$mount_point"; then
                            log_success "Successfully mounted $device at $mount_point"
                        else
                            log_error "Failed to mount $device at $mount_point"
                        fi
                    fi
                fi
            done
        fi
        
        # Set permissions and test write access on all mounted Longhorn directories
        log_step "Setting permissions and testing write access on all Longhorn mount points"
        chroot /host grep "longhorn" /etc/fstab | while read device mount_point fs_type options dump pass; do
            if [ -n "$mount_point" ] && chroot /host mount | grep -q "$mount_point"; then
                log_step "Setting permissions on $mount_point"
                chroot /host chown -R 1000:1000 "$mount_point" || log_warning "Failed to set ownership on $mount_point"
                chroot /host chmod 700 "$mount_point" || log_warning "Failed to set permissions on $mount_point"
                log_success "Permissions set for $mount_point"
                
                # Test write access
                log_step "Testing write access to $mount_point"
                if chroot /host touch "$mount_point/.longhorn_test" && chroot /host rm -f "$mount_point/.longhorn_test"; then
                    log_success "Write test successful for $mount_point"
                else
                    log_error "Write test failed for $mount_point"
                fi
            fi
        done
        
        # Final verification of all mounts
        log_step "Final verification - checking all Longhorn mounts on host"
        MOUNTED_COUNT=$(chroot /host mount | grep "longhorn" | wc -l || echo "0")
        log_step "Total Longhorn disks mounted on host: $MOUNTED_COUNT out of $LONGHORN_FSTAB_ENTRIES"
        
        if [ "$MOUNTED_COUNT" -eq "$LONGHORN_FSTAB_ENTRIES" ]; then
            log_success "All Longhorn disks are properly mounted on host"
        else
            log_warning "Some Longhorn disks may not be mounted ($MOUNTED_COUNT/$LONGHORN_FSTAB_ENTRIES)"
        fi
        
        # Show current mount status
        log_step "Current Longhorn mount status on host:"
        chroot /host mount | grep "longhorn" | while read line; do
            log_step "  $line"
        done
    else
        log_warning "No Longhorn entries found in fstab"
    fi
    
    # Wait for Longhorn CRDs and webhook to be ready (with timeout of 5 minutes)
    log_step "Waiting for Longhorn system to be ready before registering disks..."
    
    # First, verify kubectl configuration and service account
    log_step "Verifying kubectl configuration and service account"
    
    # Show current service account info for debugging
    SA_INFO=$(kubectl auth whoami 2>&1)
    log_step "Current service account: $SA_INFO"
    
    # Check specific permissions
    log_step "Checking CRD access permissions..."
    if kubectl auth can-i get customresourcedefinitions --all-namespaces > /dev/null 2>&1; then
        log_success "Service account has proper CRD access permissions"
    else
        log_error "Service account does not have permission to access CustomResourceDefinitions"
        log_step "Checking individual permissions..."
        
        # Check more specific permissions for debugging
        kubectl auth can-i get customresourcedefinitions --all-namespaces -v=6 2>&1 | head -10 | while read line; do
            log_step "Permission check: $line"
        done
        
        log_error "Check RBAC configuration for the service account"
        exit 1
    fi
    
    LONGHORN_READY=false
    TIMEOUT=300  # 5 minutes (only checking CRDs)
    START_TIME=$(date +%s)
    
    while [ $(($(date +%s) - START_TIME)) -lt $TIMEOUT ]; do
        # Check if Longhorn CRDs are available
        log_step "Checking for Longhorn CRDs..."
        set +e
        CRD_CHECK_OUTPUT=$(kubectl get crd nodes.longhorn.io 2>&1)
        CRD_CHECK_EXIT_CODE=$?
        set -e
        
        if [ $CRD_CHECK_EXIT_CODE -eq 0 ]; then
            log_success "Longhorn CRDs found - system ready"
            LONGHORN_READY=true
            break
        else
            log_step "Longhorn CRDs not yet available (exit code: $CRD_CHECK_EXIT_CODE)"
            log_step "CRD check output: $CRD_CHECK_OUTPUT"
        fi
        
        ELAPSED=$(($(date +%s) - START_TIME))
        log_step "Waiting for Longhorn CRDs... ($ELAPSED/$TIMEOUT seconds)"
        sleep 15
    done
    
    if [ "$LONGHORN_READY" = false ]; then
        log_warning "Longhorn CRDs not available after 5 minutes"
        log_warning "Disk setup completed, but unable to register with Longhorn automatically"
        log_warning "Disks are properly mounted and ready for use"
        log_step "Manual registration can be done later when Longhorn is ready"
        log_step "To register manually, run the disk setup job again or patch the node directly"
        log_success "Job completed successfully - disks are ready for Longhorn"
    else
        # Longhorn is ready, proceed with registration
        log_success "Longhorn system is ready - proceeding with disk registration"
        
        # Wait for the Longhorn node to become available (up to 5 minutes)
    log_step "Waiting for Longhorn node {node_name} to become available"
    NODE_READY=false
    NODE_TIMEOUT=300  # 5 minutes
    NODE_START_TIME=$(date +%s)
    
    while [ $(($(date +%s) - NODE_START_TIME)) -lt $NODE_TIMEOUT ]; do
        set +e
        kubectl get node.longhorn.io {node_name} -n {namespace} > /dev/null 2>&1
        NODE_CHECK_EXIT_CODE=$?
        set -e
        if [ $NODE_CHECK_EXIT_CODE -eq 0 ]; then
            log_success "Longhorn node {node_name} is available"
            NODE_READY=true
            break
        else
            NODE_ELAPSED=$(($(date +%s) - NODE_START_TIME))
            log_step "Longhorn node {node_name} not yet available, waiting... ($NODE_ELAPSED/$NODE_TIMEOUT seconds)"
            sleep 10
        fi
    done
    
    if [ "$NODE_READY" = false ]; then
        log_warning "Longhorn node {node_name} did not become available within 5 minutes"
        log_warning "This is normal if Longhorn is still starting up"
        log_warning "Proceeding with disk registration attempt anyway"
    fi
    
    # Prepare patch data for all disks at once
    log_step "Preparing patch data for all {len(disks)} disks"
    
{disk_patch_code}
    
    # Merge all disk JSON objects
    log_step "Merging all disk configurations"
    ALL_DISKS_JSON=$(echo {disk_vars} | jq -s 'add')
    
    if [ $? -eq 0 ]; then
        log_success "All disk configurations merged successfully"
    else
        log_error "Failed to merge disk configurations"
        exit 1
    fi
    
    # Create complete node YAML for kubectl apply
    NODE_YAML=$(cat <<EOF
apiVersion: longhorn.io/v1beta2
kind: Node
metadata:
  name: {node_name}
  namespace: {namespace}
spec:
  disks: $ALL_DISKS_JSON
EOF
)
    
    if [ $? -eq 0 ]; then
        log_success "Node YAML for all disks prepared successfully"
        log_debug "Node YAML: $NODE_YAML"
    else
        log_error "Failed to prepare node YAML"
        exit 1
    fi
    
    # Retry the apply operation up to 5 times with longer delays for webhook issues
    APPLY_SUCCESS=false
    attempt=1
    while [ $attempt -le 5 ]; do
        log_step "Attempting to apply Longhorn node with all disks (attempt $attempt/5)"
        log_step "Executing command: kubectl apply -f - (with node YAML)"
        
        # Use set +e to prevent script termination on command failure
        set +e
        APPLY_OUTPUT=$(echo "$NODE_YAML" | kubectl apply -f - 2>&1)
        APPLY_EXIT_CODE=$?
        set -e  # Re-enable exit on error
        
        if [ $APPLY_EXIT_CODE -eq 0 ]; then
            log_success "Apply attempt $attempt succeeded (exit code: $APPLY_EXIT_CODE)"
            APPLY_SUCCESS=true
            break
        else
            log_error "Apply attempt $attempt failed (exit code: $APPLY_EXIT_CODE)"
            log_step "Error details:"
            echo "$APPLY_OUTPUT" | while read line; do
                log_step "  $line"
            done
            
            # Check if this is a webhook-related error
            if echo "$APPLY_OUTPUT" | grep -q "longhorn-admission-webhook"; then
                log_warning "Webhook-related error detected - waiting longer before retry"
                if [ $attempt -lt 5 ]; then
                    WAIT_TIME=$((attempt * 15))  # Progressive wait: 15s, 30s, 45s, 60s
                    log_step "Waiting $WAIT_TIME seconds for webhook to become ready..."
                    sleep $WAIT_TIME
                fi
            else
                if [ $attempt -lt 5 ]; then
                    log_step "Retrying in 10 seconds..."
                    sleep 10
                fi
            fi
        fi
        attempt=$((attempt + 1))
    done
    
    if [ "$APPLY_SUCCESS" = true ]; then
        log_success "All {len(disks)} disks successfully added to Longhorn node {node_name}"
        log_step "Registered disks: {disk_info}"
    else
        log_warning "Failed to add disks to Longhorn node {node_name} after 5 attempts"
        log_warning "This is likely due to Longhorn webhook not being ready"
        log_warning "Disks are properly mounted and can be registered manually later"
        log_step "Manual registration: echo '$NODE_YAML' | kubectl apply -f -"
        log_success "Job completed successfully - disks are ready for manual registration"
    fi
    fi  # End of Longhorn readiness check
else
    log_step "Skipping disk setup - this is not node {node_name} (current: $HOSTNAME)"
fi
"""
    
    # Generate hash of the script content for job name uniqueness
    script_hash = hashlib.md5(setup_script.encode()).hexdigest()[:8]
    job_name = f"{slug}-disk-setup-{node_name}-{script_hash}".lower().replace("_", "-")
    
    # Create the Job manifest
    job = {
        "apiVersion": "batch/v1",
        "kind": "Job",
        "metadata": {
            "name": job_name,
            "namespace": namespace,
            "labels": {
                "app": f"{slug}-disk-setup",
                "node": node_name,
                "disk-count": str(len(disks))
            },
            "annotations": {
                "disks": disk_info,
                "description": f"Setup {len(disks)} disks on node {node_name}"
            }
        },
        "spec": {
            "ttlSecondsAfterFinished": 300,  # Clean up job after 5 minutes
            "backoffLimit": 0,  # Do not retry on failure
            "template": {
                "metadata": {
                    "labels": {
                        "app": f"{slug}-disk-setup",
                        "node": node_name,
                        "disk-count": str(len(disks))
                    }
                },
                "spec": {
                    "restartPolicy": "Never",
                    "serviceAccountName": f"{slug}-disk-setup",
                    "hostPID": True,
                    "hostIPC": True,
                    "hostNetwork": True,
                    "nodeSelector": {
                        "kubernetes.io/hostname": node_name
                    },
                    "containers": [
                        {
                            "name": "disk-setup",
                            "image": "bitnami/kubectl:latest",
                            "command": ["/bin/sh", "-c"],
                            "args": [setup_script],
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
                                    "name": "proc",
                                    "mountPath": "/proc"
                                },
                                {
                                    "name": "sys",
                                    "mountPath": "/sys"
                                },
                                {
                                    "name": "longhorn-dir",
                                    "mountPath": "/var/lib/longhorn"
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
                            "name": "proc",
                            "hostPath": {
                                "path": "/proc"
                            }
                        },
                        {
                            "name": "sys",
                            "hostPath": {
                                "path": "/sys"
                            }
                        },
                        {
                            "name": "longhorn-dir",
                            "hostPath": {
                                "path": "/var/lib/longhorn"
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
    
    return job


def generate_disk_setup_jobs(slug: str, namespace: str, disks: List[LonghornDisk]) -> List[Dict[str, Any]]:
    """
    Generate Jobs to set up disks on each server. Creates one job per node that handles all disks for that node.
    
    Args:
        slug: Unique identifier for the deployment
        namespace: Kubernetes namespace
        disks: List of disk configurations
        
    Returns:
        List of Job manifests
    """
    jobs = []
    
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
    
    # Create one Job per node that handles all disks for that node
    for node_name, node_disks in disks_by_node.items():
        job = generate_disk_setup_job_for_node(slug, namespace, node_disks, node_name)
        jobs.append(job)
    
    return jobs


def generate_rbac_resources(slug: str, namespace: str) -> List[Dict[str, Any]]:
    """
    Generate RBAC resources for disk setup jobs.
    
    Args:
        slug: Unique identifier for the deployment
        namespace: Kubernetes namespace
        
    Returns:
        List of RBAC manifests
    """
    service_account_name = f"{slug}-disk-setup"
    
    # ServiceAccount
    service_account = {
        "apiVersion": "v1",
        "kind": "ServiceAccount",
        "metadata": {
            "name": service_account_name,
            "namespace": namespace
        }
    }
    
    # ClusterRole with permissions to manage Longhorn nodes
    cluster_role = {
        "apiVersion": "rbac.authorization.k8s.io/v1",
        "kind": "ClusterRole",
        "metadata": {
            "name": f"{slug}-disk-setup"
        },
        "rules": [
            {
                "apiGroups": ["longhorn.io"],
                "resources": ["nodes"],
                "verbs": ["get", "list", "create", "update", "patch"]
            },
            {
                "apiGroups": ["apiextensions.k8s.io"],
                "resources": ["customresourcedefinitions"],
                "verbs": ["get", "list"]
            }
        ]
    }
    
    # ClusterRoleBinding
    cluster_role_binding = {
        "apiVersion": "rbac.authorization.k8s.io/v1",
        "kind": "ClusterRoleBinding",
        "metadata": {
            "name": f"{slug}-disk-setup"
        },
        "roleRef": {
            "apiGroup": "rbac.authorization.k8s.io",
            "kind": "ClusterRole",
            "name": f"{slug}-disk-setup"
        },
        "subjects": [
            {
                "kind": "ServiceAccount",
                "name": service_account_name,
                "namespace": namespace
            }
        ]
    }
    
    return [service_account, cluster_role, cluster_role_binding]


def create_disk_setup_jobs(
    slug: str,
    namespace: str,
    disks: List[LonghornDisk],
    output_dir: str
) -> List[str]:
    """
    Create Jobs for disk setup and write manifests to files.
    
    Args:
        slug: Unique identifier for the deployment
        namespace: Kubernetes namespace
        disks: List of disk configurations
        output_dir: Directory to write the job manifests
        
    Returns:
        List of YAML file paths created
    """
    # Generate RBAC resources
    rbac_resources = generate_rbac_resources(slug, namespace)
    
    # Generate all jobs
    jobs = generate_disk_setup_jobs(slug, namespace, disks)
    
    # Combine RBAC and jobs
    all_manifests = rbac_resources + jobs
    
    # Write all manifests to YAML file
    jobs_file = f"{output_dir}/disk-setup-jobs.yaml"
    write(jobs_file, yaml.dump_all(all_manifests, default_flow_style=False))
    
    return ["./disk-setup-jobs.yaml"]