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
from contextlib import asynccontextmanager
from typing import Any, AsyncContextManager, AsyncIterator, Callable, Mapping

import anyio
from anyio.abc import SocketAttribute

from hface import AddressType
from hface.networking import ByteStream, DatagramStream, QUICStream
from hface.protocols import HTTPOverQUICProtocol, HTTPOverTCPProtocol, HTTPProtocol


class Transport(anyio.TypedAttributeProvider, metaclass=ABCMeta):
    @property
    @abstractmethod
    def protocol(self) -> HTTPProtocol:
        raise NotImplementedError

    @abstractmethod
    async def aclose(self) -> None:
        raise NotImplementedError

    @abstractmethod
    async def receive(self) -> None:
        raise NotImplementedError

    @abstractmethod
    def send_context(self) -> AsyncContextManager[None]:
        raise NotImplementedError


class TCPTransport(Transport):

    _protocol: HTTPOverTCPProtocol
    _socket: ByteStream

    _send_lock: anyio.Lock

    def __init__(self, protocol: HTTPOverTCPProtocol, socket: ByteStream) -> None:
        self._protocol = protocol
        self._socket = socket
        self._send_lock = anyio.Lock()

    @property
    def extra_attributes(self) -> Mapping[Any, Callable[[], Any]]:
        return self._socket.extra_attributes

    @property
    def protocol(self) -> HTTPOverTCPProtocol:
        return self._protocol

    async def aclose(self) -> None:
        await self._socket.aclose()

    async def receive(self) -> None:
        try:
            data = await self._socket.receive()
        except anyio.EndOfStream:
            async with self.send_context():
                self._protocol.eof_received()
        except (anyio.BrokenResourceError, anyio.ClosedResourceError):
            self._protocol.connection_lost()
        else:
            async with self.send_context():
                self._protocol.bytes_received(data)

    @asynccontextmanager
    async def send_context(self) -> AsyncIterator[None]:
        async with self._send_lock:
            yield
            payload = self._protocol.bytes_to_send()
            if payload:
                await self._socket.send(payload)


class UDPTransport(Transport):

    _protocol: HTTPOverQUICProtocol
    _socket: DatagramStream
    _remote_address: AddressType | None

    _send_lock: anyio.Lock

    def __init__(
        self,
        protocol: HTTPOverQUICProtocol,
        socket: DatagramStream,
        *,
        remote_address: AddressType | None = None,
    ) -> None:
        self._protocol = protocol
        self._socket = socket
        self._remote_address = remote_address
        self._send_lock = anyio.Lock()

    @property
    def extra_attributes(self) -> Mapping[Any, Callable[[], Any]]:
        rv: dict[Any, Callable[[], Any]] = dict(self._socket.extra_attributes)
        if self._remote_address is not None:
            rv[SocketAttribute.remote_address] = lambda: self._remote_address
        return rv

    @property
    def protocol(self) -> HTTPOverQUICProtocol:
        return self._protocol

    async def aclose(self) -> None:
        await self._socket.aclose()

    async def receive(self) -> None:
        try:
            self._protocol.clock(anyio.current_time())
            with anyio.fail_after(self._get_timeout()):
                datagram = await self._socket.receive()
        except TimeoutError:
            async with self.send_context():
                pass
        except (anyio.BrokenResourceError, anyio.ClosedResourceError):
            self._protocol.connection_lost()
        else:
            async with self.send_context():
                self._protocol.datagram_received(datagram)

    @asynccontextmanager
    async def send_context(self) -> AsyncIterator[None]:
        async with self._send_lock:
            self._protocol.clock(anyio.current_time())
            yield
            for datagram in self._protocol.datagrams_to_send():
                await self._socket.send(datagram)
        self._update_connection_ids()

    def _get_timeout(self) -> float | None:
        timer = self._protocol.get_timer()
        if timer is None:
            return None
        return timer - anyio.current_time()

    def _update_connection_ids(self) -> None:
        if not isinstance(self._socket, QUICStream):
            return
        self._socket.update_connection_ids(self.protocol.connection_ids)
