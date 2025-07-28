from dataclasses import dataclass

from components.base.component_types import Component
from components.registry.utils import escape_registry_url


@dataclass
class RegistryComponent(Component):
    registry_url: str = ""
    secret_name: str = ""
    kaniko_secret_name: str = ""
    kaniko_namespace: str = None

    def skaffold_build_params(self, image_tag: str):
        return {
            "platforms": [
                # "linux/arm64",
                "linux/amd64"
            ],
            "tagPolicy": {
                "envTemplate": {
                    "template": image_tag
                }
            },
            # "local": {
            #     "push": True,
            #     "useDockerCLI": True,
            #     "useBuildkit": True,
            #     "concurrency": 5,
            # },
            "cluster": {
                # "pullSecretName": self.kaniko_secret_name,
                # "randomPullSecret": True,
                "concurrency": 5,
                "namespace": self.kaniko_namespace,
                "dockerConfig": {
                    # "path": "~/.docker/config.json"
                    "secretName": self.kaniko_secret_name,
                },
                "randomDockerConfigSecret": True,
                "resources": {
                    "requests": {
                        "cpu": "1",
                        "memory": "2Gi"
                    },
                    "limits": {
                        "cpu": "4",
                        "memory": "8Gi"
                    }
                },
                "kanikoImage": "gcr.io/kaniko-project/executor:latest"
            }
        }

    @property
    def registry_url_escaped(self):
        return escape_registry_url(self.registry_url)
