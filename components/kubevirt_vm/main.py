from typing import Dict, List, Optional, Any, Union
import os
import yaml
from ilio import write

from components.base.component_types import Component
from components.base.constants import GENERATED_SKAFFOLD_TMP_DIR
from components.base.utils import get_chart_path

class DiskSource:
    """Base class for disk sources"""
    pass

class ContainerDiskSource(DiskSource):
    """Container disk source for KubeVirt VM"""
    def __init__(self, image: str):
        self.image = image
        
    def to_dict(self) -> Dict[str, Any]:
        return {
            "containerDisk": {
                "image": self.image
            }
        }

class PVCDiskSource(DiskSource):
    """PVC disk source for KubeVirt VM"""
    def __init__(self, claim_name: str, read_only: bool = False):
        self.claim_name = claim_name
        self.read_only = read_only
        
    def to_dict(self) -> Dict[str, Any]:
        return {
            "persistentVolumeClaim": {
                "claimName": self.claim_name,
                "readOnly": self.read_only
            }
        }

class DataVolumeDiskSource(DiskSource):
    """DataVolume disk source for KubeVirt VM"""
    def __init__(self, name: str):
        self.name = name
        
    def to_dict(self) -> Dict[str, Any]:
        return {
            "dataVolume": {
                "name": self.name
            }
        }

class DataVolumeTemplate:
    """DataVolume template for KubeVirt VM"""
    def __init__(
        self,
        name: str,
        storage_class_name: str,
        size: str,
        source_type: str = "container",
        source_url: str = None,
        content_type: str = "kubevirt"
    ):
        self.name = name
        self.storage_class_name = storage_class_name
        self.size = size
        self.source_type = source_type
        self.source_url = source_url
        self.content_type = content_type
        
    def to_dict(self) -> Dict[str, Any]:
        dv_template = {
            "apiVersion": "cdi.kubevirt.io/v1beta1",
            "kind": "DataVolume",
            "metadata": {
                "name": self.name
            },
            "spec": {
                "pvc": {
                    "accessModes": ["ReadWriteOnce"],
                    "resources": {
                        "requests": {
                            "storage": self.size
                        }
                    },
                    "storageClassName": self.storage_class_name
                },
                "source": {}
            }
        }
        
        if self.source_type == "container":
            dv_template["spec"]["source"] = {
                "registry": {
                    "url": self.source_url,
                    "contentType": self.content_type
                }
            }
        elif self.source_type == "http":
            dv_template["spec"]["source"] = {
                "http": {
                    "url": self.source_url
                }
            }
        
        return dv_template

class PersistentVolumeClaim:
    """PersistentVolumeClaim for KubeVirt VM"""
    def __init__(
        self,
        name: str,
        storage_class_name: str,
        access_modes: List[str] = None,
        size: str = "10Gi",
        volume_mode: str = "Filesystem",
        snapshot_class_name: Optional[str] = None
    ):
        self.name = name
        self.storage_class_name = storage_class_name
        self.access_modes = access_modes or ["ReadWriteOnce"]
        self.size = size
        self.volume_mode = volume_mode
        self.snapshot_class_name = snapshot_class_name
        
    def to_dict(self) -> Dict[str, Any]:
        return {
            "apiVersion": "v1",
            "kind": "PersistentVolumeClaim",
            "metadata": {
                "name": self.name
            },
            "spec": {
                "accessModes": self.access_modes,
                "volumeMode": self.volume_mode,
                "resources": {
                    "requests": {
                        "storage": self.size
                    }
                },
                "storageClassName": self.storage_class_name
            }
        }

class NetworkInterface:
    """Network interface for KubeVirt VM"""
    def __init__(
        self, 
        name: str, 
        network_name: str, 
        mac_address: Optional[str] = None,
        model: str = "virtio",
        interface_type: str = "masquerade"  # Default to masquerade for better compatibility
    ):
        self.name = name
        self.network_name = network_name
        self.mac_address = mac_address
        self.model = model
        self.interface_type = interface_type
        
    def to_dict(self) -> Dict[str, Any]:
        interface = {
            "name": self.name,
            "model": self.model
        }
        
        # Add the interface type (masquerade, bridge, etc.)
        if self.interface_type == "masquerade":
            interface["masquerade"] = {}
        elif self.interface_type == "bridge":
            interface["bridge"] = {}
        elif self.interface_type == "slirp":
            interface["slirp"] = {}
        
        if self.mac_address:
            interface["macAddress"] = self.mac_address
            
        return interface

