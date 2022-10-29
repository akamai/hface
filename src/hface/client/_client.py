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

import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator

import anyio
from anyio.abc import AsyncResource, TaskGroup

from hface.connections import HTTPOpener
from hface.networking import ClientNetworking, SystemNetworking

from ._base import BaseClient, ClientProtocol
from ._controllers import HTTPPool, HTTPStream
from ._models import Origin, Request, Response
from ._proxy_client import ProxyClient

logger = logging.getLogger("hface.client")


class ClientSession(AsyncResource):
    """
    Active client session that can be used to issue HTTP requests.

    Maintains a pool of HTTP connections that can be used
    to :meth:`.dispatch` request.

    Use a :class:`.Client` to create instances of this class.

    :param http_opener: Defines how to open new connections.
    :param task_group: AnyIO task group for maintaining HTTP connections.
    """

    _http_opener: HTTPOpener
    _task_group: TaskGroup

    _pools: dict[Origin, HTTPPool]

    def __init__(
        self,
        *,
        http_opener: HTTPOpener,
        task_group: TaskGroup,
    ) -> None:
        self._http_opener = http_opener
        self._task_group = task_group
        self._pools = {}

    async def aclose(self) -> None:
        """
        Close all connections.
        """
        for pool in self._pools.values():
            await pool.aclose()

    async def dispatch(self, request: Request) -> Response:
        """
        Perform an HTTP request and return an HTTP response.

        :param request: an HTTP request
        :returns: an HTTP response
        """
        logger.info(f"{request.method} {request.url}")
        http_stream = await self._send_request(request)
        return await self._receive_response(http_stream)

    async def _send_request(self, request: Request) -> HTTPStream:
        pool = self._get_pool(request.url.origin)
        http_stream = await pool.open_stream(
            request.protocol_headers, end_stream=not request.content
        )
        if request.content:
            await http_stream.send_data(request.content, end_stream=True)
        return http_stream

    async def _receive_response(self, stream: HTTPStream) -> Response:
        response = Response.from_headers(await stream.receive_headers())
        while True:
            try:
                response.content += await stream.receive_data()
            except anyio.EndOfStream:
                break
        return response

    def _get_pool(self, origin: Origin) -> HTTPPool:
        # No lock is needed because this method is not async.
        if origin not in self._pools:
            self._pools[origin] = HTTPPool(
                origin.address,
                origin.tls,
                http_opener=self._http_opener,
                task_group=self._task_group,
            )
        return self._pools[origin]


class Client(BaseClient):
    """
    An HTTP client

    Supports HTTP/1, HTTP/2, and HTTP/3.
    Optionally tunnels traffic through an HTTP proxy.

    Client instances have no state.
    The :meth:`.Client.session` method must be used to open
    :class:`.ClientSession` to make HTTP requests.
    """

    #: A proxy server
    proxy_origin: Origin | None = None
    #: A protocol used to open connections to the proxy server (if set)
    proxy_protocol: ClientProtocol = ClientProtocol.TCP

    @asynccontextmanager
    async def session(self) -> AsyncIterator[ClientSession]:
        """
        Start a new client session.

        :rtype: ClientSession
        """
        async with anyio.create_task_group() as task_group:
            async with self._networking_session() as networking:
                http_opener = self._get_http_opener(networking)
                async with ClientSession(
                    http_opener=http_opener, task_group=task_group
                ) as session:
                    yield session

    @asynccontextmanager
    async def _networking_session(self) -> AsyncIterator[ClientNetworking]:
        if self.proxy_origin is not None:
            proxy = ProxyClient(self.proxy_origin)
            proxy.protocol = self.proxy_protocol
            proxy.tls_config = self.tls_config
            proxy.http1_factory = self.http1_factory
            proxy.http2_factory = self.http2_factory
            proxy.http3_factory = self.http3_factory
            async with proxy.session() as proxy_session:
                yield proxy_session
        else:
            yield SystemNetworking()
