# TODO: investigate graceful stop / force stop long running request handler
from http import HTTPStatus
import uuid

from aiohttp_apispec import (
    docs,
    request_schema,
    response_schema,
    setup_aiohttp_apispec,
    validation_middleware,
)
from aiohttp.abc import AbstractAccessLogger
from aiohttp import web
import structlog

from ..store import MulticloudStackNotFound
from ..state import MulticloudStack

log = structlog.getLogger(__name__)

routes = web.RouteTableDef()


@web.middleware
async def request_id_middleware(request, handler):
    request["id"] = str(uuid.uuid4())
    return await handler(request)


def incoming_request_logger_middleware_factory(server):
    @web.middleware
    async def incoming_request_logger_middleware(request, handler):
        server._log.debug(
            "server_request_incoming",
            request_id=request["id"],
            method=request.method,
            path=request.path,
            remote=request.remote,
        )
        return await handler(request)

    return incoming_request_logger_middleware


def _access_logger_class_builder(server):
    class AccessLogger(AbstractAccessLogger):
        def log(self, request, response, time):
            server._log.info(
                "server_request",
                request_id=request["id"],
                method=request.method,
                path=request.path,
                remote=request.remote,
                content_length=response.content_length,
                status=response.status,
                time=time,
            )

            body = None
            try:
                body = response.body.decode("UTF-8")
            except AttributeError:
                pass

            server._log.debug(
                "server_response_body", request_id=request["id"], body=body
            )

    return AccessLogger


@routes.view("/multicloudstack")
class MulticloudStacksView(web.View):
    @docs(summary="List all multicloud stacks.")
    @response_schema(MulticloudStack.list_schema(), int(HTTPStatus.OK))
    async def get(self):
        store = self.request.app["store"]

        multicloud_stack_list = await store.list()

        data = MulticloudStack.dump_list(multicloud_stack_list)

        return web.json_response(data, status=HTTPStatus.OK)


@routes.view("/multicloudstack/{stack_name}")
class MulticloudStackView(web.View):
    @docs(
        summary="Get single multicloud stack.",
        responses={
            HTTPStatus.NOT_FOUND: {"description": "Multicloud stack not found"}
        },
    )
    @response_schema(MulticloudStack.schema(), int(HTTPStatus.OK))
    async def get(self):
        store = self.request.app["store"]

        stack_name = self.request.match_info["stack_name"]

        try:
            multicloud_stack = await store.get(stack_name)
        except MulticloudStackNotFound as exc:
            return web.json_response(
                {"error": str(exc)}, status=HTTPStatus.NOT_FOUND
            )

        return web.json_response(multicloud_stack.dump(), status=HTTPStatus.OK)

    @docs(
        summary="Create or update multicloud stack.",
        responses={
            HTTPStatus.CONFLICT: {
                "description": "Conflict in multicloud stack update request"
            },
            HTTPStatus.UNPROCESSABLE_ENTITY: {
                "description": "Multicloud stack validation error"
            },
        },
    )
    @request_schema(MulticloudStack.schema())
    @response_schema(MulticloudStack.schema(), int(HTTPStatus.OK))
    async def put(self):
        store = self.request.app["store"]

        stack_name = self.request.match_info["stack_name"]

        multicloud_stack = self.request["data"]

        if multicloud_stack.stack_name != stack_name:
            return web.json_response(
                {
                    "error": (
                        "stack name in URI and body are mismatching and "
                        "updating the stack name is not currently "
                        "supported"
                    )
                },
                status=HTTPStatus.CONFLICT,
            )

        await store.set(multicloud_stack)

        return web.json_response(multicloud_stack.dump(), status=HTTPStatus.OK)

    @docs(
        summary="Delete multicloud stack.",
        responses={
            HTTPStatus.OK: {},
            HTTPStatus.NOT_FOUND: {
                "description": "Multicloud stack not found"
            },
        },
    )
    async def delete(self):
        store = self.request.app["store"]

        stack_name = self.request.match_info["stack_name"]

        try:
            await store.delete(stack_name)
        except MulticloudStackNotFound as exc:
            return web.json_response(
                {"error": str(exc)}, status=HTTPStatus.NOT_FOUND
            )

        return web.Response(status=HTTPStatus.OK)


class Server:
    def __init__(self, config, store):
        self._config = config

        self._app = web.Application()

        self._log = log

        self._app.middlewares.append(request_id_middleware)
        self._app.middlewares.append(
            incoming_request_logger_middleware_factory(self)
        )

        self._app["store"] = store

        self._app.middlewares.append(validation_middleware)

        self._app.router.add_routes(routes)

        self._runner = web.AppRunner(
            self._app, access_log_class=_access_logger_class_builder(self)
        )

        setup_aiohttp_apispec(
            app=self._app,
            title="Heat Spreader HTTP API documentation",
            version="v1",
            url="/api/docs/swagger.json",
            swagger_path="/api/docs",
        )

    @property
    def address(self):
        return self._address

    @property
    def port(self):
        return self._port

    async def start(self):
        await self._runner.setup()

        site = web.TCPSite(
            runner=self._runner,
            host=self._config.address,
            port=self._config.port,
            shutdown_timeout=self._config.shutdown_timeout,
        )

        await site.start()

        self._address = self._runner.addresses[0][0]
        self._port = self._runner.addresses[0][1]

        self._log = self._log.bind(address=self._address, port=self._port)

        self._log.info("server_serving")

    async def stop(self):
        await self._runner.cleanup()

        self._log.info("server_stopped")
