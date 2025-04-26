import os
from typing import List, Optional
import yaml

from ilio import write

from components.base.component_types import Component
from components.base.constants import GENERATED_SKAFFOLD_TMP_DIR
from components.base.utils import get_chart_path


def create_postgresql_operator_crds(
        slug: str,
        namespace: str,
        depends_on: Optional[List[Component]] = None
) -> Component:
    # Create directory structure
    dir_name = f"{slug}-postgresql-operator-crds"
    output_dir = f'{GENERATED_SKAFFOLD_TMP_DIR}/{dir_name}'
    os.makedirs(output_dir, exist_ok=True)

    postgres_operator_chart_path = get_chart_path("./charts/postgres-operator")

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
                f"{postgres_operator_chart_path}/crds/postgres-operator.crunchydata.com_postgresclusters.yaml",
                f"{postgres_operator_chart_path}/crds/postgres-operator.crunchydata.com_pgupgrades.yaml",
                f"{postgres_operator_chart_path}/crds/postgres-operator.crunchydata.com_pgadmins.yaml",
                f"{postgres_operator_chart_path}/crds/postgres-operator.crunchydata.com_crunchybridgeclusters.yaml",
            ],
        },
    }

    skaffold_yaml = yaml.dump(skaffold_config, default_flow_style=False)
    write(f"{output_dir}/skaffold-postgresql-operator-crds.yaml", skaffold_yaml)

    # Generate fleet.yaml for dependencies
    fleet_config = {
        "dependsOn": [
            c.as_fleet_dependency for c in depends_on
        ] if depends_on else [],
        "helm": {
            "releaseName": f"{slug}-postgresql-operator-crds",
        },
        "labels": {
            "name": f"{slug}-postgresql-operator-crds",
        }
    }

    fleet_yaml = yaml.dump(fleet_config, default_flow_style=False)
    write(f"{output_dir}/fleet.yaml", fleet_yaml)

    # Return Component object
    return Component(
        slug=slug,
        namespace=namespace,
        dir_name=dir_name,
        fleet_name=f"{slug}-postgresql-operator-crds",
    )


def create_postgresql_operator(
        slug: str,
        namespace: str,
        depends_on: Optional[List[Component]] = None
) -> Component:
    # Create directory structure
    dir_name = f"{slug}-postgresql-operator"
    output_dir = f'{GENERATED_SKAFFOLD_TMP_DIR}/{dir_name}'
    os.makedirs(output_dir, exist_ok=True)
    manifests_dir = f"{output_dir}/manifests"
    os.makedirs(manifests_dir, exist_ok=True)

    # Generate Helm values
    helm_values = {
    }

    # Write values file
    with open(f"{output_dir}/values.yaml", "w") as file:
        yaml.dump(helm_values, file, default_flow_style=False)

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
            "helm": {
                "releases": [
                    {
                        "name": f"{slug}-postgresql-operator",
                        "chartPath": get_chart_path("./charts/postgres-operator"),
                        "valuesFiles": [
                            f"./values.yaml"
                        ],
                        "namespace": namespace,
                        "createNamespace": True,
                        "wait": True,
                        "upgradeOnChange": True
                    }
                ],
            },
            "rawYaml": [
            ],
        },
    }

    skaffold_yaml = yaml.dump(skaffold_config, default_flow_style=False)
    write(f"{output_dir}/skaffold-postgresql-operator.yaml", skaffold_yaml)

    # Generate fleet.yaml for dependencies
    fleet_config = {
        "dependsOn": [
            c.as_fleet_dependency for c in depends_on
        ] if depends_on else [],
        "helm": {
            "releaseName": f"{slug}-postgresql-operator",
        },
        "labels": {
            "name": f"{slug}-postgresql-operator"
        }
    }

    fleet_yaml = yaml.dump(fleet_config, default_flow_style=False)
    write(f"{output_dir}/fleet.yaml", fleet_yaml)

    # Return Component object
    return Component(
        slug=slug,
        namespace=namespace,
        dir_name=dir_name,
        fleet_name=f"{slug}-postgresql-operator",
    )
