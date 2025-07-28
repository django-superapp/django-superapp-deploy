from dataclasses import dataclass

from components.base.component_types import Component


@dataclass
class IssuerComponent(Component):
    issuer_secret_name: str = ""
    dns_issuer_secret_name: str = ""
    http_issuer_secret_name: str = ""

