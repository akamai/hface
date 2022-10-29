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

from contextlib import asynccontextmanager
from typing import Any, AsyncIterator, Callable, Mapping

import anyio
from anyio.abc import AsyncResource, SocketAttribute

from hface import AddressType, HeadersType
from hface.connections import HTTPOpener
from hface.networking import (
    ByteStream,
    ClientNetworking,
    DatagramStream,
    SystemNetworking,
)

from ._base import BaseClient
from ._controllers import HTTPPool, HTTPStream
from ._exceptions import HTTPStatusError
from ._models import Origin


class ProxyAttribute(anyio.TypedAttributeSet):

    #: Network address of the proxy
    proxy_address: AddressType = anyio.typed_attribute()
    #: Network port of the proxy.
    proxy_port: int = anyio.typed_attribute()


class ProxyStream(ByteStream):

    _http_stream: HTTPStream
    _remote_address: AddressType

    def __init__(
        self,
        http_stream: HTTPStream,
        *,
        remote_address: AddressType,
    ) -> None:
        self._http_stream = http_stream
        self._remote_address = remote_address

    async def receive(self, max_bytes: int = 65536) -> bytes:
        # TODO: Handle max_bytes
        return await self._http_stream.receive_data()

    async def send(self, data: bytes) -> None:
        await self._http_stream.send_data(data)

    async def send_eof(self) -> None:
        await self._http_stream.send_data(b"", end_stream=True)

    async def aclose(self) -> None:
        await self._http_stream.aclose()

    @property
    def extra_attributes(self) -> Mapping[Any, Callable[[], Any]]:
        # Translate proxy-connection attributes to origin-connection attributes.
        #
        # - Use an origin address as a remote address because.
        #   (the origin address may be unresolved hostname, IP address is not known).
        # - Save original remote address as a proxy address.
        # - Keep local address.
        #
        # Do not blindly copy all attributes because that could lead
        # to unexpected consequences. For example, when users ask
        # for TLSAttribute.alpn_protocol, they should not get the protocol
        # of the proxy connection instead of the origin connection.
        attributes: dict[Any, Callable[[], Any]] = {
            SocketAttribute.remote_address: lambda: self._remote_address,
            SocketAttribute.remote_port: lambda: self._remote_address[1],
        }
        source_attributes = self._http_stream.connection.extra_attributes
        for attr, source_attr in {
            ProxyAttribute.proxy_address: SocketAttribute.remote_address,
            ProxyAttribute.proxy_port: SocketAttribute.remote_port,
            SocketAttribute.local_address: SocketAttribute.local_address,
            SocketAttribute.local_port: SocketAttribute.local_port,
            SocketAttribute.raw_socket: SocketAttribute.raw_socket,
        }.items():
            try:
                attributes[attr] = source_attributes[source_attr]
            except KeyError:
                pass
        return attributes


class ProxyClientSession(AsyncResource, ClientNetworking):
    """
    An active session with an HTTP proxy.

    Maintains pool of connections to the proxy (for HTTP/2 and HTTP/3
    proxies the pool will not have more than one connection).

    This class implements :class:`.ClientNetworking`, so it can be used
    to open new HTTP connections.

    Use a :class:`.ProxyClient` to create instances of this class.

    :param origin: Proxy server
    :param http_opener: Defines how to open new connections.
    :param task_group: AnyIO task group for maintaining HTTP connections.
    """

    _pool: HTTPPool

    def __init__(
        self,
        origin: Origin,
        *,
        http_opener: HTTPOpener,
        task_group: anyio.abc.TaskGroup,
    ) -> None:
        self._pool = HTTPPool(
            origin.address,
            origin.tls,
            http_opener=http_opener,
            task_group=task_group,
        )

    async def aclose(self) -> None:
        """
        Close all connections.
        """
        await self._pool.aclose()

    async def connect_tcp(self, address: AddressType) -> ByteStream:
        """
        Create a TCP-like stream connected to the given address.
        """
        request_headers = self._get_request_headers(address)
        http_stream = await self._pool.open_stream(request_headers)
        response_headers = await http_stream.receive_headers()
        self._check_response_headers(response_headers)
        return ProxyStream(http_stream, remote_address=address)

    async def connect_udp(self, remote_address: AddressType) -> DatagramStream:
        raise NotImplementedError  # TODO: implement CONNECT-UDP

    def _get_request_headers(self, address: AddressType) -> HeadersType:
        host, port = address
        return [
            (b":method", b"CONNECT"),
            (b":authority", f"{host}:{port}".encode()),
        ]

    def _check_response_headers(self, headers: HeadersType) -> None:
        for name, value in headers:
            if name == b":status":
                if value == b"200":
                    return
                raise HTTPStatusError(value)
        raise RuntimeError("Missing :status header")


class ProxyClient(BaseClient):
    """
    A client that tunnels traffic through HTTP proxies

    This client sends CONNECT requests to an HTTP proxy to establish tunnels.
    The established tunnels can be used to transfer any TCP traffic,
    it is not limited to HTTP.

    Supports HTTP/1, HTTP/2, and HTTP/3 proxies in the tunneling mode.

    Instances of this class have no state, the :meth:`.session` must
    be used to establish :class:`.ProxyClientSession`.

    :param origin: Proxy server to use
    """

    origin: Origin

    def __init__(self, origin: Origin | str) -> None:
        super().__init__()
        if isinstance(origin, str):
            origin = Origin.parse(origin)
        self.origin = origin

    @asynccontextmanager
    async def session(self) -> AsyncIterator[ProxyClientSession]:
        """
        Establish a new session with the proxy.

        :rtype: ProxyClientSession
        """
        async with anyio.create_task_group() as task_group:
            async with ProxyClientSession(
                self.origin,
                http_opener=self._get_http_opener(self._networking),
                task_group=task_group,
            ) as session:
                yield session

    @property
    def _networking(self) -> ClientNetworking:
        return SystemNetworking()
