import os
from typing import List, Optional, TypedDict, Dict, Any
import yaml

from ilio import write

from components.base.component_types import Component
from components.base.constants import GENERATED_SKAFFOLD_TMP_DIR
from components.postgresql_instance.main import create_postgres_instance, S3BackupConfig, S3BootstrapConfig
from components.postgresql_instance.component_types import PostgresInstanceComponent


class PostgresInstanceConfig(TypedDict, total=False):
    """
    Configuration for a single PostgreSQL instance.
    
    Attributes:
        slug: Unique identifier for this instance
        db_name: Name of the database to create
        superuser: Superuser username
        superuser_password: Superuser password
        username: Regular user username
        user_password: Regular user password
        replicas: Number of PostgreSQL replicas (optional, default: 1)
        storage_size: Size of the PostgreSQL data volume (optional, default: "10Gi")
        wal_storage_size: Size of the WAL volume (optional, default: "2Gi")
        repo_storage_size: Size of the backup repository volume (optional, default: "5Gi")
        ca_cert: CA certificate for TLS (optional)
        tls_cert: TLS certificate (optional)
        tls_private_key: TLS private key (optional)
        s3_backup: Configuration for S3 backup repository (optional)
        s3_bootstrap: Configuration for S3 bootstrap repository (optional)
        service_type: Type of Kubernetes service (optional, default: "ClusterIP")
        service_annotations: Annotations to add to the service metadata (optional)
    """
    slug: str
    db_name: str
    superuser: str
    superuser_password: str
    username: str
    user_password: str
    replicas: Optional[int]
    storage_size: Optional[str]
    wal_storage_size: Optional[str]
    repo_storage_size: Optional[str]
    ca_cert: Optional[str]
    tls_cert: Optional[str]
    tls_private_key: Optional[str]
    s3_backup: Optional[S3BackupConfig]
    s3_bootstrap: Optional[S3BootstrapConfig]
    service_type: Optional[str]
    service_annotations: Optional[Dict[str, str]]


def create_postgresql_instances(
    slug: str,
    namespace: str,
    instances: List[PostgresInstanceConfig],
    depends_on: Optional[List[Component]] = None
) -> Component:
    """
    Deploy multiple PostgreSQL instances using the PostgreSQL Operator.
    
    Args:
        slug: Unique identifier for the deployment
        namespace: Kubernetes namespace to deploy all instances
        instances: List of PostgreSQL instance configurations
        depends_on: List of dependencies for Fleet
        
    Returns:
        Component object with metadata about the deployment and list of created instances
    """
    # Create directory structure
    dir_name = f"{slug}-postgresql-instances"
    output_dir = f'{GENERATED_SKAFFOLD_TMP_DIR}/{dir_name}'
    os.makedirs(output_dir, exist_ok=True)
    
    # Create individual PostgreSQL instances
    postgres_instances = []
    skaffold_configs = []
    fleet_dependencies = []
    
    for instance_config in instances:
        # Set defaults for optional fields
        instance_slug = instance_config["slug"]
        
        # Create individual PostgreSQL instance
        postgres_instance = create_postgres_instance(
            slug=instance_slug,
            namespace=namespace,
            db_name=instance_config["db_name"],
            superuser=instance_config["superuser"],
            superuser_password=instance_config["superuser_password"],
            username=instance_config["username"],
            user_password=instance_config["user_password"],
            replicas=instance_config.get("replicas", 1),
            storage_size=instance_config.get("storage_size", "10Gi"),
            wal_storage_size=instance_config.get("wal_storage_size", "2Gi"),
            repo_storage_size=instance_config.get("repo_storage_size", "5Gi"),
            ca_cert=instance_config.get("ca_cert", ""),
            tls_cert=instance_config.get("tls_cert", ""),
            tls_private_key=instance_config.get("tls_private_key", ""),
            s3_backup=instance_config.get("s3_backup"),
            s3_bootstrap=instance_config.get("s3_bootstrap"),
            service_type=instance_config.get("service_type", "ClusterIP"),
            service_annotations=instance_config.get("service_annotations"),
            depends_on=depends_on
        )
        
        postgres_instances.append(postgres_instance)
        
        # Create Fleet dependency for this instance
        fleet_dependencies.append({
            "name": postgres_instance.fleet_name,
            "selector": {
                "matchLabels": {
                    "name": postgres_instance.fleet_name
                }
            }
        })
        
        # Add to skaffold config references (for combined deployment)
        skaffold_configs.append({
            "path": f"../{postgres_instance.dir_name}/skaffold-postgres.yaml"
        })
    
    # Generate combined skaffold.yaml for all instances
    combined_skaffold_config = {
        "apiVersion": "skaffold/v3",
        "kind": "Config",
        "requires": skaffold_configs,
        "deploy": {
            "kubectl": {
                "defaultNamespace": namespace,
            }
        }
    }
    
    combined_skaffold_yaml = yaml.dump(combined_skaffold_config, default_flow_style=False)
    write(f"{output_dir}/skaffold-postgresql-instances.yaml", combined_skaffold_yaml)
    
    # Generate fleet.yaml for managing all instances
    fleet_config = {
        "dependsOn": [
            c.as_fleet_dependency for c in depends_on
        ] if depends_on else [],
        "helm": {
            "releaseName": f"{slug}-postgresql-instances",
        },
        "labels": {
            "name": f"{slug}-postgresql-instances"
        }
    }
    
    fleet_yaml = yaml.dump(fleet_config, default_flow_style=False)
    write(f"{output_dir}/fleet.yaml", fleet_yaml)
    
    # Create a summary file with instance details
    instances_summary = {
        "postgresql_instances": [
            {
                "slug": instance.slug,
                "namespace": instance.namespace,
                "fleet_name": instance.fleet_name,
                "superuser_postgres_uri": instance.superuser_postgres_uri,
                "normal_user_postgres_uri": instance.normal_user_postgres_uri,
            }
            for instance in postgres_instances
        ]
    }
    
    with open(f"{output_dir}/instances-summary.yaml", "w") as file:
        yaml.dump(instances_summary, file, default_flow_style=False)
    
    # Return Component object
    return Component(
        slug=slug,
        namespace=namespace,
        dir_name=dir_name,
        fleet_name=f"{slug}-postgresql-instances"
    )