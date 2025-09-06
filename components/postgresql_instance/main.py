import base64
import os
from typing import List, Optional, TypedDict, Dict

import yaml
from ilio import write

from components.base.component_types import Component
from components.base.constants import (
    GENERATED_SKAFFOLD_TMP_DIR,
)
from components.postgresql_instance.component_types import PostgresInstanceComponent
from components.postgresql_instance.constants import (
    POSTGRES_DEFAULT_VERSION,
    POSTGRES_DEFAULT_IMAGE
)


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


def create_postgres_instance(
    slug: str,
    namespace: str,
    db_name: str,
    superuser: str,
    superuser_password: str,
    username: str,
    user_password: str,
    replicas: int = 1,
    storage_size: str = "10Gi",
    wal_storage_size: str = "2Gi",
    repo_storage_size: str = "5Gi",
    ca_cert: str = "",
    tls_cert: str = "",
    tls_private_key: str = "",
    s3_backup: Optional[S3BackupConfig] = None,
    s3_bootstrap: Optional[S3BootstrapConfig] = None,
    service_type: str = "ClusterIP",
    service_annotations: Optional[Dict[str, str]] = None,
    depends_on: Optional[List[Component]] = None
) -> PostgresInstanceComponent:
    """
    Deploy a PostgreSQL instance using the PostgreSQL Operator.

    Args:
        slug: Unique identifier for the deployment
        namespace: Kubernetes namespace to deploy the component
        db_name: Name of the database to create
        superuser: Superuser username
        superuser_password: Superuser password
        username: Regular user username
        user_password: Regular user password
        replicas: Number of PostgreSQL replicas
        storage_size: Size of the PostgreSQL data volume
        wal_storage_size: Size of the WAL volume
        repo_storage_size: Size of the backup repository volume
        ca_cert: CA certificate for TLS (optional)
        tls_cert: TLS certificate (optional)
        tls_private_key: TLS private key (optional)
        s3_backup: Configuration for S3 backup repository (optional)
        s3_bootstrap: Configuration for S3 bootstrap repository (optional)
        service_type: Type of Kubernetes service (ClusterIP, LoadBalancer, etc.)
        service_annotations: Annotations to add to the service metadata
        depends_on: List of dependencies for Fleet

    Returns:
        Component object with metadata about the deployment
    """
    # Create directory structure
    dir_name = f"{slug}-postgres"
    output_dir = f'{GENERATED_SKAFFOLD_TMP_DIR}/{dir_name}'
    os.makedirs(output_dir, exist_ok=True)
    manifests_dir = f"{output_dir}/manifests"
    os.makedirs(manifests_dir, exist_ok=True)

    # Generate init SQL ConfigMap
    init_sql_manifest = {
        "apiVersion": "v1",
        "kind": "ConfigMap",
        "metadata": {
            "name": f"{slug}-init-pg-sql",
            "namespace": namespace
        },
        "data": {
            "init.sql": f"""
\\set ON_ERROR_STOP
\\c {db_name}
CREATE EXTENSION IF NOT EXISTS pg_cron;
CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE EXTENSION IF NOT EXISTS timescaledb;
CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS pg_stat_statements;
CREATE EXTENSION IF NOT EXISTS postgis_topology;
CREATE EXTENSION IF NOT EXISTS ltree;
CREATE EXTENSION IF NOT EXISTS plpython3u;
CREATE EXTENSION IF NOT EXISTS pg_trgm;

GRANT USAGE ON SCHEMA cron TO {username};
"""
        }
    }

    # Write init SQL ConfigMap
    with open(f"{manifests_dir}/init-pg-sql.yaml", "w") as file:
        yaml.dump(init_sql_manifest, file, default_flow_style=False)

    # Generate superuser Secret
    superuser_secret = {
        "apiVersion": "v1",
        "kind": "Secret",
        "metadata": {
            "annotations": {
                "sealedsecrets.bitnami.com/skip-set-owner-references": "true",
            },
            "labels": {
                "postgres-operator.crunchydata.com/cluster": f"{slug}-pg",
                "postgres-operator.crunchydata.com/pguser": superuser,
                "postgres-operator.crunchydata.com/role": "pguser",
            },
            "name": f"{slug}-pg-{superuser}-secret",
            "namespace": namespace
        },
        "type": "Opaque",
        "data": {
            "username": base64.b64encode(superuser.encode('ascii')).decode('ascii'),
            "password": base64.b64encode(superuser_password.encode('ascii')).decode('ascii')
        }
    }

    # Write superuser Secret
    with open(f"{manifests_dir}/superuser-secret.yaml", "w") as file:
        yaml.dump(superuser_secret, file, default_flow_style=False)

    # Generate regular user Secret
    user_secret = {
        "apiVersion": "v1",
        "kind": "Secret",
        "metadata": {
            "annotations": {
                "sealedsecrets.bitnami.com/skip-set-owner-references": "true",
            },
            "labels": {
                "postgres-operator.crunchydata.com/cluster": f"{slug}-pg",
                "postgres-operator.crunchydata.com/pguser": username,
                "postgres-operator.crunchydata.com/role": "pguser",
            },
            "name": f"{slug}-pg-{username}-secret",
            "namespace": namespace
        },
        "type": "Opaque",
        "data": {
            "username": base64.b64encode(username.encode('ascii')).decode('ascii'),
            "password": base64.b64encode(user_password.encode('ascii')).decode('ascii')
        }
    }

    # Write regular user Secret
    with open(f"{manifests_dir}/user-secret.yaml", "w") as file:
        yaml.dump(user_secret, file, default_flow_style=False)

    # Generate TLS Secret if certificates are provided
    if ca_cert and tls_cert and tls_private_key:
        tls_secret = {
            "apiVersion": "v1",
            "kind": "Secret",
            "metadata": {
                "annotations": {
                    "sealedsecrets.bitnami.com/skip-set-owner-references": "true",
                },
                "labels": {
                    "postgres-operator.crunchydata.com/cluster": f"{slug}-pg",
                    "postgres-operator.crunchydata.com/cluster-certificate": "postgres-tls",
                },
                "name": f"{slug}-pg-cluster-cert",
                "namespace": namespace
            },
            "type": "Opaque",
            "data": {
                "ca.crt": base64.b64encode(ca_cert.encode('ascii')).decode('ascii'),
                "tls.crt": base64.b64encode(tls_cert.encode('ascii')).decode('ascii'),
                "tls.key": base64.b64encode(tls_private_key.encode('ascii')).decode('ascii'),
            }
        }

        # Write TLS Secret
        with open(f"{manifests_dir}/cluster-cert.yaml", "w") as file:
            yaml.dump(tls_secret, file, default_flow_style=False)

    # Generate PostgreSQL Cluster manifest
    postgres_cluster = {
        "apiVersion": "postgres-operator.crunchydata.com/v1beta1",
        "kind": "PostgresCluster",
        "metadata": {
            "name": f"{slug}-pg",
            "namespace": namespace
        },
        "spec": {
            "image": POSTGRES_DEFAULT_IMAGE,
            "postgresVersion": POSTGRES_DEFAULT_VERSION,
            "databaseInitSQL": {
                "key": "init.sql",
                "name": f"{slug}-init-pg-sql"
            },
            "instances": [
                {
                    "name": "instance1",
                    "dataVolumeClaimSpec": {
                        "accessModes": [
                            "ReadWriteOnce"
                        ],
                        "resources": {
                            "requests": {
                                "storage": storage_size
                            }
                        }
                    },
                    "replicas": replicas,
                    "resources": {
                        "limits": {
                            "cpu": "1000m",
                            "memory": "2G"
                        },
                        "requests": {
                            "cpu": "200m",
                            "memory": "200Mi"
                        }
                    },
                    "walVolumeClaimSpec": {
                        "accessModes": [
                            "ReadWriteOnce"
                        ],
                        "resources": {
                            "requests": {
                                "storage": wal_storage_size
                            }
                        }
                    }
                }
            ],
            # Add dataSource if bootstrap is enabled
            **({"dataSource": {
                "postgresCluster": {
                    "clusterName": f"{slug}-pg",
                    "repoName": "repo3"
                }
            }} if s3_bootstrap and s3_bootstrap.get("enabled", False) else {}),

            "patroni": {
                "dynamicConfiguration": {
                    "postgresql": {
                        "parameters": {
                            "checkpoint_completion_target": "0.9",
                            "cron.database_name": db_name,
                            "cron.log_run": "on",
                            "cron.log_statement": "on",
                            "default_statistics_target": "500",
                            "effective_cache_size": "23040MB",
                            "effective_io_concurrency": "300",
                            "log_checkpoints": "on",
                            "log_lock_waits": "on",
                            "log_min_duration_statement": "1000",
                            "log_min_error_statement": "INFO",
                            "statement_timeout": "60000",
                            "log_min_messages": "ERROR",
                            "maintenance_work_mem": "512MB",
                            "max_connections": "500",
                            "max_parallel_maintenance_workers": "4",
                            "max_parallel_workers": "10",
                            "max_parallel_workers_per_gather": "4",
                            "max_wal_size": "200",
                            "max_worker_processes": "10",
                            "min_wal_size": "50",
                            "random_page_cost": "1.1",
                            "shared_buffers": "256MB",
                            "shared_preload_libraries": "timescaledb,pg_stat_statements,pg_cron,pg_trgm",
                            "wal_buffers": "12MB",
                            "wal_compression": "on",
                            "work_mem": "19660kB"
                        }
                    }
                }
            },
            "backups": {
                "pgbackrest": {
                    "global": {
                        "archive-async": "y",
                        "archive-timeout": "120",
                        "compress-level": "3",
                        "log-level-console": "info",
                        "log-level-file": "info",
                        "process-max": "4",
                        "repo1-retention-archive": "10",
                        "repo1-retention-archive-type": "incr",
                        "repo1-retention-full": "10",
                        "repo1-retention-full-type": "count",
                        "spool-path": "/pgdata/pgbackrest/pgbackrest-spool",

                        # Add S3 backup configuration if enabled
                        **({
                            "repo2-path": s3_backup["path"],
                            "repo2-s3-uri-style": "path",
                            "repo2-s3-key": s3_backup["access_key"],
                            "repo2-s3-key-secret": s3_backup["secret_key"],
                            "repo2-retention-archive": "30",
                            "repo2-retention-archive-type": "incr",
                            "repo2-retention-full": "30",
                            "repo2-retention-full-type": "count",
                           } if s3_backup and s3_backup.get("enabled", False) else {}),

                        # Add S3 bootstrap configuration if enabled
                        **({
                            "repo3-path": s3_bootstrap["path"],
                            "repo3-s3-uri-style": "path",
                            "repo3-path": s3_bootstrap["path"],
                            "repo3-s3-key": s3_bootstrap["access_key"],
                            "repo3-s3-key-secret": s3_bootstrap["secret_key"],
                            "repo3-retention-archive": "1",
                            "repo3-retention-archive-type": "incr",
                            "repo3-retention-full": "1",
                            "repo3-retention-full-type": "count",
                           } if s3_bootstrap and s3_bootstrap.get("enabled", False) else {}),
                    },

                    # Add manual backup configuration if S3 backup is enabled
                    **({"manual": {
                        "options": ["--type=full"],
                        "repoName": "repo2"
                    }} if s3_backup and s3_backup.get("enabled", False) else {}),

                    "repos": [
                        # Local volume repository (always present)
                        {
                            "name": "repo1",
                            "schedules": {
                                "full": "05 4 * * *",
                                "incremental": "05 1 * * *"
                            },
                            "volume": {
                                "volumeClaimSpec": {
                                    "accessModes": [
                                        "ReadWriteOnce"
                                    ],
                                    "resources": {
                                        "requests": {
                                            "storage": repo_storage_size
                                        }
                                    }
                                }
                            }
                        }
                    ] +
                    # S3 backup repository (if enabled)
                    ([{
                        "name": "repo2",
                        "schedules": {
                            "full": "15 23 * * *",
                            "incremental": "15 6 * * *"
                        },
                        "s3": {
                            "bucket": s3_backup["bucket"],
                            "endpoint": s3_backup["endpoint"],
                            "region": s3_backup["region"],
                        }
                    }] if s3_backup and s3_backup.get("enabled", False) else []) +
                    # S3 bootstrap repository (if enabled)
                    ([{
                        "name": "repo3",
                        "schedules": {},
                        "s3": {
                            "bucket": s3_bootstrap["bucket"],
                            "endpoint": s3_bootstrap["endpoint"],
                            "region": s3_bootstrap["region"],
                        }
                    }] if s3_bootstrap and s3_bootstrap.get("enabled", False) else [])
                }
            },

            "proxy": {
                "pgBouncer": {
                    "config": {
                        "global": {
                            "max_client_conn": "50",
                            "pool_mode": "session"
                        }
                    },
                    "replicas": replicas,
                    "resources": {
                        "requests": {
                            "cpu": "500m",
                            "memory": "256Mi"
                        }
                    },
                    "service": {
                        "type": "ClusterIP"
                    }
                }
            },
            "service": {
                "type": service_type,
                **({"metadata": {"annotations": service_annotations}} if service_annotations else {})
            },
            "users": [
                {
                    "databases": [
                        db_name
                    ],
                    "name": superuser,
                    "options": "SUPERUSER LOGIN",
                    "password": {
                        "type": "AlphaNumeric"
                    }
                },
                {
                    "databases": [
                        db_name
                    ],
                    "name": username,
                    "options": "SUPERUSER LOGIN",
                    "password": {
                        "type": "AlphaNumeric"
                    }
                }
            ]
        }
    }

    # Add TLS configuration if certificates are provided
    if ca_cert and tls_cert and tls_private_key:
        postgres_cluster["spec"]["customTLSSecret"] = {
            "name": f"{slug}-pg-cluster-cert"
        }

    # Write PostgreSQL Cluster manifest
    with open(f"{manifests_dir}/cluster.yaml", "w") as file:
        yaml.dump(postgres_cluster, file, default_flow_style=False)

    # Generate Service manifest for external access
    service_manifest = {
        "apiVersion": "v1",
        "kind": "Service",
        "metadata": {
            "name": f"{slug}-pg-lb",
            "namespace": namespace,
            "labels": {
                "postgres-operator.crunchydata.com/cluster": f"{slug}-pg"
            },
            **({"annotations": service_annotations} if service_annotations else {})
        },
        "spec": {
            "type": service_type,
            "ports": [
                {
                    "name": "postgres",
                    "port": 5432,
                    "protocol": "TCP",
                    "targetPort": 5432
                }
            ],
            "selector": {
                "postgres-operator.crunchydata.com/cluster": f"{slug}-pg",
                "postgres-operator.crunchydata.com/role": "master"
            }
        }
    }

    # Write Service manifest
    with open(f"{manifests_dir}/service.yaml", "w") as file:
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
                f"./manifests/init-pg-sql.yaml",
                f"./manifests/superuser-secret.yaml",
                f"./manifests/user-secret.yaml",
                f"./manifests/cluster.yaml",
                f"./manifests/service.yaml",
            ]
        }
    }

    # Add TLS Secret to rawYaml if certificates are provided
    if ca_cert and tls_cert and tls_private_key:
        skaffold_config["manifests"]["rawYaml"].append(f"./manifests/cluster-cert.yaml")

    skaffold_yaml = yaml.dump(skaffold_config, default_flow_style=False)
    write(f"{output_dir}/skaffold-postgres.yaml", skaffold_yaml)

    # Generate fleet.yaml for dependencies
    fleet_config = {
        "dependsOn": [
            c.as_fleet_dependency for c in depends_on
        ] if depends_on else [],
        "helm": {
            "releaseName": f"{slug}-postgres",
        },
        "labels": {
            "name": f"{slug}-postgres",
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
            ]
        },
    }

    fleet_yaml = yaml.dump(fleet_config, default_flow_style=False)
    write(f"{output_dir}/fleet.yaml", fleet_yaml)

    # Construct PostgreSQL URIs
    superuser_postgres_uri = f"postgres://{superuser}:{superuser_password}@{slug}-pg-primary.{namespace}:5432/{db_name}?sslmode=require"
    normal_user_postgres_uri = f"postgres://{username}:{user_password}@{slug}-pg-primary.{namespace}:5432/{db_name}?sslmode=require"

    # Return Component object
    return PostgresInstanceComponent(
        slug=slug,
        namespace=namespace,
        dir_name=dir_name,
        fleet_name=f"{slug}-postgres",
        superuser_postgres_uri=superuser_postgres_uri,
        normal_user_postgres_uri=normal_user_postgres_uri,
        depends_on=depends_on
    )
