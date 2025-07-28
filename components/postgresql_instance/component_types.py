from dataclasses import dataclass

from components.base.component_types import Component


@dataclass
class PostgresInstanceComponent(Component):
    superuser_postgres_uri: str = ""
    normal_user_postgres_uri: str = ""
