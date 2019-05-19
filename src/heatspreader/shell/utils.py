def init_subcommands(subparsers, commands):
    for cmd in commands:
        parser = subparsers.add_parser(cmd.name, help=cmd.help)

        parser.set_defaults(call=cmd(parser).run)
