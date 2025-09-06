import os
from typing import List, Optional, TypedDict, Dict, Any
import yaml

from ilio import write

from components.base.component_types import Component
from components.base.constants import GENERATED_SKAFFOLD_TMP_DIR
from components.base.utils import get_chart_path


class Neo4jInstanceConfig(TypedDict, total=False):
    """
    Configuration for a single Neo4j instance.
    
    Attributes:
        slug: Unique identifier for this instance
        auth_enabled: Whether authentication is enabled (optional, default: True)
        password: Neo4j password (optional, will be set to 'dev-password' if not provided)
        neo4j_edition: Neo4j edition - "community" or "enterprise" (optional, default: "community")
        storage_size: Size of the Neo4j data volume (optional, default: "10Gi")
        storage_class: Storage class for persistent volumes (optional)
        resources_requests_memory: Memory request (optional, default: "512Mi")
        resources_requests_cpu: CPU request (optional, default: "250m")
        resources_limits_memory: Memory limit (optional, default: "2Gi")
        resources_limits_cpu: CPU limit (optional, default: "1000m")
        metrics_enabled: Whether to enable metrics (optional, default: True)
        service_type: Type of Kubernetes service (optional, default: "ClusterIP")
        service_annotations: Annotations to add to the service metadata (optional)
        image_registry: Neo4j image registry (optional, default: "docker.io")
        image_repository: Neo4j image repository (optional, default: "bitnami/neo4j")
        image_tag: Neo4j image tag (optional, default: "5.26.0")
    """
    slug: str
    auth_enabled: Optional[bool]
    password: Optional[str]
    neo4j_edition: Optional[str]  # "community" or "enterprise"
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
    ingress_enabled: Optional[bool]
    ingress_host: Optional[str]
    ingress_class_name: Optional[str]
    ingress_tls_secret: Optional[str]
    ingress_annotations: Optional[Dict[str, str]]


