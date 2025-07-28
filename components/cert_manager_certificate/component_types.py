from dataclasses import dataclass

from components.base.component_types import Component


@dataclass
class CertificateComponent(Component):
    certificate_secret_name: str = ""

