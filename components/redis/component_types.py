from dataclasses import dataclass

from components.base.component_types import Component


@dataclass
class RedisComponent(Component):
    redis_uri: str = ""
