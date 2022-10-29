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
from abc import ABCMeta, abstractmethod
from typing import AsyncIterator, Sequence

import anyio

from hface import ServerTLSConfig
from hface.connections import (
    HTTPConnection,
    HTTPListener,
    HTTPMultiListener,
    HTTPOverQUICListener,
    HTTPOverTCPListener,
)
from hface.networking import ServerNetworking, SystemNetworking
from hface.protocols import (
    ALPNHTTPFactory,
    HTTPOverQUICServerFactory,
    HTTPOverTCPFactory,
    http1,
    http2,
    http3,
)

from ._models import Endpoint


class ServerProtocol(enum.Enum):
    """
    Specifies for what connections a server should listen.
    """

    #: Listen for all HTTP versions.
    ALL = "all"
    #: Listen for HTTP/1 and HTTP/2 connections.
    TCP = "tcp"
    #: Listen for HTTP/1 connections only.
    HTTP1 = "http1"
    #: Listen for HTTP/2 connections only.
    HTTP2 = "http2"
    #: Listen for HTTP/3 connections only.
    HTTP3 = "http3"


class BaseServer(metaclass=ABCMeta):

    #: TLS certificate for the server.
    #:
    #: Empty by default, must be configured to listen at ``https://`` endpoints.
    tls_config: ServerTLSConfig

    #: Protocol or protocols to listen at.
    protocol: ServerProtocol = ServerProtocol.ALL

    #: Sans-IO HTTP/1 implementation
    http1_factory: HTTPOverTCPFactory
    #: Sans-IO HTTP/2 implementation
    http2_factory: HTTPOverTCPFactory
    #: Sans-IO HTTP/3 implementation
    http3_factory: HTTPOverQUICServerFactory

    def __init__(self) -> None:
        self.tls_config = ServerTLSConfig()
        self.http1_factory = http1.HTTP1ServerFactory()
        self.http2_factory = http2.HTTP2ServerFactory()
        self.http3_factory = http3.HTTP3ServerFactory()

    async def run(self, endpoints: Sequence[Endpoint]) -> None:
        """
        Run the server.

        :param endpoints: endpoints to listen at
        """
        async with await self._create_listener(endpoints) as listener:
            await listener.serve(self.handle_connection)

    @abstractmethod
    async def handle_connection(self, connection: HTTPConnection) -> None:
        """
        Serve one HTTP connection
        """
        raise NotImplementedError

    async def _create_listener(self, endpoints: Sequence[Endpoint]) -> HTTPListener:
        listeners = []
        try:
            for endpoint in endpoints:
                async for listener in self._endpoint_listeners(endpoint):
                    listeners.append(listener)
        except BaseException:
            for listener in listeners:
                await anyio.aclose_forcefully(listener)
            raise
        if len(listeners) == 0:
            raise ValueError("No valid endpoint provided.")
        if len(listeners) == 1:
            return listeners[0]
        return HTTPMultiListener(listeners)

    async def _endpoint_listeners(
        self, endpoint: Endpoint
    ) -> AsyncIterator[HTTPListener]:
        if self.protocol == ServerProtocol.ALL:
            yield await self._tcp_listener(endpoint, self._alpn_http_factory)
            if endpoint.tls:
                yield await self._quic_listener(endpoint, self.http3_factory)
        elif self.protocol == ServerProtocol.TCP:
            yield await self._tcp_listener(endpoint, self._alpn_http_factory)
        elif self.protocol == ServerProtocol.HTTP1:
            yield await self._tcp_listener(endpoint, self.http1_factory)
        elif self.protocol == ServerProtocol.HTTP2:
            yield await self._tcp_listener(endpoint, self.http2_factory)
        elif self.protocol == ServerProtocol.HTTP3:
            if endpoint.tls:
                yield await self._quic_listener(endpoint, self.http3_factory)
        else:
            raise RuntimeError("Unexpected server protocol")

    async def _tcp_listener(
        self, endpoint: Endpoint, http_factory: HTTPOverTCPFactory
    ) -> HTTPListener:
        return await HTTPOverTCPListener.create(
            http_factory,
            self._networking,
            local_address=endpoint.address,
            tls_config=self.tls_config if endpoint.tls else None,
        )

    async def _quic_listener(
        self,
        endpoint: Endpoint,
        http_factory: HTTPOverQUICServerFactory,
    ) -> HTTPListener:
        return await HTTPOverQUICListener.create(
            http_factory,
            self._networking,
            local_address=endpoint.address,
            tls_config=self.tls_config,
        )

    @property
    def _alpn_http_factory(self) -> HTTPOverTCPFactory:
        return ALPNHTTPFactory([self.http2_factory, self.http1_factory])

    @property
    def _networking(self) -> ServerNetworking:
        return SystemNetworking()
