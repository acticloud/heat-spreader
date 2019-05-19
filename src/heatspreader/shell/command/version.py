from .command import Command

from ...version import version


class VersionCommand(Command):
    name = "version"
    help = "print version"

    async def run(self, shell_args, config, **kwargs):
        print(version)
