from dataclasses import dataclass

from components.base.component_types import Component


@dataclass
class IssuerComponent(Component):
    issuer_secret_name: str
