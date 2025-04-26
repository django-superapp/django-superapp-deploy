# Component Development Conventions

This document outlines the conventions and best practices for developing components in this repository.

## Directory Structure

Each component follows this standard structure:

```
components/<component-name>/
├── charts/                  # Helm charts used by the component
│   └── <chart-name>/        # Chart directory
│       ├── templates/       # Kubernetes manifest templates
│       └── values.yaml      # Default values for the chart
├── constants.py             # Component-specific constants (optional)
└── main.py                  # Main component implementation
```

## Component Implementation

### Main Function

Each component's `main.py` should define a primary function that:

1. Takes parameters for configuration (slug, namespace, depends_on, etc.)
2. Creates necessary directories
3. Generates configuration files
4. Returns a Component object with metadata about the deployment

### Best Practices

1. **Function Naming**: Use `create_` prefix for main component functions
2. **Documentation**: Include docstrings for the main function and any helper functions
3. **Type Hints**: Use proper type hints for all parameters and return values
4. **Error Handling**: Use `exist_ok=True` for directory creation instead of try/except
5. **Configuration Objects**: Create variables for configuration objects to improve readability
6. **YAML Output**: Use `default_flow_style=False` for more readable YAML output
7. **Variable Names**: Use descriptive variable names, avoid abbreviations
8. **Multiline Strings**: Use triple quotes for multiline strings
9. **Minimal Values**: For Helm charts, include only the necessary values in values.yaml

### Common Configuration Files

Each component typically generates these files:

1. **Values File**: Contains configuration for Helm charts (e.g., `component-values.yaml`)
2. **Skaffold Config**: Defines how to build and deploy the component (e.g., `skaffold-component.yaml`)
3. **Fleet Config**: Defines dependencies and labels for Fleet (e.g., `fleet.yaml`)

## Component Types

The repository supports different types of components:

1. **Standard Components**: Basic components that return a `Component` object
2. **Certificate Components**: Components that manage certificates, returning a `CertificateComponent` object
3. **Issuer Components**: Components that manage certificate issuers, returning an `IssuerComponent` object

## Example Component Implementation

```python
from typing import List, Optional
import os
import yaml
from ilio import write

from components.base.component_types import Component
from components.base.constants import GENERATED_SKAFFOLD_TMP_DIR
from components.base.utils import get_chart_path

# Import any other necessary modules

def create_example_component(
    slug: str,
    namespace: str = 'example-namespace',
    config_value: str = 'default-value',
    depends_on: Optional[List[Component]] = None
) -> Component:
    """
    Deploy the example component using Helm.
    
    Args:
        slug: Unique identifier for the deployment
        namespace: Kubernetes namespace to deploy the component
        config_value: Configuration value for the component
        depends_on: List of dependencies for Fleet
        
    Returns:
        Component object with metadata about the deployment
    """
    # Create directory structure
    dir_name = f"{slug}-example"
    output_dir = f'{GENERATED_SKAFFOLD_TMP_DIR}/{dir_name}'
    os.makedirs(output_dir, exist_ok=True)
    manifests_dir = f"{output_dir}/manifests"
    os.makedirs(manifests_dir, exist_ok=True)
    
    # Generate Helm values
    helm_values = {
        "nameOverride": slug,
        "namespace": namespace,
        "configuration": {
            "value": config_value
        }
    }
    
    # Write values file
    with open(f"{output_dir}/values.yaml", "w") as file:
        yaml.dump(helm_values, file, default_flow_style=False)


    basic_auth_manifest = {
        "apiVersion": "v1",
        "kind": "Secret",
        "metadata": {
            "name": "basic-auth",
            "namespace": namespace
        },
        "type": "Opaque",
        "data": {
            "auth": "<<auth_base64>>"
        }
    }

    # Write secret manifest
    with open(f"{manifests_dir}/additional-example-manifest.yaml", "w") as file:
        yaml.dump(basic_auth_manifest, file, default_flow_style=False)
        
    # Generate skaffold.yaml
    skaffold_config = {
        "apiVersion": "skaffold/v3",
        "kind": "Config",
        "deploy": {
            "kubectl": {
                "default_namespace": namespace,
            }
        },
        "manifests": {
            "helm": {
                "releases": [
                    {
                        "name": f"{slug}-example",
                        "chartPath": get_chart_path("./charts/example"),
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
                f"./manifests/additional-example-manifest.yaml", # optional
            ],
        },
    }

    skaffold_yaml = yaml.dump(skaffold_config, default_flow_style=False)
    write(f"{output_dir}/skaffold-example.yaml", skaffold_yaml)

    # Generate fleet.yaml for dependencies
    fleet_config = {
        "dependsOn": [
            c.as_fleet_dependency for c in depends_on
        ] if depends_on else [],
       # "helm": {
       #      "releaseName": f"{slug}-example",
       #  },
        "labels": {
            "name": f"{slug}-example"
        }
    }

    fleet_yaml = yaml.dump(fleet_config, default_flow_style=False)
    write(f"{output_dir}/fleet.yaml", fleet_yaml)
    
    # Return Component object
    return Component(
        slug=slug,
        namespace=namespace,
        dir_name=dir_name,
        fleet_name=f"{slug}-example",
    )
```

## Testing Components

When developing a new component:

1. Test the component in isolation first
2. Verify that the generated YAML files are correct
3. Test the component with dependencies
4. Ensure the component works with the skaffold generation system

## See Also

For reference implementations, see existing components like:
- `cert_manager_operator`
- `ingress_nginx`
- `longhorn`
