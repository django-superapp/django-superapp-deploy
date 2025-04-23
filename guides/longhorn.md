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
# Replace disk_id with your actual disk ID (e.g., nvme-Samsung_SSD_980_PRO_2TB_S69ENF0WB76932R)
DISK_ID="your-disk-id"
DISK_PATH="/dev/disk/by-id/$DISK_ID"

# 1. Find the volume group name that uses this disk
VG_NAME=$(pvs --noheadings -o vg_name $DISK_PATH 2>/dev/null | tr -d ' ')

if [ -n "$VG_NAME" ]; then
  # 2. Deactivate any logical volumes in this volume group
  echo "Deactivating logical volumes in $VG_NAME"
  lvchange -an $VG_NAME

  # 3. Remove all logical volumes in this volume group
  echo "Removing logical volumes in $VG_NAME"
  lvs --noheadings -o lv_name $VG_NAME | while read LV_NAME; do
    lvremove -f $VG_NAME/$LV_NAME
  done

  # 4. Remove the volume group
  echo "Removing volume group $VG_NAME"
  vgremove -f $VG_NAME

  # 5. Remove the physical volume
  echo "Removing physical volume $DISK_PATH"
  pvremove -f $DISK_PATH
fi

# 6. Wipe the disk completely (WARNING: This will destroy all data on the disk)
echo "Wiping disk $DISK_PATH"
# First unmount any mounted partitions from this disk
mount | grep "$DISK_PATH" | awk '{print $1}' | xargs -I{} umount {} 2>/dev/null
# Try to wipe signatures, but don't fail if device is busy
wipefs -a $DISK_PATH || echo "Warning: Could not wipe all signatures, disk may be in use"

# 7. Create a new partition table (optional)
echo "Creating new partition table on $DISK_PATH"
# Use dd to zero out the first few MB of the disk (will clear partition table)
dd if=/dev/zero of=$DISK_PATH bs=1M count=10

echo "Disk $DISK_PATH has been completely wiped and LVM configuration removed"
```

⚠️ **WARNING**: This script will completely erase all data on the specified disk. Use with extreme caution, especially in production environments.
