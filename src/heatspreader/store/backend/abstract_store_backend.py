from abc import ABC, abstractmethod


class AbstractStoreBackend(ABC):
    def __init__(self, config):
        self.name = config.type.value

    def __repr__(self):
        return self.name

    @abstractmethod
    async def close(self):
        raise NotImplementedError()

    @abstractmethod
    async def multicloud_stack_get(self, stack_name):
        raise NotImplementedError()

    @abstractmethod
    async def multicloud_stack_set(self, multicloud_stack_dict):
        raise NotImplementedError()

    @abstractmethod
    async def multicloud_stack_list(self):
        raise NotImplementedError()

    @abstractmethod
    async def multicloud_stack_delete(self, stack_name):
        raise NotImplementedError()
