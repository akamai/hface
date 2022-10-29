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
import sys

import anyio

from hface.client import Client, ClientSession, Request

from .._options.client import apply_client_options, parse_client_options
from .._options.common import LoggingOptions, LoopOptions
from .base import Command


@dataclasses.dataclass
class ClientCommand(Command):
    """Make one or more HTTP requests."""

    help = __doc__

    logging: LoggingOptions
    loop: LoopOptions
    client: Client
    requests: list[Request]

    @classmethod
    def parse(cls, parser: argparse.ArgumentParser) -> None:
        cls._parse_requests(parser)
        parse_client_options(parser)
        LoggingOptions.parse(parser)
        LoopOptions.parse(parser)

    @classmethod
    def _parse_requests(cls, parser: argparse.ArgumentParser) -> None:
        parser.add_argument(
            "urls",
            nargs="+",
            metavar="URL",
            help="An URL to request.",
        )
        parser.add_argument(
            "-X",
            "--request",
            dest="method",
            metavar="METHOD",
            help=(
                "An HTTP method to use. "
                "Defaults to GET or POST depending on whether data are given."
            ),
        )
        parser.add_argument(
            "-d",
            "--data",
            help="Send the specified data in the HTTP message body.",
        )

    @classmethod
    def from_args(cls, args: argparse.Namespace) -> ClientCommand:
        client = Client()
        apply_client_options(args, client)
        return cls(
            loop=LoopOptions.from_args(args),
            logging=LoggingOptions.from_args(args),
            client=client,
            requests=cls._requests_from_args(args),
        )

    @classmethod
    def _requests_from_args(cls, args: argparse.Namespace) -> list[Request]:
        method, content = "GET", None
        if args.data is not None:
            method, content = "POST", args.data.encode()
        if args.method is not None:
            method = args.method
        return [Request(method, url, content=content) for url in args.urls]

    def run(self) -> None:
        self.logging.configure()
        self.loop.run(self._run_client)

    async def _run_client(self) -> None:
        async with self.client.session() as session:
            await self._run_session(session, self.requests)

    async def _run_session(
        self, session: ClientSession, requests: list[Request]
    ) -> None:
        async with anyio.create_task_group() as tg:
            for request in requests:
                tg.start_soon(self._run_request, session, request)

    async def _run_request(self, session: ClientSession, request: Request) -> None:
        response = await session.dispatch(request)
        sys.stdout.buffer.write(response.content)
        sys.stdout.buffer.flush()
