from ...client import Client

from .command import Command


class StackDeleteCommand(Command):
    name = "delete"
    help = "delete stack"

    def __init__(self, parser):
        parser.add_argument("name", help="the name of the stack")

    async def run(self, shell_args, config, **kwargs):
        async with Client(config.backend) as client:
            await client.delete(shell_args.name)
