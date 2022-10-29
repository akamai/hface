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

from math import inf

import anyio
from anyio.abc import TaskGroup, TaskStatus
from anyio.streams.memory import MemoryObjectReceiveStream, MemoryObjectSendStream

from hface import AddressType, HeadersType
from hface.connections import HTTPConnection, HTTPOpener
from hface.events import (
    ConnectionTerminated,
    DataReceived,
    Event,
    HeadersReceived,
    StreamEvent,
    StreamReset,
)


class HTTPStream:

    _connection: HTTPConnection
    _stream_id: int

    _headers: HeadersType | None
    _headers_waiter: anyio.Event

    _max_receive_buffer_size: float = inf
    _receive_feeder: MemoryObjectSendStream[bytes]
    _receive_queue: MemoryObjectReceiveStream[bytes]

    _end_stream_sent: bool = False
    _terminated: bool = False

    def __init__(self, connection: HTTPConnection, stream_id: int) -> None:
        self._connection = connection
        self._stream_id = stream_id
        self._headers = None
        self._headers_waiter = anyio.Event()
        self._receive_feeder, self._receive_queue = anyio.create_memory_object_stream(
            max_buffer_size=self._max_receive_buffer_size,
        )

    @property
    def connection(self) -> HTTPConnection:
        return self._connection

    async def send_headers(
        self, headers: HeadersType, end_stream: bool = False
    ) -> None:
        self._end_stream_sent |= end_stream
        await self._connection.send_headers(self._stream_id, headers, end_stream)

    async def receive_headers(self) -> HeadersType:
        await self._headers_waiter.wait()
        if self._terminated:
            raise anyio.BrokenResourceError(
                "HTTP stream was terminated before headers were received."
            )
        assert self._headers is not None
        return self._headers

    async def send_data(self, data: bytes, end_stream: bool = False) -> None:
        self._end_stream_sent |= end_stream
        await self._connection.send_data(self._stream_id, data, end_stream)

    async def receive_data(self) -> bytes:
        try:
            return await self._receive_queue.receive()
        except anyio.EndOfStream:
            pass
        if self._terminated:
            raise anyio.BrokenResourceError("HTTP stream was terminated.")
        raise anyio.EndOfStream("HTTP stream was closed from the other end.")

    async def aclose(self) -> None:
        if not self._end_stream_sent:
            await self.send_data(b"", end_stream=True)
        self._terminate()

    def handle_event(self, event: Event) -> None:
        if isinstance(event, HeadersReceived):
            assert self._headers is None
            self._headers = event.headers
            self._headers_waiter.set()
            if event.end_stream:
                self._receive_feeder.close()
        elif isinstance(event, DataReceived):
            assert self._headers is not None
            self._receive_feeder.send_nowait(event.data)
            if event.end_stream:
                self._receive_feeder.close()
        elif isinstance(event, (ConnectionTerminated, StreamReset)):
            self._terminate()

    def _terminate(self) -> None:
        self._terminated = True
        self._headers_waiter.set()
        self._receive_feeder.close()


class HTTPConnectionContext:

    _connection: HTTPConnection
    _streams: dict[int, HTTPStream]

    def __init__(self, connection: HTTPConnection) -> None:
        self._connection = connection
        self._streams = {}

    @property
    def connection(self) -> HTTPConnection:
        return self._connection

    def add_stream(self) -> HTTPStream:
        stream_id = self._connection.get_available_stream_id()
        stream = self._streams[stream_id] = HTTPStream(self._connection, stream_id)
        return stream

    def handle_event(self, event: Event) -> None:
        # TODO: remove closed stream from self._streams
        if isinstance(event, StreamEvent):
            self._streams[event.stream_id].handle_event(event)
        else:
            for stream in self._streams.values():
                stream.handle_event(event)


class HTTPPool:
    """
    Maintains a pool of connections to one origin.
    """

    _address: AddressType
    _tls: bool
    _http_opener: HTTPOpener
    _task_group: TaskGroup

    _connections: set[HTTPConnectionContext]
    _lock: anyio.Lock

    def __init__(
        self,
        address: AddressType,
        tls: bool,
        *,
        http_opener: HTTPOpener,
        task_group: TaskGroup,
    ) -> None:
        self._address = address
        self._tls = tls
        self._http_opener = http_opener
        self._task_group = task_group
        self._connections = set()
        self._lock = anyio.Lock()

    async def aclose(self) -> None:
        # Use list() to copy connections before iterating to avoid
        # "RuntimeError: Set changed size during iteration"
        # when a closed connection is removed from the set.
        for context in list(self._connections):
            await context.connection.aclose()

    async def open_stream(
        self, headers: HeadersType, end_stream: bool = False
    ) -> HTTPStream:
        async with self._lock:
            context = await self._obtain_connection()
            stream = context.add_stream()
            await stream.send_headers(headers, end_stream)
        return stream

    async def _obtain_connection(self) -> HTTPConnectionContext:
        for context in self._connections:
            if context.connection.is_available():
                return context
        return await self._start_connection()

    async def _start_connection(self) -> HTTPConnectionContext:
        context = await self._task_group.start(self._run_connection)
        assert isinstance(context, HTTPConnectionContext)
        self._connections.add(context)
        return context

    async def _run_connection(self, *, task_status: TaskStatus) -> None:
        connection = await self._http_opener(self._address, tls=self._tls)
        context = HTTPConnectionContext(connection)
        async with context.connection:
            task_status.started(context)
            while True:
                event = await context.connection.receive_event()
                context.handle_event(event)
                if isinstance(event, ConnectionTerminated):
                    break
        self._connections.remove(context)
