import asyncio
import signal

import structlog

from ..store import MulticloudStackStore

from .controller import Controller
from .healthcheck import Healthcheck
from .server import Server

SIGNALS_STOP = [signal.SIGINT, signal.SIGTERM]

log = structlog.getLogger(__name__)


class Runner:
    def __init__(self, config):
        self._stopping = False

        self._loop = asyncio.get_event_loop()

        self._store = MulticloudStackStore(config.backend)

        healthcheck = Healthcheck()

        self._controller = Controller(config, self._store, healthcheck)
        self._server = Server(config.server, self._store)

    async def stop(self):
        if self._stopping:
            return

        self._stopping = True

        log.info("runner_graceful_shutdown")

        await self._server.stop()
        await self._controller.stop()

        await self._store.close()

    async def force_stop(self):
        log.info("runner_force_shutdown")

        tasks = [
            t for t in asyncio.all_tasks() if t is not asyncio.current_task()
        ]

        for task in tasks:
            task.cancel()

        await self._controller.force_stop()

    def _force_stop_signal_handler(self):
        asyncio.ensure_future(self.force_stop())

    def _signal_handler(self, s):
        _log = log.bind(signal=s.name)

        _log.debug("runner_caught_signal")

        if s in SIGNALS_STOP:
            for s in SIGNALS_STOP:
                self._loop.remove_signal_handler(s)

            asyncio.ensure_future(self.stop())

            self._loop.add_signal_handler(
                signal.SIGINT, self._force_stop_signal_handler
            )

            print("Interrupt to force stop")
        else:
            _log.error("runner_unhandled_signal")

    async def run(self):
        for s in SIGNALS_STOP:
            self._loop.add_signal_handler(s, self._signal_handler, s)

        await self._server.start()

        try:
            await self._controller.run()
        except asyncio.CancelledError:
            pass
