from ..utils import init_subcommands

from .command import Command
from .weight_remove import WeightRemoveCommand
from .weight_set import WeightSetCommand

SUBCOMMANDS = [WeightRemoveCommand, WeightSetCommand]


class WeightCommand(Command):
    name = "weight"
    help = "weight commands"

    def __init__(self, parser):
        subparsers = parser.add_subparsers(title="weight commands")

        init_subcommands(subparsers, SUBCOMMANDS)

    async def run(self, **kwargs):
        self.parser.print_help()
