"""
Certificate Manager Certificate Component

This module provides functionality to create a cert-manager certificate
resource for TLS certificates.
"""
from typing import List, Optional

from ilio import write
from .component_types import CertificateComponent

from ..base.component_types import Component
from ..base.constants import *


def create_cert_manager_certificate(
        slug: str,
        namespace: str,
        domain_name: str,
        issuer_secret_name: str,
        certificate_dns_names: List[str],
        depends_on: Optional[List[Component]] = None
) -> CertificateComponent:
    """
    Create a cert-manager certificate resource.
    
    Args:
        slug: Unique identifier for the certificate
        namespace: Kubernetes namespace to deploy the certificate
        domain_name: Primary domain name for the certificate
        certificate_dns_names: List of DNS names to include in the certificate
        depends_on: List of dependencies for Fleet
        
    Returns:
        Directory name where the configuration is generated
    """
    # Create directory structure
    dir_name = f"{slug}-certificate"
    output_dir = f'{GENERATED_SKAFFOLD_TMP_DIR}/{dir_name}'
    manifests_dir = f'{output_dir}/manifests'
    
    os.makedirs(output_dir, exist_ok=True)
    os.makedirs(manifests_dir, exist_ok=True)
    
    # Create certificate manifest
    certificate = {
        "apiVersion": "cert-manager.io/v1",
        "kind": "Certificate",
        "metadata": {
            "name": f"{slug}-certificate",
            "namespace": namespace,
            "labels": {
                "app.kubernetes.io/name": f"{slug}-certificate",
                "app.kubernetes.io/instance": slug,
            }
        },
        "spec": {
            "commonName": domain_name,
            "dnsNames": certificate_dns_names,
            "secretName": f"{slug}-certificate",
            "issuerRef": {
                "name": issuer_secret_name,
                "kind": "Issuer"
            }
        }
    }
    
    # Generate certificate manifest file path
    certificate_manifest_path = f"{manifests_dir}/certificate.yaml"
    
    # Generate Skaffold configuration
    skaffold_config = {
        "apiVersion": "skaffold/v3",
        "kind": "Config",
        "manifests": {
            "rawYaml": [
                "./manifests/certificate.yaml"
            ]
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
                        "/metadata/uid"
                    ]
                }
            ]
        },
    }
    
    # Write all configuration files
    write(certificate_manifest_path, 
          yaml.dump(certificate, default_flow_style=False))
    
    write(f"{output_dir}/skaffold-main-certificates.yaml", 
          yaml.dump(skaffold_config, default_flow_style=False))
    
    write(f"{output_dir}/fleet.yaml", 
          yaml.dump(fleet_config, default_flow_style=False))

    return CertificateComponent(
        slug=slug,
        namespace=namespace,
        dir_name=dir_name,
        fleet_name=f"{slug}-certificates",
        certificate_secret_name=f"{slug}-certificate",
        depends_on=depends_on
    )

