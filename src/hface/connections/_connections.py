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
from types import TracebackType
from typing import Any, Callable, Mapping, Type

import anyio
from anyio.abc import AsyncResource, SocketAttribute

from hface import AddressType, HeadersType, HTTPErrorCodes
from hface.events import Event

from ._transports import Transport

logger = logging.getLogger("hface.connections")


def _get_remote_address(socket: anyio.TypedAttributeProvider) -> AddressType:
    remote_address = socket.extra(SocketAttribute.remote_address, ("", 0))
    assert isinstance(remote_address, tuple)
    return remote_address


def _get_local_address(socket: anyio.TypedAttributeProvider) -> AddressType:
    local_address = socket.extra(SocketAttribute.local_address, ("", 0))
    assert isinstance(local_address, tuple)
    return local_address


class HTTPConnection(AsyncResource, anyio.TypedAttributeProvider):
    """
    An HTTP connection

    This class unifies access to all HTTP connections.
    Internally, it combines Sans-IO :class:`.HTTPProtocol` with a network stream.
    The former allows to swap HTTP versions and implementations,
    the latter allows to proxy traffic or use alternative IO.

    This class should not be initialized directly (at least for now).
    It is returned from :class:`.HTTPListener` or :class:`.HTTPOpener` implementations.

    :param transport: not a part of public API
    """

    _transport: Transport
    _local_address: AddressType
    _remote_address: AddressType

    _opened: bool = False
    _closed: bool = False

    def __init__(self, transport: Transport) -> None:
        self._transport = transport
        self._local_address = _get_local_address(self._transport)
        self._remote_address = _get_remote_address(self._transport)

    async def __aenter__(self) -> HTTPConnection:
        """
        Calls :meth:`.open` when this class is used as an async context manager.

        :return: self
        """
        await self.open()
        return self

    async def __aexit__(
        self,
        exc_type: Type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        """
        Calls :meth:`.aclose` when this class is used as an async context manager.
        """
        await self.aclose()

    @property
    def http_version(self) -> str:
        """
        An HTTP version as a string.
        """
        return self._transport.protocol.http_version

    @property
    def multiplexed(self) -> bool:
        """
        Whether this connection supports multiple parallel streams.

        Returns ``True`` for HTTP/2 and HTTP/3 connections.
        """
        return self._transport.protocol.multiplexed

    @property
    def local_address(self) -> AddressType:
        """
        Local network address

        The address is intended for logging and/or troubleshooting.
        """
        return self._local_address

    @property
    def remote_address(self) -> AddressType:
        """
        Remote network address

        The address is intended for logging and/or troubleshooting.
        """
        return self._remote_address

    @property
    def error_codes(self) -> HTTPErrorCodes:
        """
        Error codes suitable for this HTTP connection.

        The error codes can be used :meth:`.send_stream_reset`
        """
        return self._transport.protocol.error_codes

    @property
    def extra_attributes(self) -> Mapping[Any, Callable[[], Any]]:
        """
        Implements :class:`anyio.TypedAttributeProvider`

        This method returns attributes from an underlying network stream.
        """
        return self._transport.extra_attributes

    def is_available(self) -> bool:
        """
        Return whether this connection is capable to open new streams.
        """
        return self._transport.protocol.is_available()

    def has_expired(self) -> bool:
        """
        Return whether this connection is closed or should be closed.
        """
        return self._transport.protocol.has_expired()

    async def open(self) -> None:
        """
        Sends protocol preamble if needed.
        """
        if self._opened:
            return
        self._opened = True
        async with self._transport.send_context():
            pass
        logger.info(
            f"Opened HTTP/{self.http_version} connection: "
            f"local_address={self.local_address}, "
            f"remote_address={self.remote_address}"
        )

    async def aclose(self) -> None:
        """
        Close this connection.
        """
        if self._closed:
            return
        self._closed = True
        async with self._transport.send_context():
            self._transport.protocol.submit_close()
        await self._transport.aclose()
        logger.info(
            f"Closed HTTP/{self.http_version} connection: "
            f"local_address={self.local_address}, "
            f"remote_address={self.remote_address}"
        )

    def get_available_stream_id(self) -> int:
        """
        Return an ID that can be used to create a new stream.

        Use the returned ID with :meth:`.send_headers` to create the stream.
        This method may or may not return one value until that method is called.

        :return: stream ID
        """
        return self._transport.protocol.get_available_stream_id()

    async def send_headers(
        self, stream_id: int, headers: HeadersType, end_stream: bool = False
    ) -> None:
        """
        Send a frame with HTTP headers.

        If this is a client connection, this method starts an HTTP request.
        If this is a server connection, it starts an HTTP response.

        :param stream_id: stream ID
        :param headers: HTTP headers
        :param end_stream: whether to close the stream for sending
        """
        async with self._transport.send_context():
            self._transport.protocol.submit_headers(stream_id, headers, end_stream)
        logger.debug(
            f"Sent HTTP headers: stream_id={stream_id!r}, "
            f"len(headers)={len(headers)}, end_stream={end_stream!r}"
        )

    async def send_data(
        self, stream_id: int, data: bytes, end_stream: bool = False
    ) -> None:
        """
        Send a frame with HTTP data.

        :param stream_id: stream ID
        :param data: payload
        :param end_stream: whether to close the stream for sending
        """
        async with self._transport.send_context():
            self._transport.protocol.submit_data(stream_id, data, end_stream)
        logger.debug(
            f"Sent HTTP data: stream_id={stream_id!r}, "
            f"len(data)={len(data)}, end_stream={end_stream!r}"
        )

    async def send_stream_reset(self, stream_id: int, error_code: int = 0) -> None:
        """
        Immediately terminate a stream.

        Stream reset is used to request cancellation of a stream
        or to indicate that an error condition has occurred.

        Use :attr:`.error_codes` to obtain error codes for common problems.

        :param stream_id: stream ID
        :param error_code:  indicates why the stream is being terminated
        """
        async with self._transport.send_context():
            self._transport.protocol.submit_stream_reset(stream_id, error_code)
        logger.debug(
            f"Sent stream reset: stream_id={stream_id!r}, error_code={error_code!r}"
        )

    async def receive_event(self) -> Event:
        """
        Receive next HTTP event.

        :return: an event instance
        """
        while True:
            event = self._transport.protocol.next_event()
            if event is not None:
                break
            await self._transport.receive()
        logger.debug(f"Received HTTP event: {event}")
        return event
