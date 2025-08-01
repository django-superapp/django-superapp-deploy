import os
from typing import List, Optional, TypedDict, Dict, Any
import yaml

from ilio import write

from components.base.component_types import Component
from components.base.constants import GENERATED_SKAFFOLD_TMP_DIR
from components.base.utils import get_chart_path


class RedisInstanceConfig(TypedDict, total=False):
    """
    Configuration for a single Redis instance.
    
    Attributes:
        slug: Unique identifier for this instance
        auth_enabled: Whether authentication is enabled (optional, default: True)
        password: Redis password (optional, will be auto-generated if not provided)
        architecture: Redis architecture - "standalone" or "replication" (optional, default: "standalone")
        replica_count: Number of replicas for replication mode (optional, default: 3)
        storage_size: Size of the Redis data volume (optional, default: "8Gi")
        storage_class: Storage class for persistent volumes (optional)
        resources_requests_memory: Memory request (optional, default: "256Mi")
        resources_requests_cpu: CPU request (optional, default: "250m")
        resources_limits_memory: Memory limit (optional, default: "512Mi")
        resources_limits_cpu: CPU limit (optional, default: "500m")
        metrics_enabled: Whether to enable metrics (optional, default: True)
        service_type: Type of Kubernetes service (optional, default: "ClusterIP")
        service_annotations: Annotations to add to the service metadata (optional)
        image_registry: Redis image registry (optional, default: "docker.io")
        image_repository: Redis image repository (optional, default: "bitnami/redis")
        image_tag: Redis image tag (optional, default: "7.2-debian-12")
    """
    slug: str
    auth_enabled: Optional[bool]
    password: Optional[str]
    architecture: Optional[str]  # "standalone" or "replication"
    replica_count: Optional[int]
    storage_size: Optional[str]
    storage_class: Optional[str]
    resources_requests_memory: Optional[str]
    resources_requests_cpu: Optional[str]
    resources_limits_memory: Optional[str]
    resources_limits_cpu: Optional[str]
    metrics_enabled: Optional[bool]
    service_type: Optional[str]
    service_annotations: Optional[Dict[str, str]]
    image_registry: Optional[str]
    image_repository: Optional[str]
    image_tag: Optional[str]


