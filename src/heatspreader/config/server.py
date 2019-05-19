from marshmallow import fields, post_load, Schema


class ServerConfigSchema(Schema):
    address = fields.Str(required=True)
    port = fields.Int(required=True)
    shutdown_timeout = fields.Int()

    @post_load
    def make_server_config(self, data, **kwargs):
        return ServerConfig(**data)


class ServerConfig:
    def __init__(self, address="127.0.0.1", port=8080, shutdown_timeout=30):
        self.address = address
        self.port = port
        self.shutdown_timeout = shutdown_timeout
