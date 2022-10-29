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

"""
QUIC server support

This module provides foundations for running a server listening
for HTTP/3 connection. This is not needed for HTTP/3 clients
because hface HTTP3 abstraction is designed as HTTP-over-UDP,
hiding the QUIC in the middle (submit HTTP events to get
UDP datagrams, feed UDP datagrams to get HTTP events).

The only place where this abstraction is not sufficient
is an HTTP/3 server. The problem is that HTTP/3 connections
have to share one UDP socket (reusing one UDP port),
so something has to route datagrams based on QUIC connection IDs.

"""

from __future__ import annotations

from contextlib import AsyncExitStack
from math import inf
from typing import Any, AsyncContextManager, Callable, Coroutine, Mapping, Sequence

import anyio
from anyio.abc import Listener, SocketAttribute, TaskGroup
from anyio.streams.memory import MemoryObjectReceiveStream, MemoryObjectSendStream

from hface import AddressType, DatagramType
from hface.protocols.http3 import InvalidPacket, sniff_packet

from ._typing import DatagramStream, QUICStream

DatagramFeederType = MemoryObjectSendStream[DatagramType]
DatagramQueueType = MemoryObjectReceiveStream[DatagramType]


class QUICRouter:
    """
    Routes UDP datagrams based on QUIC connection IDs.
    """

    _receive_feeders: dict[bytes, DatagramFeederType]

    def __init__(self) -> None:
        self._receive_feeders = {}

    def subscribe(self, connection_id: bytes, feeder: DatagramFeederType) -> None:
        assert connection_id not in self._receive_feeders
        self._receive_feeders[connection_id] = feeder

    def unsubscribe(self, connection_id: bytes) -> None:
        self._receive_feeders.pop(connection_id, None)

    def route(self, connection_id: bytes, datagram: DatagramType) -> bool:
        feeder = self._receive_feeders.get(connection_id)
        if feeder is None:
            return False
        # TODO: handle anyio.WouldBlock
        feeder.send_nowait(datagram)
        return True


class QUICListenerStream(QUICStream):

    _socket: DatagramStream
    _router: QUICRouter
    _receive_feeder: DatagramFeederType
    _receive_queue: DatagramQueueType
    _remote_address: AddressType
    _send_lock: anyio.Lock

    _connection_ids: frozenset[bytes]

    def __init__(
        self,
        *,
        socket: DatagramStream,
        router: QUICRouter,
        receive_feeder: DatagramFeederType,
        receive_queue: DatagramQueueType,
        remote_address: AddressType,
        send_lock: anyio.Lock,
    ):
        self._socket = socket
        self._router = router
        self._receive_feeder = receive_feeder
        self._receive_queue = receive_queue
        self._remote_address = remote_address
        self._send_lock = send_lock
        self._connection_ids = frozenset()

    def update_connection_ids(self, connection_ids: Sequence[bytes]) -> None:
        prev_connection_ids = self._connection_ids
        self._connection_ids = frozenset(connection_ids)
        for connection_id in prev_connection_ids - self._connection_ids:
            self._router.unsubscribe(connection_id)
        for connection_id in self._connection_ids - prev_connection_ids:
            self._router.subscribe(connection_id, self._receive_feeder)

    async def aclose(self) -> None:
        self._receive_feeder.close()
        self._receive_queue.close()
        self.update_connection_ids([])

    async def receive(self) -> DatagramType:
        return await self._receive_queue.receive()

    async def send(self, item: DatagramType) -> None:
        async with self._send_lock:
            await self._socket.send(item)

    @property
    def extra_attributes(self) -> Mapping[Any, Callable[[], Any]]:
        """
        Implements :class:`anyio.TypedAttributeProvider`.
        """
        return {
            **self._socket.extra_attributes,
            SocketAttribute.remote_address: lambda: self._remote_address,
            SocketAttribute.remote_port: lambda: self._remote_address[1],
        }


class QUICListener(Listener[QUICStream]):
    """
    A listener that accepts QUIC connections.
    """

    _socket: DatagramStream

    _router: QUICRouter
    _send_lock: anyio.Lock

    _receive_buffer_size: float = inf

    _quic_connection_id_length: int
    _quic_supported_versions: list[int]

    def __init__(
        self,
        socket: DatagramStream,
        *,
        quic_connection_id_length: int,
        quic_supported_versions: Sequence[int],
    ) -> None:
        self._socket = socket
        self._quic_connection_id_length = quic_connection_id_length
        self._quic_supported_versions = list(quic_supported_versions)
        self._router = QUICRouter()
        self._send_lock = anyio.Lock()

    async def aclose(self) -> None:
        await self._socket.aclose()

    async def serve(
        self,
        handler: Callable[[QUICStream], Coroutine[Any, Any, Any]],
        task_group: TaskGroup | None = None,
    ) -> None:
        context_manager: AsyncContextManager[object]
        if task_group is None:
            task_group = context_manager = anyio.create_task_group()
        else:
            context_manager = AsyncExitStack()
        async with context_manager:
            while True:
                datagram = await self._socket.receive()
                try:
                    packet_info = sniff_packet(
                        datagram[0],
                        connection_id_length=self._quic_connection_id_length,
                    )
                except InvalidPacket:
                    continue
                connection_id = packet_info.destination_connection_id
                if self._router.route(connection_id, datagram):
                    pass  # Routed to an existing connection.
                elif packet_info.is_initial_packet:
                    if packet_info.version not in self._quic_supported_versions:
                        # TODO: Version negotiation. Today, we ignore unknown versions.
                        continue
                    socket = self._create_quic_socket(datagram)
                    socket.update_connection_ids([connection_id])
                    task_group.start_soon(handler, socket)

    def _create_quic_socket(self, datagram: DatagramType) -> QUICStream:
        receive_feeder, receive_queue = anyio.create_memory_object_stream(
            max_buffer_size=self._receive_buffer_size,
        )
        receive_feeder.send_nowait(datagram)
        return QUICListenerStream(
            socket=self._socket,
            router=self._router,
            receive_feeder=receive_feeder,
            receive_queue=receive_queue,
            remote_address=datagram[1],
            send_lock=self._send_lock,
        )
