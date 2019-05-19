import os

from marshmallow import fields, post_load, Schema
from marshmallow_oneofschema import OneOfSchema

from ..store.backend import StoreBackend


class RemoteBackendConfigSchema(Schema):
    host = fields.Str(required=True)
    port = fields.Int(required=True)
    timeout = fields.Int(required=False)

    @post_load
    def make_remote_backend_config(self, data, **kwargs):
        return RemoteBackendConfig(**data)


class RemoteBackendConfig:
    type = StoreBackend.REMOTE

    def __init__(self, host="localhost", port=8080, timeout=10):
        self.host = host
        self.port = os.environ.get("HEAT_SPREADER_BACKEND_REMOTE_PORT", port)
        self.timeout = timeout


class SqliteBackendConfigSchema(Schema):
    database = fields.Str(required=True)

    @post_load
    def make_sqlite_backend_config(self, data, **kwargs):
        return SqliteBackendConfig(**data)


class SqliteBackendConfig:
    type = StoreBackend.SQLITE

    def __init__(self, database):
        self.database = database


class BackendConfigSchema(OneOfSchema):
    type_schemas = {
        RemoteBackendConfig.type.value: RemoteBackendConfigSchema,
        SqliteBackendConfig.type.value: SqliteBackendConfigSchema,
    }

    def get_obj_type(self, obj):
        if isinstance(obj, RemoteBackendConfig):
            return StoreBackend.REMOTE.value
        elif isinstance(obj, SqliteBackendConfig):
            return StoreBackend.SQLITE.value
        else:
            raise RuntimeError(f"Unknown obj type: {obj.__class__.__name__}")
