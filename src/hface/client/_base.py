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

import enum

from hface import ClientTLSConfig
from hface.connections import HTTPOpener, HTTPOverQUICOpener, HTTPOverTCPOpener
from hface.networking import ClientNetworking
from hface.protocols import (
    ALPNHTTPFactory,
    HTTPOverQUICClientFactory,
    HTTPOverTCPFactory,
)
from hface.protocols.http1 import HTTP1ClientFactory
from hface.protocols.http2 import HTTP2ClientFactory
from hface.protocols.http3 import HTTP3ClientFactory


class ClientProtocol(enum.Enum):
    """Specifies for how to open connections to the server."""

    #: Open TCP connections, use ALPN to choose beteween HTTP/1 and HTTP/2
    TCP = "tcp"
    #: Open HTTP/1 connections
    HTTP1 = "http1"
    #: Open HTTP/2 connections
    HTTP2 = "http2"
    #: Open HTTP/3 connections. Use QUIC instead of TCP.
    HTTP3 = "http3"


class BaseClient:

    #: TLS configuration for the client.
    tls_config: ClientTLSConfig

    #: A protocol used to open connections.
    protocol: ClientProtocol = ClientProtocol.TCP

    #: Sans-IO HTTP/1 implementation
    http1_factory: HTTPOverTCPFactory
    #: Sans-IO HTTP/2 implementation
    http2_factory: HTTPOverTCPFactory
    #: Sans-IO HTTP/3 implementation
    http3_factory: HTTPOverQUICClientFactory

    def __init__(self) -> None:
        self.tls_config = ClientTLSConfig()
        self.http1_factory = HTTP1ClientFactory()
        self.http2_factory = HTTP2ClientFactory()
        self.http3_factory = HTTP3ClientFactory()

    def _get_http_opener(self, networking: ClientNetworking) -> HTTPOpener:
        if self.protocol == ClientProtocol.TCP:
            return self._http_over_tcp_opener(self._alpn_http_factory, networking)
        elif self.protocol == ClientProtocol.HTTP1:
            return self._http_over_tcp_opener(self.http1_factory, networking)
        elif self.protocol == ClientProtocol.HTTP2:
            return self._http_over_tcp_opener(self.http2_factory, networking)
        elif self.protocol == ClientProtocol.HTTP3:
            return self._http_over_quic_opener(self.http3_factory, networking)
        else:
            raise RuntimeError("Unexpected client protocol.")

    def _http_over_tcp_opener(
        self,
        http_factory: HTTPOverTCPFactory,
        networking: ClientNetworking,
    ) -> HTTPOpener:
        return HTTPOverTCPOpener(http_factory, networking, tls_config=self.tls_config)

    def _http_over_quic_opener(
        self,
        http_factory: HTTPOverQUICClientFactory,
        networking: ClientNetworking,
    ) -> HTTPOpener:
        return HTTPOverQUICOpener(http_factory, networking, tls_config=self.tls_config)

    @property
    def _alpn_http_factory(self) -> HTTPOverTCPFactory:
        return ALPNHTTPFactory([self.http2_factory, self.http1_factory])
