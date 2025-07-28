"""
CloudNative PostgreSQL Instance Component

This module provides functionality to deploy PostgreSQL cluster instances 
using the CloudNative PostgreSQL operator with the cluster Helm chart.
"""

import os
import yaml
import base64
from typing import List, Optional, TypedDict, Dict, Any
from ilio import write

from components.cloudnative_pg_instance.component_types import CloudNativePgInstanceComponent
from components.base.component_types import Component
from components.base.constants import GENERATED_SKAFFOLD_TMP_DIR
from components.base.utils import get_chart_path
from components.cloudnative_pg_instance.constants import CNPG_DEFAULT_VERSION, CNPG_DEFAULT_IMAGE


class S3BackupConfig(TypedDict, total=False):
    """
    Configuration for S3 backup repository.
    
    Attributes:
        enabled: Whether S3 backup is enabled
        endpoint: S3 endpoint URL
        bucket: S3 bucket name
        region: S3 region
        access_key: S3 access key
        secret_key: S3 secret key
        path: Path within the bucket (optional)
    """
    enabled: bool
    endpoint: str
    bucket: str
    region: str
    access_key: str
    secret_key: str
    path: Optional[str]


class S3BootstrapConfig(TypedDict, total=False):
    """
    Configuration for S3 bootstrap repository.
    
    Attributes:
        enabled: Whether S3 bootstrap is enabled
        endpoint: S3 endpoint URL
        bucket: S3 bucket name
        region: S3 region
        access_key: S3 access key
        secret_key: S3 secret key
        path: Path within the bucket
    """
    enabled: bool
    endpoint: str
    bucket: str
    region: str
    access_key: str
    secret_key: str
    path: str


class CloudNativePgInstanceConfig(TypedDict, total=False):
    """
    Configuration for CloudNative PostgreSQL instance deployment.
    
    Attributes:
        slug: Unique identifier for the deployment
        namespace: Kubernetes namespace to deploy the cluster
        db_name: Name of the database to create
        superuser: Superuser username (default: postgres)
        superuser_password: Superuser password
        username: Regular user username (default: app)
        user_password: Regular user password
        instances: Number of PostgreSQL instances in the cluster
        storage_size: Size of the PostgreSQL data volume
        s3_backup: Configuration for S3 backup repository (optional)
        s3_bootstrap: Configuration for S3 bootstrap repository (optional)
        service_type: Type of Kubernetes service (ClusterIP, LoadBalancer, etc.)
        service_annotations: Annotations to add to the service metadata
        enable_monitoring: Whether to enable monitoring with PodMonitor
        postgresql_parameters: Custom PostgreSQL configuration parameters
        depends_on: List of dependencies for Fleet
    """
    slug: str
    namespace: str
    db_name: str
    superuser: str
    superuser_password: str
    username: str
    user_password: str
    instances: int
    storage_size: str
    s3_backup: Optional[S3BackupConfig]
    s3_bootstrap: Optional[S3BootstrapConfig]
    service_type: str
    service_annotations: Optional[Dict[str, str]]
    enable_monitoring: bool
    postgresql_parameters: Optional[Dict[str, Any]]
    depends_on: Optional[List[Component]]


