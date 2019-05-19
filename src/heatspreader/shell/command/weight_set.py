from ...client import Client
from ...state import MulticloudStack

from ..views import StackTable

from .command import Command


class WeightSetCommand(Command):
    name = "set"
    help = "add/update weight"

    def __init__(self, parser):
        parser.add_argument("stack", help="the name of the stack")

        parser.add_argument("cloud", help="the name of the cloud")

        parser.add_argument(
            "--weight",
            required=True,
            metavar="num",
            help="the scaling weight (between 0 and 1)",
        )

        parser.add_argument("--json", action="store_true", help="output json")

    async def run(self, shell_args, config, **kwargs):
        async with Client(config.backend) as client:
            multicloud_stack = await client.weight_set(
                stack_name=shell_args.stack,
                cloud_name=shell_args.cloud,
                weight=shell_args.weight,
            )

        if shell_args.json:
            output = MulticloudStack.dumps(multicloud_stack)
        else:
            output = StackTable(multicloud_stack)

        print(output)
