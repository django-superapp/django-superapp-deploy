# Longhorn Storage Configuration Guide

This guide explains how to configure Longhorn storage with NVMe disks.

## Finding Disk Information

```bash
# List disks with basic information
lsblk -o NAME,PATH,SIZE,MODEL,TYPE,TRAN

# Find disk by-id paths (recommended for stable disk identification)
ls -la /dev/disk/by-id/
```

## Configuration

Add to `config_env.yaml`:

```yaml
components:
  longhorn:
    LONGHORN_DOMAIN_NAME: longhorn.example.com
    LONGHORN_DISKS:
      - name: sv1-nvme-disk-1
        node_selector: 
          kubernetes.io/hostname: sv1
        disk_id: nvme-Samsung_SSD_980_PRO_1TB_S4DYNX0R123456
        tags: 
          - nvme
          - fast
        allow_scheduling: true
    LONGHORN_STORAGE_CLASSES:
      - name: nvme-storage
        replica_count: 3
        disk_selector:
          - nvme
          - fast
        is_default: true
```

Note: Each disk automatically reserves 50GB for the filesystem to prevent filling up completely. The system will create an LVM volume group and logical volume for each disk to ensure proper management and flexibility.

## Deploy and Verify

```bash
make generate-manifests
make deploy-manifests

# Access UI
kubectl -n longhorn-system port-forward svc/longhorn-frontend 8000:80
```

## Troubleshooting

If you encounter disk setup issues, check:

1. Disk permissions and availability
2. Verify disk paths: `ls -la /dev/disk/by-id/`
3. LVM tools installation on nodes: `apt list --installed | grep lvm2`
4. Disk mount status: `lsblk -f`
5. LVM status: `sudo pvs`, `sudo vgs`, `sudo lvs`
6. Check DaemonSet logs: `kubectl -n longhorn-system logs -l app=<slug>-disk-setup`
7. Check fstab entries: `cat /etc/fstab`
8. If you see "ext4 signature detected" errors, the script now uses the `-f` flag with pvcreate and vgcreate to automatically accept these prompts

### Debugging the Disk Setup DaemonSet

The disk setup DaemonSet uses an init container to run the setup script automatically and provides a main container for debugging:

```bash
# Connect to the main container for debugging
kubectl -n longhorn-system exec -it <pod-name> -- /bin/bash

# Check available disks
ls -la /dev/disk/by-id/

# Check LVM status
chroot /host pvs
chroot /host vgs
chroot /host lvs

# Check mount status
chroot /host mount | grep longhorn

# Reload systemd and mount all entries in fstab if needed
chroot /host systemctl daemon-reload
chroot /host mount -a

# View init container logs to see setup script output
kubectl -n longhorn-system logs <pod-name> -c disk-setup-init
```

## Miscellaneous Commands

### Cleaning Up LVM Partitions

If you need to completely remove LVM configuration from a disk and start fresh (run this on the host node, not in the container):

