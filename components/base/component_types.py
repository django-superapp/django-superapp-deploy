from dataclasses import dataclass
from typing import Dict


@dataclass
class Component:
    """
    Type object returned by component main functions.
    
    Attributes:
        slug: Unique identifier for the deployment
        dir_name: Directory name where the configuration is generated
        fleet_name: Name used in Fleet dependencies
    """
    slug: str
    namespace: str
    dir_name: str
    fleet_name: str
    
    @property
    def as_fleet_dependency(self) -> Dict[str, str]:
        """
        Returns this component as a dependency object for other components.
        
        Returns:
            Dictionary with the name field set to the fleet_name
        """
        return {"name": self.fleet_name}

    @property
    def as_skaffold_dependency(self) -> Dict[str, str]:
        """
        Returns this component as a dependency object for skaffold.
        
        Returns:
            Dictionary with the path field set to the component's skaffold path
        """
        return {"path": f"../{self.dir_name}/skaffold.yaml"}

@dataclass
class CertificateComponent(Component):
    certificate_secret_name: str

@dataclass
class IssuerComponent(Component):
    issuer_secret_name: str