def create_redis_instances(
    slug: str,
    namespace: str,
    instances: List[RedisInstanceConfig],
    depends_on: Optional[List[Component]] = None
) -> Component:
    """
    Deploy multiple Redis instances using the Bitnami Redis Helm chart.
    
    Args:
        slug: Unique identifier for the deployment
        namespace: Kubernetes namespace to deploy all instances
        instances: List of Redis instance configurations
        depends_on: List of dependencies for Fleet
        
    Returns:
        Component object with metadata about the deployment
    """
    # Create directory structure
    dir_name = f"{slug}-redis-instances"
    output_dir = f'{GENERATED_SKAFFOLD_TMP_DIR}/{dir_name}'
    os.makedirs(output_dir, exist_ok=True)
    
    # Create Helm releases for each Redis instance
    helm_releases = []
    redis_instances_info = []
    
    for instance_config in instances:
        instance_slug = instance_config["slug"]
        
        # Prepare Helm values for this instance
        helm_values = {
            "fullnameOverride": instance_slug,
            "global": {
                "security": {
                    "allowInsecureImages": True
                }
            },
            "image": {
                "registry": instance_config.get("image_registry", "docker.io"),
                "repository": instance_config.get("image_repository", "bitnami/redis"),
                "tag": instance_config.get("image_tag", "7.2-debian-12")
            },
            "auth": {
                "enabled": instance_config.get("auth_enabled", True),
            },
            "architecture": instance_config.get("architecture", "standalone"),
            "master": {
                "persistence": {
                    "enabled": True,
                    "size": instance_config.get("storage_size", "8Gi"),
                },
                "resources": {
                    "requests": {
                        "memory": instance_config.get("resources_requests_memory", "256Mi"),
                        "cpu": instance_config.get("resources_requests_cpu", "250m")
                    },
                    "limits": {
                        "memory": instance_config.get("resources_limits_memory", "512Mi"),
                        "cpu": instance_config.get("resources_limits_cpu", "500m")
                    }
                },
                "service": {
                    "type": instance_config.get("service_type", "ClusterIP"),
                }
            },
            "metrics": {
                "enabled": instance_config.get("metrics_enabled", True),
                "serviceMonitor": {
                    "enabled": False  # Disable by default, can be enabled per environment
                }
            }
        }
        
        # Add password if provided
        if instance_config.get("password"):
            helm_values["auth"]["password"] = instance_config["password"]
        
        # Add storage class if provided
        if instance_config.get("storage_class"):
            helm_values["master"]["persistence"]["storageClass"] = instance_config["storage_class"]
        
        # Add service annotations if provided
        if instance_config.get("service_annotations"):
            helm_values["master"]["service"]["annotations"] = instance_config["service_annotations"]
        
        # Configure replica settings for replication architecture
        if instance_config.get("architecture") == "replication":
            helm_values["replica"] = {
                "replicaCount": instance_config.get("replica_count", 3),
                "persistence": {
                    "enabled": True,
                    "size": instance_config.get("storage_size", "8Gi"),
                },
                "resources": {
                    "requests": {
                        "memory": instance_config.get("resources_requests_memory", "256Mi"),
                        "cpu": instance_config.get("resources_requests_cpu", "250m")
                    },
                    "limits": {
                        "memory": instance_config.get("resources_limits_memory", "512Mi"),
                        "cpu": instance_config.get("resources_limits_cpu", "500m")
                    }
                },
                "service": {
                    "type": instance_config.get("service_type", "ClusterIP"),
                }
            }
            
            # Add storage class for replicas if provided
            if instance_config.get("storage_class"):
                helm_values["replica"]["persistence"]["storageClass"] = instance_config["storage_class"]
            
            # Add service annotations for replicas if provided
            if instance_config.get("service_annotations"):
                helm_values["replica"]["service"]["annotations"] = instance_config["service_annotations"]
        
        # Add to Helm releases
        helm_releases.append({
            "name": f"{instance_slug}-redis",
            "chartPath": get_chart_path("./charts/redis"),
            "valuesFiles": [f"./values-{instance_slug}.yaml"],
            "namespace": namespace,
            "createNamespace": True,
            "wait": True,
            "upgradeOnChange": True
        })
        
        # Write values file for this instance
        with open(f"{output_dir}/values-{instance_slug}.yaml", "w") as file:
            yaml.dump(helm_values, file, default_flow_style=False)
        
        # Store instance information
        redis_host = f"{instance_slug}-master" if instance_config.get("architecture") == "standalone" else f"{instance_slug}-master"
        redis_port = 6379
        
        redis_instances_info.append({
            "slug": instance_slug,
            "host": redis_host,
            "port": redis_port,
            "architecture": instance_config.get("architecture", "standalone"),
            "auth_enabled": instance_config.get("auth_enabled", True),
            "password_secret": f"{instance_slug}-redis" if instance_config.get("auth_enabled", True) else None
        })
    
    # Generate skaffold.yaml
    skaffold_config = {
        "apiVersion": "skaffold/v3",
        "kind": "Config",
        "manifests": {
            "helm": {
                "releases": helm_releases
            }
        },
        "deploy": {
            "kubectl": {
                "defaultNamespace": namespace,
            },
        },
    }
    
    skaffold_yaml = yaml.dump(skaffold_config, default_flow_style=False)
    write(f"{output_dir}/skaffold-redis-instances.yaml", skaffold_yaml)
    
    # Generate fleet.yaml for dependencies
    fleet_config = {
        "dependsOn": [
            c.as_fleet_dependency for c in depends_on
        ] if depends_on else [],
        "helm": {
            "releaseName": f"{slug}-redis-instances",
        },
        "labels": {
            "name": f"{slug}-redis-instances"
        }
    }
    
    fleet_yaml = yaml.dump(fleet_config, default_flow_style=False)
    write(f"{output_dir}/fleet.yaml", fleet_yaml)
    
    # Create a summary file with instance details
    instances_summary = {
        "redis_instances": redis_instances_info
    }
    
    with open(f"{output_dir}/instances-summary.yaml", "w") as file:
        yaml.dump(instances_summary, file, default_flow_style=False)
    
    # Return Component object
    return Component(
        slug=slug,
        namespace=namespace,
        dir_name=dir_name,
        fleet_name=f"{slug}-redis-instances"
    )