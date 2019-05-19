from ...client import Client
from ...state import MulticloudStack

from ..views import StackTable

from .command import Command


class StackAddCommand(Command):
    name = "add"
    help = "add multicloud stack"

    def __init__(self, parser):
        parser.add_argument("name", help="the name of the stack")

        parser.add_argument(
            "--count",
            metavar="num",
            required=True,
            help="the initial desired count",
        )

        parser.add_argument(
            "--parameter",
            metavar="parameter_name",
            required=True,
            help="the count parameter",
        )

        parser.add_argument("--json", action="store_true", help="output json")

    async def run(self, shell_args, config, **kwargs):
        async with Client(config.backend) as client:
            multicloud_stack = await client.create(
                stack_name=shell_args.name,
                count=shell_args.count,
                count_parameter=shell_args.parameter,
            )

        if shell_args.json:
            output = MulticloudStack.dumps(multicloud_stack)
        else:
            output = StackTable(multicloud_stack)

        print(output)
