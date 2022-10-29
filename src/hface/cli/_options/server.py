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

from hface import ServerTLSConfig
from hface.protocols import protocol_registry
from hface.server import ASGIServer, Endpoint, ProxyServer, ServerProtocol


def parse_server_options(parser: argparse.ArgumentParser) -> None:
    _parse_tls_config(parser)
    _parse_server_protocol(parser)
    _parse_server_engine(parser)


def _parse_tls_config(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--cert",
        dest="tls_certfile",
        help="Path to a TLS certificate for the server in the PEM format.",
    )
    parser.add_argument(
        "--key",
        dest="tls_keyfile",
        help="Path to a secret key for the TLS certificate in the PEM format.",
    )


def _parse_server_protocol(parser: argparse.ArgumentParser) -> None:
    group = parser.add_mutually_exclusive_group()
    group.set_defaults(protocol=ServerProtocol.ALL)
    group.add_argument(
        "--tcp",
        action="store_const",
        dest="protocol",
        const=ServerProtocol.TCP,
        help=(
            "Listen for TCP connections only. "
            "Support HTTP/1 and HTTP/2 (via ALPN in a TLS handshake)."
        ),
    )
    group.add_argument(
        "--http1",
        "--http1.1",
        action="store_const",
        dest="protocol",
        const=ServerProtocol.HTTP1,
        help="Support HTTP/1.1 only.",
    )
    group.add_argument(
        "--http2",
        action="store_const",
        dest="protocol",
        const=ServerProtocol.HTTP2,
        help="Support HTTP/2 only.",
    )
    group.add_argument(
        "--http3",
        "--quic",
        action="store_const",
        dest="protocol",
        const=ServerProtocol.HTTP3,
        help="Support HTTP/3 only (listen for QUIC connections only).",
    )


def _parse_server_engine(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--http1-impl",
        choices=list(protocol_registry.http1_servers.keys()),
        default="default",
        help="Selects implementation of the HTTP/1 protocol.",
    )
    parser.add_argument(
        "--http2-impl",
        choices=list(protocol_registry.http2_servers.keys()),
        default="default",
        help="Selects implementation of the HTTP/2 protocol.",
    )
    parser.add_argument(
        "--http3-impl",
        choices=list(protocol_registry.http3_servers.keys()),
        default="default",
        help="Selects implementation of the HTTP/3 protocol.",
    )


def apply_server_options(
    args: argparse.Namespace, server: ASGIServer | ProxyServer
) -> None:
    server.tls_config = ServerTLSConfig(
        certfile=args.tls_certfile,
        keyfile=args.tls_keyfile,
    )
    server.protocol = args.protocol
    server.http1_factory = protocol_registry.http1_servers[args.http1_impl]
    server.http2_factory = protocol_registry.http2_servers[args.http2_impl]
    server.http3_factory = protocol_registry.http3_servers[args.http3_impl]


def parse_server_endpoints(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        dest="endpoints",
        type=Endpoint.parse,
        nargs="+",
        metavar="ENDPOINT",
        help=(
            "Endpoint to listen at in an URL-like format: " "{http,https}://[HOST]:PORT"
        ),
    )
