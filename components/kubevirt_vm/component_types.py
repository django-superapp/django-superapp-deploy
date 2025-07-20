from dataclasses import dataclass
from components.base.component_types import Component

@dataclass
class VMComponent(Component):
    """
    Type object returned by kubevirt_vm component functions.
    
    Attributes:
        vm_name: Name of the virtual machine
    """
    vm_name: str
