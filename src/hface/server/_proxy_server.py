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
from math import inf

import anyio
from anyio.abc import ByteStream, TaskGroup
from anyio.streams.memory import MemoryObjectReceiveStream, MemoryObjectSendStream

from hface import HeadersType
from hface.connections import HTTPConnection
from hface.events import (
    ConnectionTerminated,
    DataReceived,
    Event,
    HeadersReceived,
    StreamEvent,
    StreamReset,
)
from hface.server._base import BaseServer

logger = logging.getLogger("hface.proxy")


def _parse_request(headers: HeadersType) -> tuple[bytes, bytes]:
    method = authority = None
    for name, value in headers:
        if name == b":method":
            method = value
        elif name == b":authority":
            authority = value
    assert method is not None
    assert authority is not None
    return method, authority


class StreamController:

    _connection: HTTPConnection
    _connection_id: int
    _stream_id: int
    _tunnel_tasks: TaskGroup

    _client_cancel_scope: anyio.CancelScope
    _origin_cancel_scope: anyio.CancelScope
    _max_receive_buffer_size: float = inf
    _receive_feeder: MemoryObjectSendStream[bytes]
    _receive_queue: MemoryObjectReceiveStream[bytes]

    def __init__(
        self,
        *,
        connection: HTTPConnection,
        connection_id: int,
        stream_id: int,
        tunnel_tasks: TaskGroup,
    ) -> None:
        self._connection = connection
        self._connection_id = connection_id
        self._stream_id = stream_id
        self._tunnel_tasks = tunnel_tasks
        self._receive_feeder, self._receive_queue = anyio.create_memory_object_stream(
            max_buffer_size=self._max_receive_buffer_size,
        )
        self._client_cancel_scope = anyio.CancelScope()
        self._origin_cancel_scope = anyio.CancelScope()

    def handle_event(self, event: Event) -> None:
        if isinstance(event, HeadersReceived):
            self._tunnel_tasks.start_soon(self._run, event.headers)
            if event.end_stream:
                self._receive_feeder.close()
        elif isinstance(event, DataReceived):
            self._receive_feeder.send_nowait(event.data)
            if event.end_stream:
                self._receive_feeder.close()
        elif isinstance(event, (ConnectionTerminated, StreamReset)):
            self._client_cancel_scope.cancel()
            self._receive_feeder.close()
            self._receive_queue.close()

    async def _run(self, headers: HeadersType) -> None:
        if self._client_cancel_scope.cancel_called:
            logger.info(
                f"Connection {self._connection_id}/{self._stream_id}: "
                "Terminated by the client before starting to process its request."
            )
            return
        with self._client_cancel_scope:
            method, authority = _parse_request(headers)
            if method != b"CONNECT":
                await self._send_error(405, "Method not allowed.")
                return
            try:
                host_bytes, _, port_bytes = authority.partition(b":")
                host = host_bytes.decode()
                port = int(port_bytes.decode())
            except (ValueError, TypeError):
                await self._send_error(400, "Invalid authority.")
                return
            try:
                socket = await anyio.connect_tcp(host, port)
            except OSError:
                await self._send_error(502, "Connection failed.")
                return
            async with socket:
                await self._send_success()
                await self._run_tunnel(socket)

        if self._client_cancel_scope.cancel_called:
            logger.info(  # type: ignore[unreachable]
                f"Connection {self._connection_id}/{self._stream_id}: "
                "The tunnel was terminated by the client."
            )
        elif self._origin_cancel_scope.cancel_called:
            logger.info(
                f"Connection {self._connection_id}/{self._stream_id}: "
                "The tunnel was terminated by the origin."
            )
        else:
            logger.info(
                f"Connection {self._connection_id}/{self._stream_id}: "
                "Gracefully closed by both the client and the origin."
            )

    async def _run_tunnel(self, socket: ByteStream) -> None:
        async with anyio.create_task_group() as tg:
            assert not self._origin_cancel_scope.cancel_called
            with anyio.CancelScope() as self._origin_cancel_scope:
                tg.start_soon(self._run_upload, socket)
                tg.start_soon(self._run_download, socket)
            if self._origin_cancel_scope.cancel_called:
                error_code = self._connection.error_codes.connect_error
                await self._connection.send_stream_reset(self._stream_id, error_code)

    async def _run_upload(self, socket: ByteStream) -> None:
        while True:
            try:
                data = await self._receive_queue.receive()
            except anyio.EndOfStream:
                await socket.send_eof()
                logger.debug(
                    f"Connection {self._connection_id}/{self._stream_id}: "
                    "Received EOF from the client, "
                    "so sent EOF to the origin and stopped uploading."
                )
                break
            try:
                await socket.send(data)
            except anyio.BrokenResourceError:
                self._origin_cancel_scope.cancel()
                break

    async def _run_download(self, socket: ByteStream) -> None:
        while True:
            try:
                data = await socket.receive()
            except anyio.EndOfStream:
                await self._connection.send_data(self._stream_id, b"", end_stream=True)
                logger.debug(
                    f"Connection {self._connection_id}/{self._stream_id}: "
                    "Received EOF from the origin, "
                    "so sent EOF to the client and stopped downloading."
                )
                break
            except anyio.BrokenResourceError:
                self._origin_cancel_scope.cancel()
                break

            await self._connection.send_data(self._stream_id, data)

    async def _send_success(self) -> None:
        await self._connection.send_headers(self._stream_id, [(b":status", b"200")])
        logger.info(
            f"Connection {self._connection_id}/{self._stream_id}: "
            f"CONNECT request succeeded, a tunnel was established."
        )

    async def _send_error(self, status: int = 400, message: str = "") -> None:
        content = message.encode()
        headers = [
            (b":status", str(status).encode()),
            (b"content-length", str(len(content)).encode()),
            (b"content-type", b"text/plain; charset=UTF-8"),
        ]
        await self._connection.send_headers(self._stream_id, headers)
        await self._connection.send_data(self._stream_id, content, end_stream=True)
        logger.warning(
            f"Connection {self._connection_id}/{self._stream_id}: "
            f"CONNECT request failed: {status} {message}"
        )


