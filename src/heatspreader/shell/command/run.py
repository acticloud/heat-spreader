from ...service import Runner

from .command import Command


class RunCommand(Command):
    name = "run"
    help = "start running the Heat Spreader service"

    def __init__(self, parser):
        pass

    async def run(self, config, **kwargs):
        await Runner(config).run()
