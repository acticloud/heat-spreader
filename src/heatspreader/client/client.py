from ..store import MulticloudStackStore
from ..state import MulticloudStack

from .exceptions import WeightNotFound


class Client:
    def __init__(self, config):
        self.config = config

        self._store = MulticloudStackStore(config)

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()

    async def close(self):
        await self._store.close()

    async def create(self, stack_name, count, count_parameter, weights={}):
        multicloud_stack = MulticloudStack(
            stack_name=stack_name,
            count=count,
            count_parameter=count_parameter,
            weights=weights,
        )

        await self._store.set(multicloud_stack)

        return multicloud_stack

    async def get(self, stack_name):
        return await self._store.get(stack_name)

    async def update(self, stack_name, count=None, count_parameter=None):
        multicloud_stack = await self._store.get(stack_name)

        if count is not None:
            multicloud_stack.count = count

        if count_parameter is not None:
            multicloud_stack.count_parameter = count_parameter

        await self._store.set(multicloud_stack)

        return multicloud_stack

    async def delete(self, stack_name):
        await self._store.delete(stack_name)

    async def list(self):
        return await self._store.list()

    async def weight_set(self, stack_name, cloud_name, weight):
        multicloud_stack = await self._store.get(stack_name)

        multicloud_stack.weights[cloud_name] = float(weight)

        await self._store.set(multicloud_stack)

        return multicloud_stack

    async def weight_unset(self, stack_name, cloud_name):
        multicloud_stack = await self._store.get(stack_name)

        try:
            del multicloud_stack.weights[cloud_name]
        except KeyError:
            raise WeightNotFound(stack_name, cloud_name)

        await self._store.set(multicloud_stack)

        return multicloud_stack