class ConnectionController:
    """
    Maintains one HTTP connections, possibly consisting of multiple streams.
    """

    _connection: HTTPConnection
    _connection_id: int
    _tunnel_tasks: TaskGroup

    _streams: dict[int, StreamController]
    _terminated: bool = False

    def __init__(
        self,
        *,
        connection: HTTPConnection,
        connection_id: int,
        tunnel_tasks: TaskGroup,
    ) -> None:
        self._connection = connection
        self._connection_id = connection_id
        self._streams = {}
        self._tunnel_tasks = tunnel_tasks

    async def run(self) -> None:
        """
        Consume and dispatch events on the connection.
        """
        logger.info(
            f"Connection #{self._connection_id}: Serving: "
            f"local_address={self._connection.local_address}, "
            f"remote_address={self._connection.remote_address}"
        )
        while not self._terminated:
            event = await self._connection.receive_event()
            self._handle_event(event)
        logger.info(f"Connection #{self._connection_id}: Done serving.")

    def _handle_event(self, event: Event) -> None:
        if isinstance(event, StreamEvent):
            self._handle_stream_event(event)
        else:
            self._handle_connection_event(event)

    def _handle_stream_event(self, event: StreamEvent) -> None:
        if isinstance(event, HeadersReceived):
            assert event.stream_id not in self._streams
            self._streams[event.stream_id] = StreamController(
                connection=self._connection,
                connection_id=self._connection_id,
                stream_id=event.stream_id,
                tunnel_tasks=self._tunnel_tasks,
            )
        self._streams[event.stream_id].handle_event(event)

    def _handle_connection_event(self, event: Event) -> None:
        if isinstance(event, ConnectionTerminated):
            self._terminated = True
        for controller in self._streams.values():
            controller.handle_event(event)


class ProxyServer(BaseServer):

    _connection_counter: int = 0

    async def handle_connection(self, connection: HTTPConnection) -> None:
        async with connection:
            async with anyio.create_task_group() as tunnel_tasks:
                self._connection_counter += 1
                controller = ConnectionController(
                    connection=connection,
                    connection_id=self._connection_counter,
                    tunnel_tasks=tunnel_tasks,
                )
                await controller.run()
