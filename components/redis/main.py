import os
from typing import List, Optional

import yaml
from ilio import write

from components.base.component_types import Component
from components.base.constants import GENERATED_SKAFFOLD_TMP_DIR
from components.base.utils import get_chart_path
from components.redis.component_types import RedisComponent


def create_redis(
        slug: str,
        namespace: str,
        password: str,
        storage_size: str = "5Gi",
        replicas: int = 1,
        depends_on: Optional[List[Component]] = None
) -> RedisComponent:
    # Create directory structure
    dir_name = f"{slug}-redis"
    output_dir = f'{GENERATED_SKAFFOLD_TMP_DIR}/{dir_name}'
    os.makedirs(output_dir, exist_ok=True)
    manifests_dir = f"{output_dir}/manifests"
    os.makedirs(manifests_dir, exist_ok=True)

    # Generate Helm values
    helm_values = {
        "nameOverride": f"{slug}-redis",
        "auth": {
            "password": password,
        },
        "master": {
            "disableCommands": [],
            "persistence": {
                "size": storage_size,
            }
        },
        "replica": {
            "replicaCount": replicas,
            "revisionHistoryLimit": 0,
        },
    }

    # Write values file
    with open(f"{output_dir}/values.yaml", "w") as file:
        yaml.dump(helm_values, file, default_flow_style=False)

    # Generate skaffold.yaml
    skaffold_config = {
        "apiVersion": "skaffold/v3",
        "kind": "Config",
        "manifests": {
            "helm": {
                "releases": [
                    {
                        "name": f"{slug}-redis",
                        "chartPath": get_chart_path("./charts/redis"),
                        "valuesFiles": [
                            f"./values.yaml"
                        ],
                        "namespace": namespace,
                        "createNamespace": True,
                        "wait": True,
                        "upgradeOnChange": True,
                    },
                ],
            },
            "rawYaml": [
            ],
        },
        "deploy": {
            "kubectl": {
                "defaultNamespace": namespace,
            },
        },
    }

    skaffold_yaml = yaml.dump(skaffold_config, default_flow_style=False)
    write(f"{output_dir}/skaffold-redis.yaml", skaffold_yaml)

    # Generate fleet.yaml for dependencies
    fleet_config = {
        "dependsOn": [
            c.as_fleet_dependency for c in depends_on
        ] if depends_on else [],
        "helm": {
            "releaseName": f"{slug}-redis",
        },
        "labels": {
            "name": f"{slug}-redis"
        }
    }

    fleet_yaml = yaml.dump(fleet_config, default_flow_style=False)
    write(f"{output_dir}/fleet.yaml", fleet_yaml)

    redis_uri = f"redis://:{password}@{slug}-redis-master.{namespace}.svc.cluster.local:6379/0"

    # Return Component object
    return RedisComponent(
        slug=slug,
        namespace=namespace,
        dir_name=dir_name,
        fleet_name=f"{slug}-redis",
        redis_uri=redis_uri,
    )
