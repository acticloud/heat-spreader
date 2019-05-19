import pytest

from heatspreader.service.server import Server
from heatspreader.config import (
    RemoteBackendConfig,
    ServerConfig,
    SqliteBackendConfig,
)
from heatspreader.store import MulticloudStackStore
from heatspreader.store.backend.exceptions import NotFoundException
from heatspreader.store.backend.remote import (
    StoreBackend as RemoteStoreBackend,
)
from heatspreader.store.backend.sqlite import (
    StoreBackend as SqliteStoreBackend,
)


class BackendContract:
    @pytest.yield_fixture()
    @pytest.mark.asyncio
    async def store_backend(self):
        raise NotImplementedError()

    @pytest.mark.asyncio
    async def test_multicloud_stack_set_get(self, store_backend):
        expected = {
            "stack_name": "stack_name",
            "count": 5,
            "count_parameter": "param",
            "weights": {"cloud_1": 0.5, "cloud_2": 0.3},
        }

        await store_backend.multicloud_stack_set(expected)

        actual = await store_backend.multicloud_stack_get(
            expected["stack_name"]
        )

        assert actual == expected

    @pytest.mark.asyncio
    async def test_multicloud_stack_set_set_get(self, store_backend):
        expected = {
            "stack_name": "stack_name",
            "count": 5,
            "count_parameter": "param",
            "weights": {"cloud_1": 0.5, "cloud_2": 0.3},
        }

        await store_backend.multicloud_stack_set(expected)

        expected["stack_name"] = "stack_name_2"
        expected["count"] = 6
        expected["count_parameter"] = "param_2"
        expected["weights"]["cloud_3"] = 0.1

        await store_backend.multicloud_stack_set(expected)

        actual = await store_backend.multicloud_stack_get(
            expected["stack_name"]
        )

        assert actual == expected

    @pytest.mark.asyncio
    async def test_multicloud_stack_set_list(self, store_backend):
        expected = {
            "stacks": [
                {
                    "stack_name": "stack_name_1",
                    "count": 1,
                    "count_parameter": "param_1",
                    "weights": {"cloud_1": 0.0, "cloud_2": 0.1},
                },
                {
                    "stack_name": "stack_name_2",
                    "count": 2,
                    "count_parameter": "param_2",
                    "weights": {"cloud_1": 0.2, "cloud_2": 0.3},
                },
                {
                    "stack_name": "stack_name_3",
                    "count": 3,
                    "count_parameter": "param_3",
                    "weights": {"cloud_1": 0.4, "cloud_2": 0.5},
                },
            ]
        }

        for ms in expected["stacks"]:
            await store_backend.multicloud_stack_set(ms)

        actual = await store_backend.multicloud_stack_list()

        assert actual == expected

    @pytest.mark.asyncio
    async def test_multicloud_stack_set_delete_get_not_found(
        self, store_backend
    ):
        expected = {
            "stack_name": "stack_name",
            "count": 5,
            "count_parameter": "param",
            "weights": {"cloud_1": 0.5, "cloud_2": 0.3},
        }

        await store_backend.multicloud_stack_set(expected)

        await store_backend.multicloud_stack_delete(expected["stack_name"])

        with pytest.raises(NotFoundException):
            await store_backend.multicloud_stack_get(expected["stack_name"])

    @pytest.mark.asyncio
    async def test_multicloud_stack_delete_not_found(self, store_backend):
        with pytest.raises(NotFoundException):
            await store_backend.multicloud_stack_delete("non-existing-stack")


class TestSqliteBackend(BackendContract):
    @pytest.yield_fixture()
    @pytest.mark.asyncio
    async def store_backend(self):
        store_backend = SqliteStoreBackend(
            SqliteBackendConfig(database=":memory:")
        )
        yield store_backend
        await store_backend.close()


class TestRemoteBackend(BackendContract):
    @pytest.yield_fixture()
    @pytest.mark.asyncio
    async def store_backend(self):
        server = Server(
            ServerConfig(address="0.0.0.0", port=0),
            MulticloudStackStore(SqliteBackendConfig(database=":memory:")),
        )

        await server.start()

        store_backend = RemoteStoreBackend(
            RemoteBackendConfig(host="localhost", port=server.port, timeout=1)
        )
        yield store_backend
        await store_backend.close()

        await server.stop()
