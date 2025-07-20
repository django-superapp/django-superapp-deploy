from components.kubevirt_vm.main import (
    create_kubevirt_vm,
    VMDisk,
    ContainerDiskSource,
    PVCDiskSource,
    Network,
    NetworkInterface,
    PersistentVolumeClaim,
    DataVolumeTemplate
)

def create_ubuntu_vm_example(
    slug: str,
    namespace: str,
    depends_on=None
):
    """
    Example of creating an Ubuntu VM with KubeVirt
    """
    # SSH public key for access
    ssh_public_key = "ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAACAQDEMziTibIPetH52n7Mw4TWNNUE3/RWlkONsxuhgnKDOscFd1eALUb1wWbhsUU1GFidrwz9nelOCZ6+9H+dXc+yZV28Ux86ajVluRQfIb0h+gl+KmTe2hyNcdGcmhtyPFlc7oWQsoxaz7vbi/AcQGQCuu9IPESFfiiy+VYRYlHY3kxZ2N1S120Xr7TMIFFdZeginfiRiAyTzdJg7TYoYlqkRcKd1Oz28jA8L6Ad+Li+G/dF9QGsGBABnLgZACIZsO4npmtU/iSfvGKfIfcFMIWbC/oIb8IuasVYod4Ym+bCgTVQxvLrcWhEt17ogg0sXJ4OxkoQ7Ao6HpNPWjNkNhx1y7G2Ekiw++OjtmcORnIJqyJtgLpTlsJrTMEZExuSzFqnlyMXbkznng5zOpTvss7eRM8Ly4r4eXC3zY0vJ37fCi3qLln9ZzPlk4ynN+53y3IsZnvzbkeocqKhO8YykLp1d1YHyyL4S3qLyM9srjcs0ui6Alc58QddwjUQKwXECNPsWb0Yi9WNfvPG8xBwZmY/5w0m8DTKsp20AHffa7GUpsO8QBCb7p9QLDgTbRipKofSCs4IvlIi4Gay9vMfx1g5XCbuIbVYJM+RU+i7rs4xjgxx3vwD5QCLeVEzx9NvTlonfIi7ZWV72h5pzSYGSYtn234/OJtItyPXdOU2Lsn2tQ=="
    
    # Create the VM with 100GB disk
    return create_kubevirt_vm(
        slug=slug,
        namespace=namespace,
        vm_name=f"{slug}-ubuntu",
        cpu_cores=2,
        memory_mb=4096,
        disks=[
            VMDisk(
                name="datadisk",
                disk_source=None,
                bus="virtio"
            )
        ],
        disk_sources=[
            PVCDiskSource(
                claim_name=f"{slug}-data-pvc",
                read_only=False
            )
        ],
        persistent_volume_claims=[
            PersistentVolumeClaim(
                name=f"{slug}-data-pvc",
                storage_class_name="standard",
                size="100Gi"
            )
        ],
        boot_from_container_disk=True,
        container_disk_image="quay.io/containerdisks/ubuntu:22.04",
        networks=[
            Network(
                name="default",
                pod=True
            )
        ],
        network_interfaces=[
            NetworkInterface(
                name="default",
                network_name="default",
                interface_type="masquerade"
            )
        ],
        cloud_init_user_data=f"""#cloud-config
users:
  - name: ubuntu
    sudo: ALL=(ALL) NOPASSWD:ALL
    shell: /bin/bash
    ssh_authorized_keys:
      - {ssh_public_key}

chpasswd:
  list: |
    ubuntu:ubuntu
  expire: False

ssh_pwauth: False

packages:
  - lvm2

# Configure disks (create partitions)
disk_setup:
  /dev/vdb:
    table_type: gpt
    layout: true

fs_setup:
  - device: /dev/vdb1
    partition: auto
    filesystem: ext4

# Set up LVM
runcmd:
  - pvcreate /dev/vdb1
  - vgextend ubuntu-vg /dev/vdb1 || vgcreate ubuntu-vg /dev/vda1 /dev/vdb1
  - lvextend -l +100%FREE /dev/ubuntu-vg/ubuntu-lv
  - resize2fs /dev/ubuntu-vg/ubuntu-lv
""",
        running=True,
        expose_service=True,
        service_type="LoadBalancer",
        service_ports=[
            {
                "name": "ssh", 
                "port": 22,           # Port exposed on the service
                "targetPort": 22,     # Port on the VM to forward to
                "protocol": "TCP"
            }
        ],
        annotations={
            "kubevirt.io/storage-size": "100Gi"
        },
        depends_on=depends_on
    )
