from __future__ import annotations

import argparse
from typing import Type

from ._commands.base import Command
from ._commands.client import ClientCommand
from ._commands.proxy import ProxyCommand
from ._commands.server import ServerCommand

COMMANDS: dict[str, Type[Command]] = {
    "client": ClientCommand,
    "proxy": ProxyCommand,
    "server": ServerCommand,
}


def run(*, prog: str | None = None) -> None:
    """
    Main entry point of a command-line utility.

    :param prog: Program name, included in help output
    """
    parser = argparse.ArgumentParser(
        prog=prog,
        description="HTTP/{1,2,3} {client,server,proxy}.",
        allow_abbrev=False,
    )

    def default_command(args: argparse.Namespace) -> None:
        parser.print_usage()

    parser.set_defaults(command=default_command)
    subparsers = parser.add_subparsers()
    for name, cls in COMMANDS.items():
        subparser = subparsers.add_parser(
            name,
            help=cls.help,  # For root command help
            description=cls.help,  # For subcommand help
        )
        cls.parse(subparser)
        subparser.set_defaults(command=cls.run_from_args)

    args = parser.parse_args()
    args.command(args)
