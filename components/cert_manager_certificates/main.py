"""
Certificate Manager Certificates Component

This module provides functionality to create multiple cert-manager certificates
with different configurations (DNS01/HTTP01 challenges, Cloudflare credentials).
"""
import os
from typing import List, Optional, TypedDict, Literal
import yaml

from ilio import write

from .component_types import CertificatesComponent
from ..base.component_types import Component
from ..base.constants import *


class CloudflareConfig(TypedDict, total=False):
    email: str
    api_token: str


class CertificateConfig(TypedDict, total=False):
    secret_name: str
    namespace: Optional[str]  # Optional: defaults to component namespace if not specified
    domain_name: str
    dns_names: List[str]
    challenge_type: Literal["dns01", "http01"]
    cloudflare: Optional[CloudflareConfig]
    ingress_class_name: Optional[str]  # Required for HTTP01 challenge


def create_cert_manager_certificates(
        slug: str,
        namespace: str,
        certificates: List[CertificateConfig],
        depends_on: Optional[List[Component]] = None
) -> CertificatesComponent:
    """
    Create multiple cert-manager certificates with different configurations.

    Args:
        slug: Unique identifier for the certificates component
        namespace: Kubernetes namespace to deploy the certificates
        certificates: List of certificate configurations
        depends_on: List of dependencies for Fleet

    Returns:
        CertificatesComponent object with metadata about the certificates
    """
    # Create directory structure
    dir_name = f"{slug}-certificates"
    output_dir = f'{GENERATED_SKAFFOLD_TMP_DIR}/{dir_name}'
    manifests_dir = f'{output_dir}/manifests'

    os.makedirs(output_dir, exist_ok=True)
    os.makedirs(manifests_dir, exist_ok=True)

    # Store certificate info for the component
    certificates_info = []
    manifest_files = []

    # Process each certificate configuration
    for cert_config in certificates:
        certificate_secret_name = cert_config["secret_name"]
        cert_namespace = cert_config.get("namespace", namespace)  # Use per-cert namespace or default
        domain_name = cert_config["domain_name"]
        dns_names = cert_config["dns_names"]
        challenge_type = cert_config["challenge_type"]
        cloudflare_config = cert_config.get("cloudflare")
        ingress_class_name = cert_config.get("ingress_class_name", "nginx")

        # Generate names from secret name
        cert_slug = certificate_secret_name.replace("-tls", "").replace("_", "-")
        issuer_name = f"{cert_slug}-issuer"

        # Store certificate info
        certificates_info.append({
            "secret_name": certificate_secret_name,
            "domain_name": domain_name,
            "dns_names": dns_names,
            "certificate_secret_name": certificate_secret_name,
            "issuer_name": issuer_name,
            "challenge_type": challenge_type
        })

        # Create Cloudflare API token secret if DNS01 challenge
        if challenge_type == "dns01" and cloudflare_config:
            api_token_secret = {
                "apiVersion": "v1",
                "kind": "Secret",
                "metadata": {
                    "name": f"{cert_slug}-cloudflare-api-token",
                    "namespace": namespace,
                    "labels": {
                        "app.kubernetes.io/name": f"{cert_slug}-cloudflare",
                        "app.kubernetes.io/instance": cert_slug,
                    }
                },
                "type": "Opaque",
                "stringData": {
                    "api-token": cloudflare_config["api_token"]
                }
            }

            secret_file = f"{manifests_dir}/{cert_slug}-cloudflare-secret.yaml"
            write(secret_file, yaml.dump(api_token_secret, default_flow_style=False))
            manifest_files.append(f"./manifests/{cert_slug}-cloudflare-secret.yaml")

        # Generate Let's Encrypt issuer
        issuer = {
            "apiVersion": "cert-manager.io/v1",
            "kind": "Issuer",
            "metadata": {
                "name": issuer_name,
                "namespace": namespace,
                "labels": {
                    "app.kubernetes.io/name": f"{cert_slug}-issuer",
                    "app.kubernetes.io/instance": cert_slug,
                }
            },
            "spec": {
                "acme": {
                    "server": "https://acme-v02.api.letsencrypt.org/directory",
                    "email": cloudflare_config["email"] if cloudflare_config else "admin@example.com",
                    "privateKeySecretRef": {
                        "name": f"{cert_slug}-letsencrypt-private-key"
                    },
                    "solvers": []
                }
            }
        }

        # Configure solver based on challenge type
        if challenge_type == "dns01" and cloudflare_config:
            issuer["spec"]["acme"]["solvers"].append({
                "dns01": {
                    "cloudflare": {
                        "email": cloudflare_config["email"],
                        "apiTokenSecretRef": {
                            "name": f"{cert_slug}-cloudflare-api-token",
                            "key": "api-token"
                        }
                    }
                }
            })
        elif challenge_type == "http01":
            issuer["spec"]["acme"]["solvers"].append({
                "http01": {
                    "ingress": {
                        "ingressClassName": ingress_class_name,
                    }
                }
            })

        issuer_file = f"{manifests_dir}/{cert_slug}-issuer.yaml"
        write(issuer_file, yaml.dump(issuer, default_flow_style=False))
        manifest_files.append(f"./manifests/{cert_slug}-issuer.yaml")

        # Generate certificate
        certificate = {
            "apiVersion": "cert-manager.io/v1",
            "kind": "Certificate",
            "metadata": {
                "name": f"{cert_slug}-certificate",
                "namespace": namespace,
                "labels": {
                    "app.kubernetes.io/name": f"{cert_slug}-certificate",
                    "app.kubernetes.io/instance": cert_slug,
                }
            },
            "spec": {
                "commonName": domain_name,
                "dnsNames": dns_names,
                "secretName": certificate_secret_name,
                "issuerRef": {
                    "name": issuer_name,
                    "kind": "Issuer"
                }
            }
        }

        cert_file = f"{manifests_dir}/{cert_slug}-certificate.yaml"
        write(cert_file, yaml.dump(certificate, default_flow_style=False))
        manifest_files.append(f"./manifests/{cert_slug}-certificate.yaml")

    # Generate Skaffold configuration
    skaffold_config = {
        "apiVersion": "skaffold/v3",
        "kind": "Config",
        "manifests": {
            "rawYaml": manifest_files
        },
        "deploy": {
            "kubectl": {
                "defaultNamespace": namespace,
            },
        },
    }

    # Generate Fleet configuration
    fleet_config = {
        "dependsOn": [
            c.as_fleet_dependency for c in depends_on
        ] if depends_on else [],
        "helm": {
            "releaseName": f"{slug}-certificates",
        },
        "labels": {
            "name": f"{slug}-certificates"
        },
        "diff": {
            "comparePatches": [
                {
                    "apiVersion": "cert-manager.io/v1",
                    "kind": "Certificate",
                    "jsonPointers": [
                        "/metadata/resourceVersion",
                        "/metadata/uid",
                        "/status"
                    ]
                },
                {
                    "apiVersion": "cert-manager.io/v1",
                    "kind": "Issuer",
                    "jsonPointers": [
                        "/metadata/resourceVersion",
                        "/metadata/uid",
                        "/status"
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

    # Write all configuration files
    write(f"{output_dir}/skaffold-main-certificates.yaml",
          yaml.dump(skaffold_config, default_flow_style=False))

    write(f"{output_dir}/fleet.yaml",
          yaml.dump(fleet_config, default_flow_style=False))

    return CertificatesComponent(
        slug=slug,
        namespace=namespace,
        dir_name=dir_name,
        fleet_name=f"{slug}-certificates",
        certificates_info=certificates_info,
        depends_on=depends_on,
    )