def create_neo4j_instances(
    slug: str,
    namespace: str,
    instances: List[Neo4jInstanceConfig],
    depends_on: Optional[List[Component]] = None
) -> Component:
    """
    Deploy multiple Neo4j instances using the Bitnami Neo4j Helm chart.
    
    Args:
        slug: Unique identifier for the deployment
        namespace: Kubernetes namespace to deploy all instances
        instances: List of Neo4j instance configurations
        depends_on: List of dependencies for Fleet
        
    Returns:
        Component object with metadata about the deployment
    """
    # Create directory structure
    dir_name = f"{slug}-neo4j-instances"
    output_dir = f'{GENERATED_SKAFFOLD_TMP_DIR}/{dir_name}'
    os.makedirs(output_dir, exist_ok=True)
    
    # Store Neo4j instance information
    neo4j_instances_info = []
    
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
                "repository": instance_config.get("image_repository", "bitnami/neo4j"),
                "tag": instance_config.get("image_tag", "5.26.0")
            },
            "auth": {
                "enabled": instance_config.get("auth_enabled", True),
                "password": instance_config.get("password", "dev-password"),
                "username": "neo4j"
            },
            "neo4j": {
                "edition": instance_config.get("neo4j_edition", "community"),
                "acceptLicenseAgreement": "yes" if instance_config.get("neo4j_edition") == "enterprise" else "no",
                "defaultDatabase": "neo4j"
            },
            "persistence": {
                "enabled": True,
                "size": instance_config.get("storage_size", "10Gi"),
                "storageClass": instance_config.get("storage_class", "")
            },
            "service": {
                "type": instance_config.get("service_type", "ClusterIP"),
                "annotations": instance_config.get("service_annotations", {})
            },
            "resources": {
                "requests": {
                    "memory": instance_config.get("resources_requests_memory", "512Mi"),
                    "cpu": instance_config.get("resources_requests_cpu", "250m")
                },
                "limits": {
                    "memory": instance_config.get("resources_limits_memory", "2Gi"),
                    "cpu": instance_config.get("resources_limits_cpu", "1000m")
                }
            },
            "metrics": {
                "enabled": instance_config.get("metrics_enabled", True),
                "serviceMonitor": {
                    "enabled": instance_config.get("metrics_enabled", True)
                }
            }
        }
        
        # Configure ingress if enabled
        if instance_config.get("ingress_enabled", False):
            ingress_annotations = instance_config.get("ingress_annotations", {})
            # Add default NGINX annotations for Neo4j
            default_annotations = {
                "nginx.ingress.kubernetes.io/proxy-body-size": "50m",
                "nginx.ingress.kubernetes.io/proxy-read-timeout": "600",
                "nginx.ingress.kubernetes.io/proxy-send-timeout": "600",
                "nginx.ingress.kubernetes.io/backend-protocol": "HTTP"
            }
            # Merge default and custom annotations
            ingress_annotations = {**default_annotations, **ingress_annotations}
            
            helm_values["ingress"] = {
                "enabled": True,
                "hostname": instance_config.get("ingress_host", f"neo4j-{instance_slug}.example.com"),
                "ingressClassName": instance_config.get("ingress_class_name", "nginx"),
                "annotations": ingress_annotations,
                "tls": False,  # Disable automatic TLS generation
                "extraTls": [{
                    "hosts": [instance_config.get("ingress_host", f"neo4j-{instance_slug}.example.com")],
                    "secretName": instance_config.get("ingress_tls_secret")
                }] if instance_config.get("ingress_tls_secret") else []
            }
        
        # Write values file for this instance
        with open(f"{output_dir}/values-{instance_slug}.yaml", "w") as file:
            yaml.dump(helm_values, file, default_flow_style=False)
        
        # Store instance information for reference
        neo4j_instances_info.append({
            "name": instance_slug,
            "host": f"{instance_slug}.{namespace}.svc.cluster.local",
            "bolt_port": 7687,
            "http_port": 7474,
            "auth_enabled": instance_config.get("auth_enabled", True),
            "username": "neo4j",
            "password": instance_config.get("password", "dev-password")
        })
    
    # Generate skaffold.yaml with Helm releases
    helm_releases_config = []
    for instance_config in instances:
        instance_slug = instance_config["slug"]
        helm_releases_config.append({
            "name": f"{instance_slug}-neo4j",
            "chartPath": get_chart_path("./charts/neo4j"),
            "valuesFiles": [f"./values-{instance_slug}.yaml"],
            "namespace": namespace,
            "createNamespace": True,
            "wait": True,
            "upgradeOnChange": True
        })
    
    skaffold_config = {
        "apiVersion": "skaffold/v3",
        "kind": "Config",
        "manifests": {
            "helm": {
                "releases": helm_releases_config
            }
        },
        "deploy": {
            "kubectl": {
                "defaultNamespace": namespace,
            },
        },
    }
    
    skaffold_yaml = yaml.dump(skaffold_config, default_flow_style=False)
    write(f"{output_dir}/skaffold-neo4j-instances.yaml", skaffold_yaml)
    
    # Generate fleet.yaml for dependencies
    fleet_config = {
        "dependsOn": [
            c.as_fleet_dependency for c in depends_on
        ] if depends_on else [],
        "helm": {
            "releaseName": f"{slug}-neo4j-instances",
        },
        "labels": {
            "name": f"{slug}-neo4j-instances"
        }
    }
    
    fleet_yaml = yaml.dump(fleet_config, default_flow_style=False)
    write(f"{output_dir}/fleet.yaml", fleet_yaml)
    
    # Create a summary file with instance details
    summary = {
        "neo4j_instances": neo4j_instances_info,
        "namespace": namespace,
        "component": f"{slug}-neo4j-instances"
    }
    
    write(f"{output_dir}/neo4j-instances-summary.yaml", yaml.dump(summary, default_flow_style=False))
    
    # Create component metadata
    component = Component(
        slug=slug,
        namespace=namespace,
        dir_name=dir_name,
        fleet_name=f"{slug}-neo4j-instances"
    )
    
    return component