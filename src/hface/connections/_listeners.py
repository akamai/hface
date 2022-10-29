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

from abc import abstractmethod
from typing import Any, Callable, Coroutine

from anyio.abc import Listener, TaskGroup
from anyio.streams.stapled import MultiListener
from anyio.streams.tls import TLSAttribute

from hface import AddressType, ServerTLSConfig
from hface.networking import (
    ByteStream,
    DatagramStream,
    QUICServerNetworking,
    QUICStream,
    SystemNetworking,
    TCPServerNetworking,
)
from hface.protocols import (
    HTTPOverQUICServerFactory,
    HTTPOverTCPFactory,
    HTTPOverTCPProtocol,
)

from ._connections import HTTPConnection
from ._transports import TCPTransport, UDPTransport

HandlerType = Callable[[HTTPConnection], Coroutine[Any, Any, Any]]


class HTTPListener(Listener[HTTPConnection]):
    """Interface for listeners that accept HTTP connections"""

    # The serve method is inherited from the parent Listener class,
    # but we redefine it here for documentation purposes.

    @abstractmethod
    async def serve(
        self,
        handler: Callable[[HTTPConnection], Any],
        task_group: TaskGroup | None = None,
    ) -> None:
        """
        Accept incoming connections as they come in and start tasks to handle them.

        :param handler: a callable that will be used to handle each accepted connection
        :param task_group: AnyIO task group that will be used to start tasks for
            accepted connection (if omitted, an ad-hoc task group will be created)
        """
        raise NotImplementedError


class HTTPOverTCPListener(HTTPListener):
    """
    Accepts HTTP connections from a TCP socket.

    Implements :class:`.HTTPListener`.

    :param http_factory: a factory that will construct a Sans-IO protocol
        for each accepted connection.
    :param network_listener: AnyIO listener that will accept TCP connections.
    """

    _http_factory: HTTPOverTCPFactory
    _network_listener: Listener[ByteStream]

    def __init__(
        self,
        http_factory: HTTPOverTCPFactory,
        network_listener: Listener[ByteStream],
    ) -> None:
        self._network_listener = network_listener
        self._http_factory = http_factory

    @classmethod
    async def create(
        cls,
        http_factory: HTTPOverTCPFactory,
        networking: TCPServerNetworking | None = None,
        *,
        local_address: AddressType,
        tls_config: ServerTLSConfig | None,
    ) -> HTTPOverTCPListener:
        """
        Create a new listener for the given local address.

        :param http_factory: a factory that will construct a Sans-IO protocol
            for each accepted connection.
        :param networking: networking implementation to use.
            Defaults to :class:`.SystemNetworking`
        :param local_address: an IP address and a port number to listen on.
        :param tls_config: TLS configuration for secure (https) connections.
            ``None`` for insecure (http) connections.
        """
        if networking is None:
            networking = SystemNetworking()
        if tls_config is None:
            network_listener = await networking.listen_tcp(local_address)
        else:
            network_listener = await networking.listen_tcp_tls(
                local_address,
                tls_config=tls_config,
                alpn_protocols=http_factory.alpn_protocols,
            )
        return cls(http_factory, network_listener)

    async def aclose(self) -> None:
        """
        Close the underlying network listener.
        """
        await self._network_listener.aclose()

    async def serve(
        self, handler: HandlerType, task_group: TaskGroup | None = None
    ) -> None:
        async def socket_handler(socket: ByteStream) -> None:
            http = self._get_http_protocol(socket)
            transport = TCPTransport(http, socket)
            connection = HTTPConnection(transport)
            await handler(connection)

        await self._network_listener.serve(socket_handler, task_group=task_group)

    def _get_http_protocol(self, socket: ByteStream) -> HTTPOverTCPProtocol:
        alpn_protocol = socket.extra(TLSAttribute.alpn_protocol, None)
        tls_version = socket.extra(TLSAttribute.tls_version, None)
        return self._http_factory(
            tls_version=tls_version,
            alpn_protocol=alpn_protocol,
        )


class HTTPOverQUICListener(HTTPListener):
    """
    Accepts HTTP connections over QUIC (at a UDP socket).

    Implements :class:`.HTTPListener`.

    :param http_factory: a factory that will construct a Sans-IO protocol
        for each accepted connection.
    :param network_listener: listener that will accept QUIC connections.
    :param tls_config: TLS configuration
    """

    _http_factory: HTTPOverQUICServerFactory
    _network_listener: Listener[QUICStream]
    _tls_config: ServerTLSConfig

    def __init__(
        self,
        http_factory: HTTPOverQUICServerFactory,
        network_listener: Listener[QUICStream],
        *,
        tls_config: ServerTLSConfig,
    ) -> None:
        self._http_factory = http_factory
        self._network_listener = network_listener
        self._tls_config = tls_config

    @classmethod
    async def create(
        cls,
        http_factory: HTTPOverQUICServerFactory,
        networking: QUICServerNetworking | None = None,
        *,
        local_address: AddressType,
        tls_config: ServerTLSConfig,
    ) -> HTTPOverQUICListener:
        """
        Create a new listener for the given local address.

        :param http_factory: a factory that will construct a Sans-IO protocol
            for each accepted connection.
        :param networking: networking implementation to use.
            Defaults to :class:`.SystemNetworking`
        :param local_address: an IP address and a port number to listen on.
        :param tls_config: TLS configuration
        """
        if networking is None:
            networking = SystemNetworking()
        network_listener = await networking.listen_quic(
            local_address,
            quic_connection_id_length=http_factory.quic_connection_id_length,
            quic_supported_versions=http_factory.quic_supported_versions,
        )
        return cls(http_factory, network_listener, tls_config=tls_config)

    async def aclose(self) -> None:
        await self._network_listener.aclose()

    async def serve(
        self, handler: HandlerType, task_group: TaskGroup | None = None
    ) -> None:
        async def socket_handler(socket: DatagramStream) -> None:
            http = self._http_factory(tls_config=self._tls_config)
            transport = UDPTransport(http, socket)
            connection = HTTPConnection(transport)
            await handler(connection)

        await self._network_listener.serve(socket_handler, task_group=task_group)


class HTTPMultiListener(MultiListener[HTTPConnection], HTTPListener):
    """
    Combines multiple HTTP listeners into one.

    Implements :class:`.HTTPListener`.

    :param listeners: listeners to serve
    :type listeners: Sequence[HTTPListener]
    """
