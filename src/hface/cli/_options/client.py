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

from hface import ClientTLSConfig
from hface.client import Client, ClientProtocol, Origin
from hface.protocols import protocol_registry


def parse_client_options(parser: argparse.ArgumentParser) -> None:
    _parse_tls_config(parser)
    _parse_protocol(parser)
    _parse_proxy(parser)
    _parse_proxy_protocol(parser)
    _parse_engine(parser)


def _parse_tls_config(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--cacert",
        dest="tls_cafile",
        help="Use the specified certificate file to verify a peer.",
    )
    parser.add_argument(
        "-k",
        "--insecure",
        action="store_true",
        dest="tls_insecure",
        default=False,
        help="Allows to proceed if a peer's TLS certificate is invalid.",
    )


def _parse_protocol(parser: argparse.ArgumentParser) -> None:
    group = parser.add_mutually_exclusive_group()
    group.set_defaults(protocol=ClientProtocol.TCP)
    group.add_argument(
        "--tcp",
        action="store_const",
        dest="protocol",
        const=ClientProtocol.TCP,
        help=(
            "Open TCP connections. "
            "Supports HTTP/1 and HTTP/2 (via ALPN in a TLS handshake). "
            "This is the default behavior."
        ),
    )
    group.add_argument(
        "--http1",
        "--http1.1",
        action="store_const",
        dest="protocol",
        const=ClientProtocol.HTTP1,
        help="Use HTTP/1.1.",
    )
    group.add_argument(
        "--http2",
        action="store_const",
        dest="protocol",
        const=ClientProtocol.HTTP2,
        help="Use HTTP/2.",
    )
    group.add_argument(
        "--http3",
        "--quic",
        action="store_const",
        dest="protocol",
        const=ClientProtocol.HTTP3,
        help="Use HTTP/3. Opens QUIC connections instead of a TCP connections.",
    )


def _parse_proxy(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--proxy",
        dest="proxy_origin",
        type=Origin.parse,
        metavar="PROXY",
        help="HTTP proxy to use in an URL-like format: {http,https}://HOST[:PORT]",
    )


def _parse_proxy_protocol(parser: argparse.ArgumentParser) -> None:
    group = parser.add_mutually_exclusive_group()
    group.set_defaults(proxy_protocol=ClientProtocol.TCP)
    group.add_argument(
        "--proxy-tcp",
        action="store_const",
        dest="proxy_protocol",
        const=ClientProtocol.TCP,
        help="Like --tcp, but for proxy connections.",
    )
    group.add_argument(
        "--proxy-http1",
        action="store_const",
        dest="proxy_protocol",
        const=ClientProtocol.HTTP1,
        help="Like --http1, but for proxy connections.",
    )
    group.add_argument(
        "--proxy-http2",
        action="store_const",
        dest="proxy_protocol",
        const=ClientProtocol.HTTP2,
        help="Like --http2, but for proxy connections.",
    )
    group.add_argument(
        "--proxy-http3",
        "--proxy-quic",
        action="store_const",
        dest="proxy_protocol",
        const=ClientProtocol.HTTP3,
        help="Like --http3, but for proxy connections.",
    )


def _parse_engine(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--http1-impl",
        choices=list(protocol_registry.http1_clients.keys()),
        default="default",
        help="Select implementation of the HTTP/1 protocol.",
    )
    parser.add_argument(
        "--http2-impl",
        choices=list(protocol_registry.http2_clients.keys()),
        default="default",
        help="Select implementation of the HTTP/2 protocol.",
    )
    parser.add_argument(
        "--http3-impl",
        choices=list(protocol_registry.http3_clients.keys()),
        default="default",
        help="Select implementation of the HTTP/3 protocol.",
    )


def apply_client_options(args: argparse.Namespace, client: Client) -> None:
    client.tls_config = ClientTLSConfig(
        insecure=args.tls_insecure,
        cafile=args.tls_cafile,
    )
    client.protocol = args.protocol
    client.proxy_origin = args.proxy_origin
    client.proxy_protocol = args.proxy_protocol
    client.http1_factory = protocol_registry.http1_clients[args.http1_impl]
    client.http2_factory = protocol_registry.http2_clients[args.http2_impl]
    client.http3_factory = protocol_registry.http3_clients[args.http3_impl]
