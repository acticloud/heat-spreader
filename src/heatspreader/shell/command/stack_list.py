from ...client import Client
from ...state import MulticloudStack

from ..views import StacksTable

from .command import Command


class StackListCommand(Command):
    name = "list"
    help = "list all stacks"

    def __init__(self, parser):
        parser.add_argument("--json", action="store_true", help="output json")

    async def run(self, config, shell_args, **kwargs):
        async with Client(config.backend) as client:
            multicloud_stack_list = await client.list()

            if shell_args.json:
                output = MulticloudStack.dumps_list(multicloud_stack_list)
            else:
                output = StacksTable(multicloud_stack_list)

            print(output)
