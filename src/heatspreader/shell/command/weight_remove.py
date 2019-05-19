from ...client import Client

from ..views import StackTable

from .command import Command


class WeightRemoveCommand(Command):
    name = "remove"
    help = "remove weight"

    def __init__(self, parser):
        parser.add_argument("stack", help="the name of the stack")

        parser.add_argument("cloud", help="the name of the cloud")

    async def run(self, shell_args, config, **kwargs):
        async with Client(config.backend) as client:
            multicloud_stack = await client.weight_unset(
                stack_name=shell_args.stack, cloud_name=shell_args.cloud
            )

        print(StackTable(multicloud_stack))
