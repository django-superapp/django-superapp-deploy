"""
Component types for the cert_manager_certificates component.
"""

from typing import List, Optional
from ..base.component_types import Component


class CertificatesComponent(Component):
    """
    Component representing a collection of cert-manager certificates.
    """

    def __init__(
        self,
        slug: str,
        namespace: str,
        dir_name: str,
        fleet_name: str,
        certificates_info: List[dict],
        depends_on: Optional[List[Component]] = None
    ):
        super().__init__(slug, namespace, dir_name, fleet_name, depends_on)
        self.certificates_info = certificates_info

    def get_certificate_secret_for_domain(self, domain: str) -> Optional[str]:
        """
        Get the certificate secret name for a specific domain.

        Args:
            domain: The domain to find certificate for

        Returns:
            The certificate secret name if found, None otherwise
        """
        for cert_info in self.certificates_info:
            dns_names = cert_info.get('dns_names', [])
            if domain in dns_names or domain == cert_info.get('domain_name'):
                return cert_info['certificate_secret_name']
        return None