```bash
# Function to clean up LVM partitions and format disk
cleanup_disk() {
  local DISK_ID="$1"
  
  if [ -z "$DISK_ID" ]; then
    echo "Error: Disk ID is required"
    echo "Usage: cleanup_disk <disk-id>"
    return 1
  fi
  
  local DISK_PATH="/dev/disk/by-id/$DISK_ID"
  
  if [ ! -e "$DISK_PATH" ]; then
    echo "Error: Disk $DISK_PATH does not exist"
    return 1
  fi
  
  echo "Starting safe cleanup of disk: $DISK_PATH"
  echo "WARNING: This will destroy all data on the disk!"
  
  # 1. Find the volume group name that uses this disk
  echo "Finding LVM volume groups using disk $DISK_PATH"
  VG_NAME=$(pvs --noheadings -o vg_name $DISK_PATH 2>/dev/null | tr -d ' ')
  
  if [ -n "$VG_NAME" ]; then
    echo "Found volume group: $VG_NAME"
    
    # 2. Safely unmount all logical volumes in this VG
    echo "Unmounting logical volumes in volume group $VG_NAME"
    lvs --noheadings -o lv_path $VG_NAME 2>/dev/null | while read LV_PATH; do
      if [ -n "$LV_PATH" ]; then
        # Check if mounted and unmount gracefully first, then force if needed
        if mount | grep -q "$LV_PATH"; then
          echo "Unmounting $LV_PATH"
          umount "$LV_PATH" 2>/dev/null || umount -l "$LV_PATH" 2>/dev/null || echo "Warning: Could not unmount $LV_PATH"
        fi
      fi
    done
    
    # Wait for unmounts to complete
    sleep 3
    
    # 3. Remove entries from /etc/fstab
    echo "Removing disk entries from /etc/fstab"
    cp /etc/fstab /etc/fstab.backup.$(date +%Y%m%d_%H%M%S)
    grep -v "$DISK_PATH" /etc/fstab > /tmp/fstab.tmp && mv /tmp/fstab.tmp /etc/fstab
    grep -v "/dev/$VG_NAME/" /etc/fstab > /tmp/fstab.tmp && mv /tmp/fstab.tmp /etc/fstab 2>/dev/null || true
    grep -v "/dev/mapper/$VG_NAME" /etc/fstab > /tmp/fstab.tmp && mv /tmp/fstab.tmp /etc/fstab 2>/dev/null || true
    
    # 4. Deactivate logical volumes
    echo "Deactivating logical volumes in $VG_NAME"
    lvchange -an $VG_NAME 2>/dev/null || echo "Warning: Could not deactivate all LVs"
    
    # 5. Remove logical volumes
    echo "Removing logical volumes in $VG_NAME"
    lvs --noheadings -o lv_name $VG_NAME 2>/dev/null | while read LV_NAME; do
      if [ -n "$LV_NAME" ]; then
        echo "Removing LV: $VG_NAME/$LV_NAME"
        lvremove -f "$VG_NAME/$LV_NAME" 2>/dev/null || echo "Warning: Could not remove $VG_NAME/$LV_NAME"
      fi
    done
    
    # 6. Remove volume group
    echo "Removing volume group $VG_NAME"
    vgremove -f "$VG_NAME" 2>/dev/null || echo "Warning: Could not remove VG $VG_NAME"
    
    # 7. Remove physical volume
    echo "Removing physical volume $DISK_PATH"
    pvremove -f "$DISK_PATH" 2>/dev/null || echo "Warning: Could not remove PV $DISK_PATH"
    
  else
    echo "No LVM volume groups found on disk $DISK_PATH"
    
    # Handle non-LVM partitions
    echo "Unmounting any regular partitions from disk $DISK_PATH"
    mount | grep "$DISK_PATH" | awk '{print $1}' | while read PARTITION; do
      echo "Unmounting $PARTITION"
      umount "$PARTITION" 2>/dev/null || echo "Warning: Could not unmount $PARTITION"
    done
    
    # Remove from fstab
    echo "Removing disk entries from /etc/fstab"
    cp /etc/fstab /etc/fstab.backup.$(date +%Y%m%d_%H%M%S)
    grep -v "$DISK_PATH" /etc/fstab > /tmp/fstab.tmp && mv /tmp/fstab.tmp /etc/fstab
  fi
  
  # 8. Wait for operations to complete
  echo "Waiting for operations to complete..."
  sleep 5
  
  # 9. Wipe disk signatures
  echo "Wiping disk signatures on $DISK_PATH"
  wipefs -a "$DISK_PATH" 2>/dev/null || echo "Warning: Could not wipe all signatures"
  
  # 10. Zero out beginning of disk
  echo "Zeroing beginning of disk $DISK_PATH"
  dd if=/dev/zero of="$DISK_PATH" bs=1M count=10 2>/dev/null || echo "Warning: Could not zero disk"
  
  # 11. Safe system refresh
  echo "Refreshing system state (safe mode)"
  
  # Sync filesystems
  sync
  
  # Reload systemd
  systemctl daemon-reload
  
  # Gentle udev refresh
  udevadm settle
  udevadm trigger --subsystem-match=block
  udevadm settle
  
  # Safe LVM refresh
  if command -v pvscan >/dev/null 2>&1; then
    pvscan --cache 2>/dev/null || echo "Warning: pvscan failed"
  fi
  
  # Gentle partition table refresh
  partprobe "$DISK_PATH" 2>/dev/null || echo "Warning: partprobe failed"
  
  echo "Disk $DISK_PATH cleanup completed safely"
  echo "Please run 'lsblk' to verify the disk state"
  echo "If lsblk shows I/O errors, a system reboot may be required"
}

# Example usage:
# cleanup_disk "nvme-Samsung_SSD_980_PRO_2TB_S69ENF0WB76932R"
```

⚠️ **WARNING**: This script will completely erase all data on the specified disk. Use with extreme caution, especially in production environments.

### Recovery from I/O Errors

If you encounter "Input/output error" from `lsblk` after running the cleanup script, this means the kernel's block device subsystem has been corrupted. Here are recovery steps:

1. **Immediate Recovery (try first):**
   ```bash
   # Reload block device subsystem
   echo 1 > /sys/block/$(basename $DISK_PATH)/device/rescan 2>/dev/null || true
   
   # Force reload of all block devices
   for device in /sys/block/*/device/rescan; do
     echo 1 > "$device" 2>/dev/null || true
   done
   
   # Wait and try lsblk again
   sleep 5
   lsblk
   ```

2. **If step 1 fails, reload kernel modules:**
   ```bash
   # Reload LVM modules
   modprobe -r dm_mod 2>/dev/null || true
   modprobe dm_mod
   
   # Reload block device modules
   modprobe -r sd_mod 2>/dev/null || true
   modprobe sd_mod
   
   # Wait and try lsblk again
   sleep 5
   lsblk
   ```

3. **If steps 1-2 fail, reboot the system:**
   ```bash
   # This will cleanly restart the kernel and fix all I/O errors
   reboot
   ```

**Prevention**: The updated cleanup function above uses safer operations to prevent I/O errors. Always use the latest version of the function.