def create_cloudnative_pg_instance(config: CloudNativePgInstanceConfig) -> CloudNativePgInstanceComponent:
    """
    Deploy a CloudNative PostgreSQL cluster instance using Helm.
    
    Args:
        config: Typed configuration object containing all deployment parameters
        
    Returns:
        CloudNativePgInstanceComponent object with metadata about the deployment
    """
    # Extract configuration values
    slug = config["slug"]
    namespace = config["namespace"]
    db_name = config["db_name"]
    superuser = config.get("superuser", "postgres")
    superuser_password = config["superuser_password"]
    username = config.get("username", "app")
    user_password = config["user_password"]
    instances = config.get("instances", 1)
    storage_size = config.get("storage_size", "10Gi")
    s3_backup = config.get("s3_backup")
    s3_bootstrap = config.get("s3_bootstrap")
    service_type = config.get("service_type", "ClusterIP")
    service_annotations = config.get("service_annotations")
    enable_monitoring = config.get("enable_monitoring", True)
    postgresql_parameters = config.get("postgresql_parameters")
    depends_on = config.get("depends_on")

    # Create directory structure
    dir_name = f"{slug}-cnpg-cluster"
    output_dir = f'{GENERATED_SKAFFOLD_TMP_DIR}/{dir_name}'
    os.makedirs(output_dir, exist_ok=True)

    cluster_name = f"{slug}-pg"
    
    # Default PostgreSQL parameters
    default_postgresql_params = {
        "max_connections": "200",
        "shared_buffers": "128MB",
        "effective_cache_size": "512MB",
        "maintenance_work_mem": "64MB",
        "checkpoint_completion_target": "0.9",
        "wal_buffers": "16MB",
        "default_statistics_target": "100",
        "random_page_cost": "1.1",
        "effective_io_concurrency": "200",
        "work_mem": "4MB",
        "min_wal_size": "1GB",
        "max_wal_size": "4GB",
        "log_checkpoints": "on",
        "log_connections": "on",
        "log_disconnections": "on",
        "log_lock_waits": "on",
        "log_min_duration_statement": "1000",
        "shared_preload_libraries": "pg_stat_statements"
    }
    
    # Merge with custom parameters
    if postgresql_parameters:
        default_postgresql_params.update(postgresql_parameters)

    # Generate Helm values for CloudNative PG cluster
    cnpg_cluster_values = {
        "cluster": {
            "name": cluster_name,
            "instances": instances,
            "imageName": CNPG_DEFAULT_IMAGE,
            "postgresql": {
                "parameters": default_postgresql_params
            },
            "storage": {
                "size": storage_size,
                "storageClass": ""  # Use default storage class
            },
            "monitoring": {
                "enabled": enable_monitoring,
                "podMonitorEnabled": enable_monitoring
            }
        },
        "backup": {
            "enabled": True,
            "retentionPolicy": "30d"
        }
    }

    # Add S3 backup configuration if enabled
    if s3_backup and s3_backup.get("enabled", False):
        cnpg_cluster_values["backup"]["s3"] = {
            "bucket": s3_backup["bucket"],
            "endpoint": s3_backup["endpoint"],
            "region": s3_backup["region"],
            "path": s3_backup.get("path", f"/{cluster_name}"),
            "credentials": {
                "accessKeyId": s3_backup["access_key"],
                "secretAccessKey": s3_backup["secret_key"]
            }
        }

    # Add bootstrap configuration if enabled
    if s3_bootstrap and s3_bootstrap.get("enabled", False):
        cnpg_cluster_values["cluster"]["bootstrap"] = {
            "recovery": {
                "source": "bootstrap-source",
                "recoveryTarget": {
                    "targetTime": ""  # Latest available
                }
            }
        }
        cnpg_cluster_values["externalClusters"] = {
            "bootstrap-source": {
                "barmanObjectStore": {
                    "destinationPath": s3_bootstrap["path"],
                    "s3Credentials": {
                        "accessKeyId": s3_bootstrap["access_key"],
                        "secretAccessKey": s3_bootstrap["secret_key"],
                        "region": s3_bootstrap["region"]
                    },
                    "endpointURL": s3_bootstrap["endpoint"],
                    "wal": {
                        "maxParallel": 8
                    }
                }
            }
        }

    # Add database and user configuration
    cnpg_cluster_values["cluster"]["initdb"] = {
        "database": db_name,
        "owner": superuser,
        "secret": {
            "name": f"{cluster_name}-superuser-secret"
        }
    }

    # Generate secrets for users
    secrets = []
    
    # Superuser secret
    superuser_secret = {
        "apiVersion": "v1",
        "kind": "Secret",
        "metadata": {
            "name": f"{cluster_name}-superuser-secret",
            "namespace": namespace
        },
        "type": "kubernetes.io/basic-auth",
        "data": {
            "username": base64.b64encode(superuser.encode('ascii')).decode('ascii'),
            "password": base64.b64encode(superuser_password.encode('ascii')).decode('ascii')
        }
    }
    secrets.append(superuser_secret)

    # Regular user secret
    if username != superuser:
        user_secret = {
            "apiVersion": "v1",
            "kind": "Secret",
            "metadata": {
                "name": f"{cluster_name}-user-secret",
                "namespace": namespace
            },
            "type": "kubernetes.io/basic-auth",
            "data": {
                "username": base64.b64encode(username.encode('ascii')).decode('ascii'),
                "password": base64.b64encode(user_password.encode('ascii')).decode('ascii')
            }
        }
        secrets.append(user_secret)

    # Generate Skaffold configuration
    skaffold_config = {
        "apiVersion": "skaffold/v3",
        "kind": "Config",
        "build": {
            "artifacts": [],
        },
        "manifests": {
            "helm": {
                "releases": [
                    {
                        "name": f"{slug}-cnpg-cluster",
                        "namespace": namespace,
                        "chartPath": get_chart_path("./charts/cluster"),
                        "createNamespace": False,
                        "valuesFiles": [
                            "./cnpg-cluster-values.yaml"
                        ]
                    },
                ]
            },
            "rawYaml": [
                "./secrets.yaml"
            ]
        },
        "deploy": {
            "kubectl": {}
        },
    }
    
    # Generate Fleet configuration
    fleet_config = {
        "dependsOn": [
            c.as_fleet_dependency for c in depends_on
        ] if depends_on else [],
        "helm": {
            "releaseName": f"{slug}-cnpg-cluster",
        },
        "labels": {
            "name": f"{slug}-cnpg-cluster",
        },
        "diff": {
            "comparePatches": [
                {
                    "apiVersion": "v1",
                    "kind": "Secret",
                    "jsonPointers": [
                        "/data",
                    ]
                },
                {
                    "apiVersion": "postgresql.cnpg.io/v1",
                    "kind": "Cluster",
                    "name": cluster_name,
                    "operations": [
                        {
                            "op": "remove",
                            "path": "/status"
                        },
                    ]
                }
            ]
        }
    }

    # Write all configuration files
    write(f"{output_dir}/cnpg-cluster-values.yaml", 
          yaml.dump(cnpg_cluster_values, default_flow_style=False))
    
    write(f"{output_dir}/secrets.yaml", 
          yaml.dump_all(secrets, default_flow_style=False))
    
    write(f"{output_dir}/skaffold-cnpg-cluster.yaml", 
          yaml.dump(skaffold_config, default_flow_style=False))
    
    write(f"{output_dir}/fleet.yaml", 
          yaml.dump(fleet_config, default_flow_style=False))

    # Construct PostgreSQL connection URIs
    service_name = f"{cluster_name}-rw"  # CloudNative PG creates read-write service with -rw suffix
    superuser_postgres_uri = f"postgresql://{superuser}:{superuser_password}@{service_name}.{namespace}:5432/{db_name}?sslmode=require"
    normal_user_postgres_uri = f"postgresql://{username}:{user_password}@{service_name}.{namespace}:5432/{db_name}?sslmode=require"

    return CloudNativePgInstanceComponent(
        slug=slug,
        namespace=namespace,
        dir_name=dir_name,
        fleet_name=f"{slug}-cnpg-cluster",
        superuser_postgres_uri=superuser_postgres_uri,
        normal_user_postgres_uri=normal_user_postgres_uri,
        cluster_name=cluster_name
    )