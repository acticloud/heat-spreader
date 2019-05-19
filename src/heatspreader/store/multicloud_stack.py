import structlog

from ..exceptions import ValidationError
from ..state import MulticloudStack

from .backend import load_store_backend, NotFoundException
from .exceptions import MulticloudStackNotFound

log = structlog.getLogger(__name__)


class MulticloudStackStore:
    def __init__(self, config):
        # TODO: except import error
        self.backend = load_store_backend(config)

        self._log = log.bind(backend=self.backend)

    async def close(self):
        await self.backend.close()

    async def get(self, stack_name):
        _log = self._log.bind(stack_name=stack_name)

        _log.debug("multicloud_stack_store_get")

        try:
            data = await self.backend.multicloud_stack_get(stack_name)
        except NotFoundException as exc:
            raise MulticloudStackNotFound(exc.name) from exc

        _log.debug("multicloud_stack_store_get_data", data=data)

        return MulticloudStack.load(data)

    async def set(self, multicloud_stack):
        _log = self._log.bind(stack_name=multicloud_stack.stack_name)

        _log.debug("multicloud_stack_store_set")

        validation_errors = multicloud_stack.validate()
        if validation_errors:
            raise ValidationError(validation_errors)

        data = MulticloudStack.dump(multicloud_stack)

        _log.debug("multicloud_stack_store_set_data", data=data)

        await self.backend.multicloud_stack_set(data)

    async def delete(self, stack_name):
        self._log.debug("multicloud_stack_store_delete", stack_name=stack_name)

        try:
            await self.backend.multicloud_stack_delete(stack_name)
        except NotFoundException as exc:
            raise MulticloudStackNotFound(exc.name) from exc

    async def list(self):
        self._log.debug("multicloud_stack_store_list")

        data = await self.backend.multicloud_stack_list()

        self._log.debug("multicloud_stack_store_list_data", data=data)

        return MulticloudStack.load_list(data)
