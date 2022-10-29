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
import traceback
from math import inf

import anyio
from anyio.abc import TaskGroup
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

from ._asgi import (
    ASGIAppType,
    ASGIError,
    ASGIMessageType,
    asgi_message_to_data,
    asgi_message_to_headers,
    data_to_asgi_message,
    headers_to_asgi_scope,
    reset_to_asgi_message,
)
from ._base import BaseServer

logger = logging.getLogger("hface.server")


class StreamController:
    """
    Maintains one HTTP stream, handling one HTTP request.
    """

    _connection: HTTPConnection
    _connection_id: int
    _stream_id: int
    _app: ASGIAppType
    _app_tasks: TaskGroup

    _receive_feeder: MemoryObjectSendStream[ASGIMessageType]
    _receive_queue: MemoryObjectReceiveStream[ASGIMessageType]

    _response_headers: HeadersType | None = None
    _response_headers_sent: bool = False
    _response_end_stream_sent: bool = False

    # Infinite buffer is not ideal, but size of stream buffers should be
    # bounded by HTTP Flow Control -- when we implement it ;)

    _max_receive_buffer_size: float = inf

    def __init__(
        self,
        *,
        connection: HTTPConnection,
        connection_id: int,
        stream_id: int,
        app: ASGIAppType,
        app_tasks: TaskGroup,
    ) -> None:
        self._connection = connection
        self._connection_id = connection_id
        self._stream_id = stream_id
        self._app = app
        self._app_tasks = app_tasks
        self._receive_feeder, self._receive_queue = anyio.create_memory_object_stream(
            max_buffer_size=self._max_receive_buffer_size,
        )

    def handle_event(self, event: Event) -> None:
        if isinstance(event, HeadersReceived):
            self._start_app(event.headers)
            if event.end_stream:
                message = data_to_asgi_message(b"", event.end_stream)
                self._receive_feeder.send_nowait(message)
        elif isinstance(event, DataReceived):
            message = data_to_asgi_message(event.data, event.end_stream)
            self._receive_feeder.send_nowait(message)
        elif isinstance(event, (ConnectionTerminated, StreamReset)):
            message = reset_to_asgi_message()
            self._receive_feeder.send_nowait(message)

    def _start_app(self, headers: HeadersType) -> None:
        scope = headers_to_asgi_scope(
            headers,
            server_address=self._connection.local_address,
            client_address=self._connection.remote_address,
            http_version=self._connection.http_version,
        )
        self._app_tasks.start_soon(self._run_app, scope)

    async def _run_app(self, scope: ASGIMessageType) -> None:
        logger.info(
            f"Stream #{self._connection_id}-{self._stream_id}: "
            f"ASGI application will run."
        )
        try:
            await self._app(scope, self._asgi_receive, self._asgi_send)
            if not self._response_headers_sent:
                raise ASGIError("ASGI application finished without sending a response.")
            if not self._response_end_stream_sent:
                raise ASGIError("ASGI application finished without closing a response.")
        except ASGIError as exc:
            # ApplicationError is thrown by us when the application misbehaves.
            # It bubbles from ASGI receive or send callback back to us.
            logger.exception(
                f"Stream #{self._connection_id}-{self._stream_id}: "
                "ASGI application misbehaved:"
            )
            await self._send_error(exc, show_tb=False)
        except Exception as exc:
            logger.exception(
                f"Stream #{self._connection_id}-{self._stream_id}: "
                "ASGI application thrown an unhandled exception:"
            )
            await self._send_error(exc)
        else:
            logger.info(
                f"Stream #{self._connection_id}-{self._stream_id}: "
                f"ASGI application successfully finished."
            )

    async def _asgi_receive(self) -> ASGIMessageType:
        """
        Receive callback passed to an ASGI app.
        """
        event = await self._receive_queue.receive()
        logger.debug(f"ASGI {event['type']!r} received by the app.")
        return event

    async def _asgi_send(self, event: ASGIMessageType) -> None:
        """
        Send callback passed to an ASGI app.
        """
        logger.debug(f"ASGI {event['type']!r} sent by the app.")
        if event["type"] == "http.response.start":
            await self._asgi_send_start(event)
        elif event["type"] == "http.response.body":
            await self._asgi_send_body(event)
        else:
            raise ASGIError(f"ASGI event not supported: {event['type']!r}")

    async def _asgi_send_start(self, event: ASGIMessageType) -> None:
        """
        Handle 'http.response.start' from an ASGI app.
        """
        if self._response_headers is not None or self._response_headers_sent:
            raise ASGIError("ASGI 'http.response.start' sent more than once.")
        # Delay headers. From ASGI specs:
        # > The protocol server must not start sending the response to the client
        # > until it has received at least one Response Body event.
        self._response_headers = asgi_message_to_headers(event)

    async def _asgi_send_body(self, event: ASGIMessageType) -> None:
        """
        Handle 'http.response.body' from an ASGI app.
        """
        if self._response_end_stream_sent:
            # Ignore events after more_body=False. From ASGI spec:
            # > more_body: ... If False, response will be taken as complete and closed,
            # > and any further messages on the channel will be ignored.
            logger.warning("ASGI 'http.response.body' for a closed response.")
            return
        data, end_stream = asgi_message_to_data(event)
        if not self._response_headers_sent:
            # Headers are flushed with the first body event.
            # See a comment in _asgi_send_start() with a snippet from ASGI specs.
            if self._response_headers is None:
                raise ASGIError(
                    "ASGI 'http.response.body' before 'http.response.start'."
                )
            # If we got no data and we know that we will not get more,
            # we can close the stream with the headers (and possibly save one frame).
            headers_end_stream = end_stream and not data
            await self._connection.send_headers(
                self._stream_id,
                self._response_headers,
                end_stream=headers_end_stream,
            )
            self._response_headers = None
            self._response_headers_sent = True
            self._response_end_stream_sent = headers_end_stream
        if data or (end_stream and not self._response_end_stream_sent):
            await self._connection.send_data(self._stream_id, data, end_stream)
        self._response_end_stream_sent = end_stream

    async def _send_error(self, exc: Exception, show_tb: bool = True) -> None:
        if self._response_end_stream_sent:
            # We got error after a complete response was sent.
            # This will get logged, but a client will not notice anything.
            return
        if self._response_headers_sent:
            # If headers were sent, there is not much to do, so we reset the stream.
            # Browsers either get stuck loading, or say that the page is not available.
            error_code = self._connection.error_codes.internal_error
            await self._connection.send_stream_reset(self._stream_id, error_code)
            return
        # If headers were not sent, we can send the exception.
        # This could be a terrible idea in production, but this server
        # is intended for development or testing.
        if show_tb:
            tb = exc.__traceback__.tb_next if exc.__traceback__ else None
        else:
            tb = None
        lines = traceback.format_exception(type(exc), exc, tb)
        content = "\r\n".join(lines).encode()
        headers = [
            (b":status", b"500"),
            (b"content-type", b"text/plain"),
            (b"content-length", str(len(content)).encode()),
        ]
        await self._connection.send_headers(self._stream_id, headers)
        await self._connection.send_data(self._stream_id, content, end_stream=True)


