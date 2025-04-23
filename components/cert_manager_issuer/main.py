"""
Certificate Manager Issuer Component

This module provides functionality to create a cert-manager issuer
for DNS01 validation using Cloudflare.
"""
from typing import Any, List, Optional
import os

import yaml
from ilio import write

from ..base.component_types import Component, IssuerComponent
from ..base.constants import *


def create_cert_manager_issuer(
        slug: str,
        namespace: str,
        cloudflare_email: str,
        cloudflare_api_token: str,
        depends_on: Optional[List[Component]] = None
) -> IssuerComponent:
    """
    Create a cert-manager issuer configuration for Cloudflare DNS01 validation.
    
    Args:
        slug: Unique identifier for the issuer
        namespace: Kubernetes namespace to deploy the issuer
        cloudflare_email: Email address registered with Cloudflare
        cloudflare_api_token: Cloudflare API token with DNS edit permissions
        depends_on: List of dependencies for Fleet
        
    Returns:
        Directory name where the configuration is generated
    """
    # Create directory structure
    dir_name = f"{slug}-certificate-issuer"
    manifests_dir = f'{GENERATED_SKAFFOLD_TMP_DIR}/{dir_name}/manifests'
    
    os.makedirs(f'{GENERATED_SKAFFOLD_TMP_DIR}/{dir_name}', exist_ok=True)
    os.makedirs(manifests_dir, exist_ok=True)
    
    # Generate Cloudflare API token secret
    api_token_secret = {
        "apiVersion": "v1",
        "kind": "Secret",
        "metadata": {
            "name": f"{slug}-certificate-cloudflare-api-token",
            "namespace": namespace,
            "labels": {
                "app.kubernetes.io/name": f"{slug}-certificate-cloudflare",
                "app.kubernetes.io/instance": slug,
                "app.kubernetes.io/managed-by": "skaffold"
            }
        },
        "type": "Opaque",
        "stringData": {
            "api-token": cloudflare_api_token
        }
    }
    
    # Generate Let's Encrypt issuer
    issuer_secret_name =  f"{slug}-issuer"
    letsencrypt_issuer = {
        "apiVersion": "cert-manager.io/v1",
        "kind": "Issuer",
        "metadata": {
            "name": issuer_secret_name,
            "namespace": namespace,
            "labels": {
                "app.kubernetes.io/name": f"{slug}-letsencrypt",
                "app.kubernetes.io/instance": slug,
                "app.kubernetes.io/managed-by": "skaffold"
            }
        },
        "spec": {
            "acme": {
                "server": "https://acme-v02.api.letsencrypt.org/directory",
                "email": cloudflare_email,
                "privateKeySecretRef": {
                    "name": f"{slug}-letsencrypt-production"
                },
                "solvers": [
                    {
                        "dns01": {
                            "cloudflare": {
                                "email": cloudflare_email,
                                "apiTokenSecretRef": {
                                    "name": f"{slug}-certificate-cloudflare-api-token",
                                    "key": "api-token"
                                }
                            }
                        }
                    }
                ]
            }
        }
    }
    
    # Generate Skaffold configuration
    skaffold_config = {
        "apiVersion": "skaffold/v3",
        "kind": "Config",
        "requires": [
            c.as_skaffold_dependency for c in depends_on
        ] if depends_on else [],
        "manifests": {
            "rawYaml": [
                "./manifests/cert-manager-issuer-secret.yaml",
                "./manifests/cert-manager-letsencrypt-issuer.yaml",
            ],
        },
        "deploy": {
            "kubectl": {
                "defaultNamespace": namespace,
            },
        },
    }
    
    # Generate Fleet configuration
    fleet_config = {
        "namespace": namespace,
        "dependsOn": [
            c.as_fleet_dependency for c in depends_on
        ] if depends_on else [],
        "labels": {
            "name": f"{slug}-certificates"
        },
        "diff": {
            "comparePatches": [
                {
                    "apiVersion": "cert-manager.io/v1",
                    "kind": "Issuer",
                    "jsonPointers": [
                        "/metadata/resourceVersion",
                        "/metadata/uid"
                    ]
                },
                {
                    "apiVersion": "v1",
                    "kind": "Secret",
                    "jsonPointers": [
                        "/metadata/resourceVersion",
                        "/metadata/uid"
                    ]
                }
            ]
        },
    }
    
    # Write all files
    write(f"{manifests_dir}/cert-manager-issuer-secret.yaml", 
          yaml.dump(api_token_secret, default_flow_style=False))
    
    write(f"{manifests_dir}/cert-manager-letsencrypt-issuer.yaml", 
          yaml.dump(letsencrypt_issuer, default_flow_style=False))
    
    write(f"{GENERATED_SKAFFOLD_TMP_DIR}/{dir_name}/skaffold-main-certificates.yaml", 
          yaml.dump(skaffold_config, default_flow_style=False))
    
    write(f"{GENERATED_SKAFFOLD_TMP_DIR}/{dir_name}/fleet.yaml", 
          yaml.dump(fleet_config, default_flow_style=False))

    return IssuerComponent(
        slug=slug,
        namespace=namespace,
        dir_name=dir_name,
        fleet_name=f"{slug}-certificates",
        issuer_secret_name=issuer_secret_name,
    )

