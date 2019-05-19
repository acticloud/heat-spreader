from marshmallow import fields, post_load, Schema

from .backend import BackendConfigSchema
from .server import ServerConfig, ServerConfigSchema


class ConfigSchema(Schema):
    backend = fields.Nested(BackendConfigSchema, required=True)
    clouds = fields.List(fields.Str())
    server = fields.Nested(ServerConfigSchema)

    @post_load
    def make_config(self, data, **kwargs):
        return Config(
            backend_config=data["backend"],
            server_config=data.get("server", ServerConfig()),
            clouds=data.get("clouds", []),
        )


class Config:
    def __init__(self, backend_config=None, server_config=None, clouds=[]):
        self.backend = backend_config
        self.clouds = clouds
        self.server = server_config
