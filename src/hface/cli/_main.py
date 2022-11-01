# Copyright 2022 Akamai Technologies, Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from __future__ import annotations

import argparse
from typing import Type

from .. import __version__ as version
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
    parser.add_argument("--version", action="version", version=f"hface {version}")

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