class ConnectionController:
    """
    Maintains one HTTP connections, possibly consisting of multiple streams.
    """

    _connection: HTTPConnection
    _app: ASGIAppType
    _app_tasks: TaskGroup
    _connection_id: int

    _streams: dict[int, StreamController]
    _terminated: bool = False

    def __init__(
        self,
        *,
        connection: HTTPConnection,
        connection_id: int,
        app: ASGIAppType,
        app_tasks: TaskGroup,
    ) -> None:
        self._connection = connection
        self._app = app
        self._app_tasks = app_tasks
        self._connection_id = connection_id
        self._streams = {}

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
                app=self._app,
                app_tasks=self._app_tasks,
            )
        self._streams[event.stream_id].handle_event(event)

    def _handle_connection_event(self, event: Event) -> None:
        if isinstance(event, ConnectionTerminated):
            self._terminated = True
        for controller in self._streams.values():
            controller.handle_event(event)


class ASGIServer(BaseServer):
    """
    HTTP server with an ASGI application
    """

    _app: ASGIAppType
    _connection_counter: int = 0

    def __init__(self, app: ASGIAppType) -> None:
        """
        :param app: ASGI application
        """
        super().__init__()
        self._app = app

    async def handle_connection(self, connection: HTTPConnection) -> None:
        async with connection:
            async with anyio.create_task_group() as app_tasks:
                self._connection_counter += 1
                controller = ConnectionController(
                    connection=connection,
                    connection_id=self._connection_counter,
                    app_tasks=app_tasks,
                    app=self._app,
                )
                await controller.run()
