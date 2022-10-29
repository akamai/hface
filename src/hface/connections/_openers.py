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

from abc import ABCMeta, abstractmethod

import anyio
from anyio.streams.tls import TLSAttribute

from hface import AddressType, ClientTLSConfig
from hface.networking import SystemNetworking, TCPClientNetworking, UDPClientNetworking
from hface.protocols import (
    HTTPOverQUICClientFactory,
    HTTPOverQUICProtocol,
    HTTPOverTCPFactory,
    HTTPOverTCPProtocol,
)

from ._connections import HTTPConnection
from ._transports import TCPTransport, UDPTransport


class HTTPOpener(metaclass=ABCMeta):
    """
    Opens HTTP connections.
    """

    @abstractmethod
    async def __call__(
        self,
        remote_address: AddressType,
        tls: bool = False,
        *,
        server_name: str | None = None,
    ) -> HTTPConnection:
        """
        Open connection to the given origin.

        :param: an IP address and a port number to connect to
        :param tls: whether to secure the connection using TLS
        :param server_name: override server name sent in TLS SNI
        :return: a new HTTP connection
        """
        raise NotImplementedError


class HTTPOverTCPOpener(HTTPOpener):
    """
    Opens a new HTTP connections over a TPC.

    Implements :class:`.HTTPOpener`.

    :param http_factory: a factory that will construct a Sans-IO protocol
        for each opened connection.
    :param networking: networking implementation to use.
        Defaults to :class:`.SystemNetworking`
    :param tls_config: TLS configuration for secure (https) connections
    """

    _http_factory: HTTPOverTCPFactory
    _networking: TCPClientNetworking
    _tls_config: ClientTLSConfig

    def __init__(
        self,
        http_factory: HTTPOverTCPFactory,
        networking: TCPClientNetworking | None = None,
        *,
        tls_config: ClientTLSConfig | None = None,
    ) -> None:
        self._http_factory = http_factory
        self._networking = networking or SystemNetworking()
        self._tls_config = tls_config or ClientTLSConfig()

    async def __call__(
        self,
        remote_address: AddressType,
        tls: bool = False,
        *,
        server_name: str | None = None,
    ) -> HTTPConnection:
        if tls:
            socket = await self._networking.connect_tcp_tls(
                remote_address,
                tls_config=self._tls_config,
                alpn_protocols=self._http_factory.alpn_protocols,
                server_name=server_name,
            )
        else:
            socket = await self._networking.connect_tcp(remote_address)
        http = self._get_http_protocol(socket)
        transport = TCPTransport(http, socket)
        return HTTPConnection(transport)

    def _get_http_protocol(
        self, socket: anyio.TypedAttributeProvider
    ) -> HTTPOverTCPProtocol:
        alpn_protocol = socket.extra(TLSAttribute.alpn_protocol, None)
        tls_version = socket.extra(TLSAttribute.tls_version, None)
        return self._http_factory(
            tls_version=tls_version,
            alpn_protocol=alpn_protocol,
        )


class HTTPOverQUICOpener(HTTPOpener):
    """
    Opens a new HTTP connections over a QUIC.

    Implements :class:`.HTTPOpener`.

    :param http_factory: a factory that will construct a Sans-IO protocol
        for each opened connection.
    :param networking: networking implementation to use.
        Defaults to :class:`.SystemNetworking`
    :param tls_config: TLS configuration for secure (https) connections
    """

    _http_factory: HTTPOverQUICClientFactory
    _networking: UDPClientNetworking
    _tls_config: ClientTLSConfig

    def __init__(
        self,
        http_factory: HTTPOverQUICClientFactory,
        networking: UDPClientNetworking | None = None,
        *,
        tls_config: ClientTLSConfig,
    ) -> None:
        self._http_factory = http_factory
        self._networking = networking or SystemNetworking()
        self._tls_config = tls_config

    async def __call__(
        self,
        remote_address: AddressType,
        tls: bool = False,
        *,
        server_name: str | None = None,
    ) -> HTTPConnection:
        if not tls:
            raise ValueError("QUIC does not support insecure connections.")
        socket = await self._networking.connect_udp(remote_address)
        http = self._get_http_protocol(remote_address, server_name=server_name)
        transport = UDPTransport(http, socket, remote_address=remote_address)
        return HTTPConnection(transport)

    def _get_http_protocol(
        self, address: AddressType, *, server_name: str | None
    ) -> HTTPOverQUICProtocol:
        return self._http_factory(
            remote_address=address,
            server_name=server_name or address[0],
            tls_config=self._tls_config,
        )
