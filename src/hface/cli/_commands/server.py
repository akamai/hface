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
import dataclasses
import importlib
from typing import Any

from hface.server import ASGIServer, Endpoint

from .._options.common import LoggingOptions, LoopOptions
from .._options.server import (
    apply_server_options,
    parse_server_endpoints,
    parse_server_options,
)
from .base import Command


def import_app(spec: str) -> Any:
    """
    Import a ASGI application by a dotted path.
    """
    module_name, _, attr_name = spec.partition(":")
    if not attr_name:
        attr_name = "application"

    app = importlib.import_module(module_name)
    for key in attr_name.split("."):
        app = getattr(app, key)
    return app


@dataclasses.dataclass
class ServerCommand(Command):
    """Starts an HTTP server with an ASGI application."""

    help = __doc__

    logging: LoggingOptions
    loop: LoopOptions
    server: ASGIServer
    endpoints: list[Endpoint]

    @classmethod
    def parse(cls, parser: argparse.ArgumentParser) -> None:
        parser.add_argument(
            "app",
            type=str,
            metavar="ASGI_APP",
            help="ASGI application in a MODULE_NAME:VARIABLE_NAME format.",
        )
        parse_server_endpoints(parser)
        parse_server_options(parser)
        LoggingOptions.parse(parser)
        LoopOptions.parse(parser)

    @classmethod
    def from_args(cls, args: argparse.Namespace) -> ServerCommand:
        server = ASGIServer(import_app(args.app))
        apply_server_options(args, server)
        return cls(
            loop=LoopOptions.from_args(args),
            logging=LoggingOptions.from_args(args),
            server=server,
            endpoints=args.endpoints,
        )

    def run(self) -> None:
        self.logging.configure()
        self.loop.run(self._run_server)

    async def _run_server(self) -> None:
        await self.server.run(self.endpoints)
