import argparse

from marshmallow.exceptions import ValidationError

from ..client.exceptions import WeightNotFound
from ..store.backend.exceptions import BackendException
from ..store.exceptions import MulticloudStackNotFound

from .command.run import RunCommand
from .command.stack_add import StackAddCommand
from .command.stack_delete import StackDeleteCommand
from .command.stack_list import StackListCommand
from .command.stack_show import StackShowCommand
from .command.stack_update import StackUpdateCommand
from .command.version import VersionCommand
from .command.weight import WeightCommand
from .helpers import validation_error_formatter
from .utils import init_subcommands

SUBCOMMANDS = [
    RunCommand,
    StackAddCommand,
    StackDeleteCommand,
    StackListCommand,
    StackShowCommand,
    StackUpdateCommand,
    VersionCommand,
    WeightCommand,
]


class ShellException(Exception):
    pass


class Shell:
    def __init__(self, config):
        self.config = config

        self.parser = argparse.ArgumentParser(description="Heat Spreader")

        async def _print_help(**_):
            self.parser.print_help()

        self.parser.set_defaults(call=_print_help)

        subparsers = self.parser.add_subparsers(title="commands")

        init_subcommands(subparsers, SUBCOMMANDS)

    async def run(self):
        args = self.parser.parse_args()

        try:
            return await args.call(shell_args=args, config=self.config)
        except BackendException as exc:
            raise ShellException(f"Store backend error: {exc}") from exc
        except ValidationError as exc:
            err_msg = validation_error_formatter(exc)
            raise ShellException(f"Validation error: {err_msg}") from exc
        except (MulticloudStackNotFound, WeightNotFound) as exc:
            raise ShellException(str(exc)) from exc
