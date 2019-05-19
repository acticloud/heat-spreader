import asyncio
from http import HTTPStatus

import aiohttp
import structlog

from ...exceptions import ValidationError

from .exceptions import BackendException, NotFoundException

from .abstract_store_backend import AbstractStoreBackend

log = structlog.getLogger(__name__)


class StoreBackend(AbstractStoreBackend):
    def __init__(self, config):
        super().__init__(config)

        self._config = config

        self._log = log.bind(
            host=self._config.host,
            port=self._config.port,
            timeout=self._config.timeout,
        )

        self._session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=self._config.timeout)
        )

        self._log.debug("backend_remote_session_created")

    async def close(self):
        await self._session.close()

    def _url(self, path):
        return f"http://{self._config.host}:{self._config.port}{path}"

    async def _request(self, method, path, json=None):
        if self._session.closed:
            raise RuntimeError("session closed")

        url = self._url(path)

        self._log.debug("backend_remote_request", method=method, path=path)

        try:
            return await self._session.request(method, url, json=json)
        except aiohttp.ClientConnectorError as exc:
            err_msg = (
                "could not connect to server: "
                f"{self._config.host}:{self._config.port}"
            )
            raise BackendException(err_msg) from exc
        except aiohttp.ServerTimeoutError as exc:
            err_msg = "timeout while sending request server"
            raise BackendException(err_msg) from exc
        except asyncio.TimeoutError as exc:
            err_msg = "unexpected timeout exception"
            raise BackendException(err_msg) from exc
        except aiohttp.ClientError as exc:
            err_msg = f"unexpected backend exception: {exc}"
            raise BackendException(err_msg) from exc

    async def multicloud_stack_get(self, stack_name):
        response = await self._request(
            method="GET", path=f"/multicloudstack/{stack_name}"
        )

        if response.status == HTTPStatus.NOT_FOUND:
            raise NotFoundException(stack_name)
        elif response.status == HTTPStatus.OK:
            return await response.json()
        else:
            # TODO
            raise Exception(f"Unexpected response: {response.status}")

    async def multicloud_stack_set(self, multicloud_stack_dict):
        response = await self._request(
            method="PUT",
            path=f"/multicloudstack/{multicloud_stack_dict['stack_name']}",
            json=multicloud_stack_dict,
        )

        if response.status == HTTPStatus.UNPROCESSABLE_ENTITY:
            raise ValidationError(await response.json())
        elif response.status == HTTPStatus.OK:
            return
        else:
            # TODO
            raise Exception(f"Unexpected response: {response.status}")

    async def multicloud_stack_list(self):
        response = await self._request(method="GET", path="/multicloudstack")

        if response.status == HTTPStatus.OK:
            return await response.json()
        else:
            # TODO
            raise Exception(f"Unexpected response: {response.status}")

    async def multicloud_stack_delete(self, stack_name):
        response = await self._request(
            method="DELETE", path=f"/multicloudstack/{stack_name}"
        )

        if response.status == HTTPStatus.NOT_FOUND:
            raise NotFoundException(stack_name)
        elif response.status == HTTPStatus.OK:
            return
        else:
            # TODO
            raise Exception(f"Unexpected response: {response.status}")
