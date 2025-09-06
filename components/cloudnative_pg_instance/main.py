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
from components.cloudnative_pg_instance.constants import CNPG_DEFAULT_IMAGE


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
        backup_schedule: Cron schedule for automatic backups (optional)
        retention_policy: Retention policy for backups (e.g., "30d") (optional)
    """
    enabled: bool
    endpoint: str
    bucket: str
    region: str
    access_key: str
    secret_key: str
    path: Optional[str]
    backup_schedule: Optional[str]
    retention_policy: Optional[str]


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
        server_name: Name of the server backup to restore from (default: cluster-example)
    """
    enabled: bool
    endpoint: str
    bucket: str
    region: str
    access_key: str
    secret_key: str
    path: str
    server_name: Optional[str]


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


def create_scheduled_backup_manifest(cluster_name: str, namespace: str, schedule: str = "0 2 * * *") -> dict:
    """
    Create a ScheduledBackup manifest for the Barman plugin.

    Args:
        cluster_name: Name of the PostgreSQL cluster
        namespace: Kubernetes namespace
        schedule: Cron schedule for backups (default: daily at 2 AM)

    Returns:
        ScheduledBackup manifest dictionary
    """
    return {
        "apiVersion": "postgresql.cnpg.io/v1",
        "kind": "ScheduledBackup",
        "metadata": {
            "name": f"{cluster_name}-scheduled-backup",
            "namespace": namespace
        },
        "spec": {
            "schedule": schedule,
            "backupOwnerReference": "self",
            "cluster": {
                "name": cluster_name
            },
            "method": "plugin",
            "pluginConfiguration": {
                "name": "barman-cloud.cloudnative-pg.io"
            }
        }
    }


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

    # Initialize resources list early to collect all resources
    resources = []

    # Default PostgreSQL parameters (excluding fixed configuration parameters)
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
        "log_min_duration_statement": "1000"
    }

    # Merge with custom parameters
    if postgresql_parameters:
        default_postgresql_params.update(postgresql_parameters)

    # Generate Helm values for CloudNative PG cluster
    cnpg_cluster_values = {
        "fullnameOverride": cluster_name,
        "mode": "recovery" if (s3_bootstrap and s3_bootstrap.get("enabled", False)) else "standalone",
        "cluster": {
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
                "podMonitor": {
                    "enabled": enable_monitoring
                }
            },
            "services": {
                "additional": [
                    {
                        "selectorType": "rw",
                        "serviceTemplate": {
                            "metadata": {
                                "name": f"{cluster_name}-rw-external",
                                "annotations": service_annotations,

                            },
                            "spec": {
                                "type": service_type
                            }
                        }
                    },
                    {
                        "selectorType": "ro",
                        "serviceTemplate": {
                            "metadata": {
                                "name": f"{cluster_name}-ro-external",
                                "annotations": service_annotations,
                            },
                            "spec": {
                                "type": service_type
                            }
                        }
                    }
                ]
            }
        },
        "backups": {
            "enabled": True,
            "retentionPolicy": "30d"
        }
    }

    # Configure Barman plugin instead of built-in backup
    if s3_backup and s3_backup.get("enabled", False):
        # Add plugin configuration to use Barman Cloud plugin for WAL archiving
        cnpg_cluster_values["cluster"]["plugins"] = [
            {
                "name": "barman-cloud.cloudnative-pg.io",
                "isWALArchiver": True,
                "parameters": {
                    "barmanObjectName": f"{cluster_name}-backup-store"
                }
            }
        ]
        # Remove built-in backup configuration as we're using the plugin
        cnpg_cluster_values["backups"]["enabled"] = False

    # Add bootstrap configuration if enabled
    if s3_bootstrap and s3_bootstrap.get("enabled", False):
        # Get server name from config or use default
        server_name = s3_bootstrap.get("server_name", "cluster-example")

        # Configure recovery values for Helm chart
        cnpg_cluster_values["recovery"] = {
            "method": "object_store",
            "clusterName": server_name,
            "database": db_name,
            "owner": superuser,
            "provider": "s3",
            "endpointURL": s3_bootstrap["endpoint"],
            "destinationPath": f"s3://{s3_bootstrap['bucket']}{s3_bootstrap.get('path', f'/{cluster_name}')}",
            "s3": {
                "region": s3_bootstrap["region"],
                "bucket": s3_bootstrap["bucket"],
                "path": s3_bootstrap.get("path", f'/{cluster_name}'),
                "accessKey": s3_bootstrap["access_key"],
                "secretKey": s3_bootstrap["secret_key"],
                "inheritFromIAMRole": False
            },
            "secret": {
                "create": True,
                "name": f"{cluster_name}-recovery-credentials"
            }
        }

    # Add database and user configuration
    # In recovery mode, initdb is handled differently by the Helm template
    if not (s3_bootstrap and s3_bootstrap.get("enabled", False)):
        cnpg_cluster_values["cluster"]["initdb"] = {
            "database": db_name,
            "owner": superuser,  # Superuser owns the database and has full access
            "secret": {
                "name": f"{cluster_name}-superuser-secret"
            },
            "postInitApplicationSQL": [
                f"GRANT CONNECT ON DATABASE {db_name} TO {username};",
                f"GRANT USAGE ON SCHEMA public TO {username};",
                f"GRANT CREATE ON SCHEMA public TO {username};",
                f"ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO {username};",
                f"ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT USAGE, SELECT ON SEQUENCES TO {username};"
            ]
        }
    else:
        # In recovery mode, we still need the initdb with secret for the test template
        cnpg_cluster_values["cluster"]["initdb"] = {
            "secret": {
                "name": f"{cluster_name}-superuser-secret"
            },
            "postInitApplicationSQL": [
                f"GRANT CONNECT ON DATABASE {db_name} TO {username};",
                f"GRANT USAGE ON SCHEMA public TO {username};",
                f"GRANT CREATE ON SCHEMA public TO {username};",
                f"ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO {username};",
                f"ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT USAGE, SELECT ON SEQUENCES TO {username};"
            ]
        }

    # Set the superuser secret for the cluster
    cnpg_cluster_values["cluster"]["superuserSecret"] = f"{cluster_name}-superuser-secret"

    # Configure the regular user with limited database access
    cnpg_cluster_values["cluster"]["roles"] = [
        {
            "name": username,
            "ensure": "present",
            "login": True,
            "passwordSecret": {
                "name": f"{cluster_name}-user-secret"
            }
        }
    ]


    # Create ObjectStore resource for Barman plugin if S3 backup is enabled
    if s3_backup and s3_backup.get("enabled", False):
        # First create S3 credentials secret
        s3_credentials_secret = {
            "apiVersion": "v1",
            "kind": "Secret",
            "metadata": {
                "name": f"{cluster_name}-s3-credentials",
                "namespace": namespace
            },
            "type": "Opaque",
            "stringData": {
                "ACCESS_KEY_ID": s3_backup["access_key"],
                "SECRET_ACCESS_KEY": s3_backup["secret_key"],
                "REGION": s3_backup["region"]
            }
        }
        resources.append(s3_credentials_secret)

        # Create ObjectStore resource for Barman plugin
        object_store = {
            "apiVersion": "barmancloud.cnpg.io/v1",
            "kind": "ObjectStore",
            "metadata": {
                "name": f"{cluster_name}-backup-store",
                "namespace": namespace
            },
            "spec": {
                "configuration": {
                    "destinationPath": f"s3://{s3_backup['bucket']}{s3_backup.get('path', f'/{cluster_name}')}",
                    "endpointURL": s3_backup["endpoint"],
                    "s3Credentials": {
                        "accessKeyId": {
                            "name": f"{cluster_name}-s3-credentials",
                            "key": "ACCESS_KEY_ID"
                        },
                        "secretAccessKey": {
                            "name": f"{cluster_name}-s3-credentials",
                            "key": "SECRET_ACCESS_KEY"
                        },
                        "region": {
                            "name": f"{cluster_name}-s3-credentials",
                            "key": "REGION"
                        }
                    },
                    "wal": {
                        "compression": "gzip",
                        "maxParallel": 8
                    },
                    "data": {
                        "compression": "gzip",
                        "jobs": 2,
                        "immediateCheckpoint": False
                    }
                },
                "retentionPolicy": s3_backup.get("retention_policy", "30d")
            }
        }
        resources.append(object_store)

        # Add scheduled backup if schedule is provided
        backup_schedule = s3_backup.get("backup_schedule")
        if backup_schedule:
            scheduled_backup = {
                "apiVersion": "postgresql.cnpg.io/v1",
                "kind": "ScheduledBackup",
                "metadata": {
                    "name": f"{cluster_name}-backup",
                    "namespace": namespace
                },
                "spec": {
                    "cluster": {
                        "name": cluster_name
                    },
                    "schedule": backup_schedule,
                    "backupOwnerReference": "self",
                    "method": "plugin",
                    "pluginConfiguration": {
                        "name": "barman-cloud.cloudnative-pg.io"
                    }
                }
            }
            resources.append(scheduled_backup)

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
    resources.append(superuser_secret)

    # Regular user secret - only create if different from superuser
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
        resources.append(user_secret)

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
                "./resources.yaml"
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
        "labels": {
            "name": f"{slug}-cnpg-cluster"
        },
        "diff": {
            "comparePatches": [
                {
                    "apiVersion": "postgresql.cnpg.io/v1",
                    "kind": "Cluster",
                    "name": cluster_name,
                    "operations": [
                        {
                            "op": "remove",
                            "path": "/status"
                        }
                    ]
                },
                {
                    "apiVersion": "bitnami.com/v1alpha1",
                    "kind": "SealedSecret",
                    "namespace": namespace,
                    "operations": [
                        {
                            "op": "remove",
                            "path": "/spec/encryptedData/password"
                        }
                    ]
                }
            ]
        }
    }

    # Write all configuration files
    write(f"{output_dir}/cnpg-cluster-values.yaml",
          yaml.dump(cnpg_cluster_values, default_flow_style=False))

    write(f"{output_dir}/resources.yaml",
          yaml.dump_all(resources, default_flow_style=False))

    write(f"{output_dir}/skaffold-cnpg-cluster.yaml",
          yaml.dump(skaffold_config, default_flow_style=False))

    write(f"{output_dir}/fleet.yaml",
          yaml.dump(fleet_config, default_flow_style=False))

    # Construct PostgreSQL connection URIs
    # Use the default rw service for internal connections and external service for external access
    default_rw_service = f"{cluster_name}-rw"  # Default CloudNative PG read-write service
    external_rw_service = f"{cluster_name}-rw-external"  # Custom external service
    ro_service = f"{cluster_name}-ro-external"  # Custom read-only service

    superuser_postgres_uri = f"postgresql://{superuser}:{superuser_password}@{default_rw_service}.{namespace}:5432/{db_name}?sslmode=require"
    normal_user_postgres_uri = f"postgresql://{username}:{user_password}@{default_rw_service}.{namespace}:5432/{db_name}?sslmode=require"

    # Additional connection URIs for external services
    external_rw_postgres_uri = f"postgresql://{username}:{user_password}@{external_rw_service}.{namespace}:5432/{db_name}?sslmode=require"
    readonly_postgres_uri = f"postgresql://{username}:{user_password}@{ro_service}.{namespace}:5432/{db_name}?sslmode=require"

    return CloudNativePgInstanceComponent(
        slug=slug,
        namespace=namespace,
        dir_name=dir_name,
        fleet_name=f"{slug}-cnpg-cluster",
        depends_on=depends_on,
        superuser_postgres_uri=superuser_postgres_uri,
        normal_user_postgres_uri=normal_user_postgres_uri,
        cluster_name=cluster_name
    )
