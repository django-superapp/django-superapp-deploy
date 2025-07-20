from typing import Dict, List, Optional
import os
import yaml
from ilio import write

from components.base.component_types import Component
from components.base.constants import GENERATED_SKAFFOLD_TMP_DIR
from components.base.utils import get_chart_path
from components.librechat.constants import LIBRECHAT_DEFAULT_IMAGE, LIBRECHAT_DEFAULT_TAG


def create_librechat(
    slug: str,
    namespace: str,
    image_repository: str = LIBRECHAT_DEFAULT_IMAGE,
    image_tag: str = LIBRECHAT_DEFAULT_TAG,
    replicas: int = 1,
    env_vars: Optional[Dict[str, str]] = None,
    ingress_enabled: bool = True,
    ingress_host: Optional[str] = None,
    ingress_class_name: str = "nginx",
    ingress_tls_secret: Optional[str] = None,
    mongodb_enabled: bool = True,
    meilisearch_enabled: bool = True,
    meilisearch_master_key: Optional[str] = None,
    openai_api_key: Optional[str] = None,
    custom_yaml_config: Optional[str] = None,
    depends_on: Optional[List[Component]] = None
) -> Component:
    """
    Deploy LibreChat using Helm.

    Args:
        slug: Unique identifier for the deployment
        namespace: Kubernetes namespace to deploy the component
        image_repository: Docker image repository
        image_tag: Docker image tag
        replicas: Number of replicas to deploy
        env_vars: Environment variables for the deployment
        ingress_enabled: Whether to enable ingress
        ingress_host: Hostname for ingress
        ingress_class_name: Ingress class name
        ingress_tls_secret: TLS secret name for ingress
        mongodb_enabled: Whether to enable MongoDB
        meilisearch_enabled: Whether to enable Meilisearch
        meilisearch_master_key: Meilisearch master key
        openai_api_key: OpenAI API key for LibreChat
        custom_yaml_config: Custom YAML configuration for LibreChat
        depends_on: List of dependencies for Fleet

    Returns:
        Component object with metadata about the deployment
    """
    # Create directory structure
    dir_name = f"{slug}-librechat"
    output_dir = f'{GENERATED_SKAFFOLD_TMP_DIR}/{dir_name}'
    os.makedirs(output_dir, exist_ok=True)
    manifests_dir = f"{output_dir}/manifests"
    os.makedirs(manifests_dir, exist_ok=True)

    # Set default env vars if not provided
    if env_vars is None:
        env_vars = {}

    # Create environment variables secret
    env_secret = {
        # Default environment variables that should be set
        "ALLOW_EMAIL_LOGIN": "true",
        "ALLOW_REGISTRATION": "true",
        "ALLOW_SOCIAL_LOGIN": "false",
        "ALLOW_SOCIAL_REGISTRATION": "false",
        "APP_TITLE": "Librechat",
        "CUSTOM_FOOTER": "Provided with ❤️",
        "DEBUG_CONSOLE": "true",
        "DEBUG_LOGGING": "true",
        "DEBUG_OPENAI": "true",
        "DEBUG_PLUGINS": "true",
        "ENDPOINTS": "openAI,azureOpenAI,bingAI,chatGPTBrowser,google,gptPlugins,anthropic,custom",
        "SEARCH": "false"
    }
    
    # Add user-provided environment variables
    if env_vars:
        env_secret.update(env_vars)
    
    # Add OpenAI API key if provided
    if openai_api_key:
        env_secret["OPENAI_API_KEY"] = openai_api_key
    
    # Add Meilisearch master key if meilisearch is enabled
    if meilisearch_enabled:
        # Generate a random master key if not provided
        if not meilisearch_master_key:
            import secrets
            meilisearch_master_key = secrets.token_hex(16)
        env_secret["MEILI_MASTER_KEY"] = meilisearch_master_key

    # Create the secret manifest
    env_secret_manifest = {
        "apiVersion": "v1",
        "kind": "Secret",
        "metadata": {
            "name": f"{slug}-librechat-env",
            "namespace": namespace
        },
        "type": "Opaque",
        "stringData": env_secret
    }

    # Write environment secret manifest
    with open(f"{manifests_dir}/env-secret.yaml", "w") as file:
        yaml.dump(env_secret_manifest, file, default_flow_style=False)

    # Generate Helm values
    helm_values = {
        "nameOverride": slug,
        "fullnameOverride": f"{slug}-librechat",
        "namespace": namespace,
        "image": {
            "repository": image_repository.split('/')[-1],
            "registry": '/'.join(image_repository.split('/')[:-1]),
            "tag": image_tag,
            "pullPolicy": "IfNotPresent"
        },
        "replicaCount": replicas,
        "service": {
            "type": "ClusterIP",
            "port": 3080
        },
        "ingress": {
            "enabled": ingress_enabled,
            "className": ingress_class_name,
            "annotations": {},
            "hosts": [
                {
                    "host": ingress_host,
                    "paths": [
                        {
                            "path": "/",
                            "pathType": "ImplementationSpecific"
                        }
                    ]
                }
            ]
        },
        "mongodb": {
            "enabled": mongodb_enabled
        },
        "meilisearch": {
            "enabled": meilisearch_enabled,
            "auth": {
                "existingMasterKeySecret": f"{slug}-librechat-env"
            }
        },
        "global": {
            "librechat": {
                "existingSecretName": f"{slug}-librechat-env"
            }
        }
    }

    # Add TLS configuration if provided
    if ingress_enabled and ingress_tls_secret:
        helm_values["ingress"]["tls"] = [
            {
                "secretName": ingress_tls_secret,
                "hosts": [ingress_host]
            }
        ]

    # Add custom YAML configuration if provided
    if custom_yaml_config:
        helm_values["librechat"] = helm_values.get("librechat", {})
        helm_values["librechat"]["configYamlContent"] = custom_yaml_config


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
                        "name": f"{slug}-librechat",
                        "chartPath": get_chart_path("./charts/librechat"),
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
                f"./manifests/env-secret.yaml"
            ]
        },
    }

    skaffold_yaml = yaml.dump(skaffold_config, default_flow_style=False)
    write(f"{output_dir}/skaffold-librechat.yaml", skaffold_yaml)

    # Generate fleet.yaml for dependencies
    fleet_config = {
        "dependsOn": [
            c.as_fleet_dependency for c in depends_on
        ] if depends_on else [],
        "helm": {
            "releaseName": f"{slug}-librechat",
        },
        "labels": {
            "name": f"{slug}-librechat"
        }
    }

    fleet_yaml = yaml.dump(fleet_config, default_flow_style=False)
    write(f"{output_dir}/fleet.yaml", fleet_yaml)

    # Return Component object
    return Component(
        slug=slug,
        namespace=namespace,
        dir_name=dir_name,
        fleet_name=f"{slug}-librechat",
    )
