import yaml

from .config import ConfigSchema, Config
from .backend import RemoteBackendConfig, SqliteBackendConfig
from .exceptions import ConfigParseException
from .server import ServerConfig


def parse_config_file(path):
    with open(path, "r") as config_file:
        try:
            config_data = yaml.safe_load(config_file)
        except yaml.YAMLError as exc:
            raise ConfigParseException(str(exc))

    return ConfigSchema().load(config_data)


__all__ = [
    "Config",
    "ConfigParseException",
    "parse_config_file",
    "RemoteBackendConfig",
    "ServerConfig",
    "SqliteBackendConfig",
]
