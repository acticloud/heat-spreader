from ...client import Client

from ..views import StackTable

from .command import Command


class StackShowCommand(Command):
    name = "show"
    help = "show multicloud stack details"

    def __init__(self, parser):
        parser.add_argument("name", help="the name of the stack")

    async def run(self, shell_args, config, **kwargs):
        async with Client(config.backend) as client:
            multicloud_stack = await client.get(shell_args.name)

        print(StackTable(multicloud_stack))