class Network:
    """Network for KubeVirt VM"""
    def __init__(self, name: str, pod: bool = True, multus: Optional[str] = None):
        self.name = name
        self.pod = pod
        self.multus = multus
        
    def to_dict(self) -> Dict[str, Any]:
        network = {
            "name": self.name
        }
        
        if self.pod:
            network["pod"] = {}
        elif self.multus:
            network["multus"] = {
                "networkName": self.multus
            }
            
        return network

class VMDisk:
    """Disk for KubeVirt VM"""
    def __init__(
        self, 
        name: str, 
        disk_source: DiskSource,
        boot_order: Optional[int] = None,
        disk_type: str = "disk",
        bus: str = "virtio"
    ):
        self.name = name
        self.disk_source = disk_source
        self.boot_order = boot_order
        self.disk_type = disk_type
        self.bus = bus
        
    def to_dict(self) -> Dict[str, Any]:
        disk = {
            "name": self.name,
            "disk": {
                "bus": self.bus
            }
        }
        
        if self.boot_order:
            disk["bootOrder"] = self.boot_order
            
        return disk

def create_kubevirt_vm(
    slug: str,
    namespace: str,
    vm_name: str,
    cpu_cores: int = 1,
    memory_mb: int = 1024,
    disks: List[VMDisk] = None,
    disk_sources: List[DiskSource] = None,
    persistent_volume_claims: List[PersistentVolumeClaim] = None,
    data_volume_templates: List[DataVolumeTemplate] = None,
    networks: List[Network] = None,
    network_interfaces: List[NetworkInterface] = None,
    cloud_init_user_data: Optional[str] = None,
    cloud_init_network_data: Optional[str] = None,
    running: bool = True,
    node_selector: Optional[Dict[str, str]] = None,
    tolerations: Optional[List[Dict[str, Any]]] = None,
    affinity: Optional[Dict[str, Any]] = None,
    labels: Optional[Dict[str, str]] = None,
    annotations: Optional[Dict[str, str]] = None,
    expose_service: bool = False,
    service_type: str = "LoadBalancer",
    service_ports: List[Dict[str, Any]] = None,
    boot_from_container_disk: bool = False,
    container_disk_image: Optional[str] = None,
    depends_on: Optional[List[Component]] = None
) -> Component:
    """
    Deploy a KubeVirt Virtual Machine.
    
    Args:
        slug: Unique identifier for the deployment
        namespace: Kubernetes namespace to deploy the VM
        vm_name: Name of the virtual machine
        cpu_cores: Number of CPU cores
        memory_mb: Memory in MB
        disks: List of VM disks
        disk_sources: List of disk sources
        networks: List of networks
        network_interfaces: List of network interfaces
        cloud_init_user_data: Cloud-init user data
        cloud_init_network_data: Cloud-init network data
        running: Whether the VM should be running
        node_selector: Node selector for VM placement
        tolerations: Tolerations for VM placement
        affinity: Affinity rules for VM placement
        labels: Labels to apply to the VM
        annotations: Annotations to apply to the VM
        depends_on: List of dependencies for Fleet
        
    Returns:
        Component object with metadata about the deployment
    """
    # Create directory structure
    dir_name = f"{slug}-kubevirt-vm"
    output_dir = f'{GENERATED_SKAFFOLD_TMP_DIR}/{dir_name}'
    os.makedirs(output_dir, exist_ok=True)
    manifests_dir = f"{output_dir}/manifests"
    os.makedirs(manifests_dir, exist_ok=True)
    
    # Default values if not provided
    disks = disks or []
    disk_sources = disk_sources or []
    persistent_volume_claims = persistent_volume_claims or []
    data_volume_templates = data_volume_templates or []
    networks = networks or []
    network_interfaces = network_interfaces or []
    labels = labels or {}
    annotations = annotations or {}
    service_ports = service_ports or [
        {"name": "ssh", "port": 22, "targetPort": 22, "protocol": "TCP"}
    ]
    
    # If boot_from_container_disk is enabled, create a DataVolumeTemplate for the boot disk
    if boot_from_container_disk and container_disk_image:
        # Create a DataVolumeTemplate for the boot disk
        boot_dv_name = f"{slug}-boot-dv"
        boot_dv = DataVolumeTemplate(
            name=boot_dv_name,
            storage_class_name=persistent_volume_claims[0].storage_class_name if persistent_volume_claims else "standard",
            size="10Gi",  # Default size for boot disk
            source_type="container",
            source_url=container_disk_image,
            content_type="kubevirt"
        )
        data_volume_templates.append(boot_dv)
        
        # Add a disk and disk source for the boot disk
        boot_disk = VMDisk(
            name="bootdisk",
            disk_source=None,
            boot_order=1,
            bus="virtio"
        )
        disks.insert(0, boot_disk)
        
        # Add a DataVolumeDiskSource for the boot disk
        boot_disk_source = DataVolumeDiskSource(name=boot_dv_name)
        disk_sources.insert(0, boot_disk_source)
    
    # Create PVCs if provided
    for pvc in persistent_volume_claims:
        pvc_manifest = pvc.to_dict()
        pvc_manifest["metadata"]["namespace"] = namespace
        
        # Add annotations for snapshot class if provided
        if hasattr(pvc, 'snapshot_class_name') and pvc.snapshot_class_name:
            if "annotations" not in pvc_manifest["metadata"]:
                pvc_manifest["metadata"]["annotations"] = {}
            pvc_manifest["metadata"]["annotations"]["snapshot.storage.kubernetes.io/volumesnapshotclass"] = pvc.snapshot_class_name
        
        # Write PVC manifest
        with open(f"{manifests_dir}/{pvc.name}-pvc.yaml", "w") as file:
            yaml.dump(pvc_manifest, file, default_flow_style=False)
    
    # Create cloud-init secret if needed
    cloud_init_secret_name = None
    if cloud_init_user_data or cloud_init_network_data:
        cloud_init_secret_name = f"{slug}-cloud-init"
        cloud_init_secret = {
            "apiVersion": "v1",
            "kind": "Secret",
            "metadata": {
                "name": cloud_init_secret_name,
                "namespace": namespace
            },
            "type": "Opaque",
            "stringData": {}
        }
        
        if cloud_init_user_data:
            cloud_init_secret["stringData"]["userdata"] = cloud_init_user_data
            
        if cloud_init_network_data:
            cloud_init_secret["stringData"]["networkdata"] = cloud_init_network_data
            
        # Write cloud-init secret manifest
        with open(f"{manifests_dir}/cloud-init-secret.yaml", "w") as file:
            yaml.dump(cloud_init_secret, file, default_flow_style=False)
    
    # Create VM manifest
    # Ensure the VM has the proper labels for service selection
    vm_labels = labels.copy()
    vm_labels["kubevirt.io/vm"] = vm_name
    
    # Add annotations to disable live migration
    vm_annotations = annotations.copy()
    vm_annotations["kubevirt.io/disableLiveMigration"] = "true"
    
    vm_manifest = {
        "apiVersion": "kubevirt.io/v1",
        "kind": "VirtualMachine",
        "metadata": {
            "name": vm_name,
            "namespace": namespace,
            "labels": vm_labels,
            "annotations": vm_annotations
        },
        "spec": {
            "running": running,
            "template": {
                "metadata": {
                    "labels": vm_labels  # Apply the same labels to the VMI template
                },
                "spec": {
                    "domain": {
                        "cpu": {
                            "cores": cpu_cores
                        },
                        "devices": {
                            "disks": [disk.to_dict() for disk in disks],
                            "interfaces": [interface.to_dict() for interface in network_interfaces]
                        },
                        "resources": {
                            "requests": {
                                "memory": f"{memory_mb}Mi"
                            }
                        }
                    },
                    "networks": [network.to_dict() for network in networks],
                    "volumes": []
                }
            }
        }
    }
    
    # Add DataVolumeTemplates if provided
    if data_volume_templates:
        vm_manifest["spec"]["dataVolumeTemplates"] = [dv.to_dict() for dv in data_volume_templates]
    
    # Add volumes based on disk sources
    volumes = []
    for i, disk in enumerate(disks):
        if i < len(disk_sources):
            volume = {
                "name": disk.name,
                **disk_sources[i].to_dict()
            }
            volumes.append(volume)
    
    # Add cloud-init volume if needed
    if cloud_init_secret_name:
        cloud_init_volume = {
            "name": "cloudinitdisk",
            "cloudInitNoCloud": {
                "secretRef": {
                    "name": cloud_init_secret_name
                }
            }
        }
        volumes.append(cloud_init_volume)
        
        # Add cloud-init disk if not already in disks
        cloud_init_disk_exists = any(disk.name == "cloudinitdisk" for disk in disks)
        if not cloud_init_disk_exists:
            cloud_init_disk = {
                "name": "cloudinitdisk",
                "disk": {
                    "bus": "virtio"
                }
            }
            vm_manifest["spec"]["template"]["spec"]["domain"]["devices"]["disks"].append(cloud_init_disk)
    
    # Add volumes to VM manifest
    vm_manifest["spec"]["template"]["spec"]["volumes"] = volumes
    
    # Add placement configuration if provided
    if node_selector or tolerations or affinity:
        vm_manifest["spec"]["template"]["spec"]["nodeSelector"] = node_selector or {}
        
        if tolerations:
            vm_manifest["spec"]["template"]["spec"]["tolerations"] = tolerations
            
        if affinity:
            vm_manifest["spec"]["template"]["spec"]["affinity"] = affinity
    
    # Write VM manifest
    with open(f"{manifests_dir}/vm.yaml", "w") as file:
        yaml.dump(vm_manifest, file, default_flow_style=False)
        
    # Create service to expose the VM if requested
    if expose_service:
        # Create a specific selector for the VM
        vm_selector = {
            "kubevirt.io/vm": vm_name  # This matches the label KubeVirt adds to VM pods
        }
        
        service_manifest = {
            "apiVersion": "v1",
            "kind": "Service",
            "metadata": {
                "name": f"{vm_name}-service",
                "namespace": namespace
            },
            "spec": {
                "selector": vm_selector,
                "type": service_type,
                "externalTrafficPolicy": "Cluster",  # Ensures proper traffic routing
                "ports": service_ports
            }
        }
        
        # Write service manifest
        with open(f"{manifests_dir}/vm-service.yaml", "w") as file:
            yaml.dump(service_manifest, file, default_flow_style=False)
    
    # Generate skaffold.yaml
    skaffold_config = {
        "apiVersion": "skaffold/v3",
        "kind": "Config",
        "deploy": {
            "kubectl": {
                "defaultNamespace": namespace,
            }
        },
        "manifests": {
            "rawYaml": [
                f"./manifests/vm.yaml",
            ],
        },
    }
    
    # Add cloud-init secret to rawYaml if it exists
    if cloud_init_secret_name:
        skaffold_config["manifests"]["rawYaml"].append(f"./manifests/cloud-init-secret.yaml")
        
    # Add PVCs to rawYaml if they exist
    for pvc in persistent_volume_claims:
        skaffold_config["manifests"]["rawYaml"].append(f"./manifests/{pvc.name}-pvc.yaml")
        
    # Add service to rawYaml if it exists
    if expose_service:
        skaffold_config["manifests"]["rawYaml"].append(f"./manifests/vm-service.yaml")
    
    skaffold_yaml = yaml.dump(skaffold_config, default_flow_style=False)
    write(f"{output_dir}/skaffold-kubevirt-vm.yaml", skaffold_yaml)
    
    # Generate fleet.yaml for dependencies
    fleet_config = {
        "dependsOn": [
            c.as_fleet_dependency for c in depends_on
        ] if depends_on else [],
        "labels": {
            "name": f"{slug}-kubevirt-vm"
        }
    }
    
    fleet_yaml = yaml.dump(fleet_config, default_flow_style=False)
    write(f"{output_dir}/fleet.yaml", fleet_yaml)
    
    # Return Component object
    return Component(
        slug=slug,
        namespace=namespace,
        dir_name=dir_name,
        fleet_name=f"{slug}-kubevirt-vm",
        depends_on=depends_on
    )
