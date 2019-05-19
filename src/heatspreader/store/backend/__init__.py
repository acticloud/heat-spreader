from enum import Enum
from importlib import import_module

from .exceptions import BackendException, NotFoundException


class StoreBackend(Enum):
    MEMORY = "memory"
    REMOTE = "remote"
    SQLITE = "sqlite"


_backend_module = {
    StoreBackend.MEMORY: "heatspreader.store.backend.memory",
    StoreBackend.REMOTE: "heatspreader.store.backend.remote",
    StoreBackend.SQLITE: "heatspreader.store.backend.sqlite",
}


def load_store_backend(config):
    store_backend_module = import_module(_backend_module[config.type])
    return store_backend_module.StoreBackend(config)


__all__ = [
    "BackendException",
    "load_store_backend",
    "NotFoundException",
    "StoreBackend",
]
