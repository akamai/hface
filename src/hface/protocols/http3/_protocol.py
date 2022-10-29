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

from collections import deque
from typing import Iterable, Sequence

import aioquic.h3.connection
import aioquic.h3.events
import aioquic.quic.configuration
import aioquic.quic.connection
import aioquic.quic.events

from hface import AddressType, DatagramType, HeadersType
from hface.events import (
    ConnectionTerminated,
    DataReceived,
    Event,
    HeadersReceived,
    StreamResetReceived,
)
from hface.protocols import HTTP3Protocol

from ._quic import sniff_packet


class HTTP3ProtocolImpl(HTTP3Protocol):

    _configuration: aioquic.quic.configuration.QuicConfiguration

    # H3Connection and QuicConnection are initialized lazily.
    #
    # For server connections, we wait for original_destination_connection_id
    # from the first packet. Also, QuicConnection.datagrams_to_send()
    # raises exceptions until that first packet.
    #
    # For client connections, we have to delay QuicConnection.connect()
    # util the internal clock are set.

    _quic: aioquic.quic.connection.QuicConnection | None = None
    _http: aioquic.h3.connection.H3Connection | None = None

    _now: float | None = None

    _connection_ids: set[bytes]

    _event_buffer: deque[Event]
    _terminated: bool = False

    def __init__(
        self,
        configuration: aioquic.quic.configuration.QuicConfiguration,
        *,
        remote_address: AddressType | None = None,
    ) -> None:
        if configuration.is_client and remote_address is None:
            raise ValueError("remote_address is required for client connections.")
        self._configuration = configuration
        self._connection_ids = set()
        self._remote_address = remote_address
        self._event_buffer = deque()

    def is_available(self) -> bool:
        # TODO: check concurrent stream limit
        return not self._terminated

    def has_expired(self) -> bool:
        # TODO: check that we do not run out of stream IDs.
        return self._terminated

    def get_available_stream_id(self) -> int:
        return self._require_quic().get_next_available_stream_id()

    def submit_close(self, error_code: int = 0) -> None:
        # QUIC has two different frame types for closing the connection.
        # From RFC 9000 (QUIC: A UDP-Based Multiplexed and Secure Transport):
        #
        # > An endpoint sends a CONNECTION_CLOSE frame (type=0x1c or 0x1d)
        # > to notify its peer that the connection is being closed.
        # > The CONNECTION_CLOSE frame with a type of 0x1c is used to signal errors
        # > at only the QUIC layer, or the absence of errors (with the NO_ERROR code).
        # > The CONNECTION_CLOSE frame with a type of 0x1d is used
        # > to signal an error with the application that uses QUIC.
        frame_type = 0x1D if error_code else 0x1C
        self._require_quic().close(error_code=error_code, frame_type=frame_type)

    def submit_headers(
        self, stream_id: int, headers: HeadersType, end_stream: bool = False
    ) -> None:
        self._require_http().send_headers(stream_id, list(headers), end_stream)

    def submit_data(
        self, stream_id: int, data: bytes, end_stream: bool = False
    ) -> None:
        self._require_http().send_data(stream_id, data, end_stream)

    def submit_stream_reset(self, stream_id: int, error_code: int = 0) -> None:
        self._require_quic().reset_stream(stream_id, error_code)

    def next_event(self) -> Event | None:
        if not self._event_buffer:
            return None
        return self._event_buffer.popleft()

    @property
    def connection_ids(self) -> Sequence[bytes]:
        return list(self._connection_ids)

    def clock(self, now: float) -> None:
        self._now = now
        if self._quic is None:
            return
        timer = self._quic.get_timer()
        if timer is not None and now >= timer:
            self._quic.handle_timer(now)
            self._fetch_events()

    def get_timer(self) -> float | None:
        if self._quic is None:
            return None
        return self._quic.get_timer()

    def connection_lost(self) -> None:
        self._terminated = True
        self._event_buffer.append(ConnectionTerminated())

    def datagram_received(self, datagram: DatagramType) -> None:
        data, address = datagram
        if self._quic is None and not self._configuration.is_client:
            # For server, we initialize the QUIC connection when the first
            # packet is received. That is necessary because aioquic
            # QuicConnection requires original_destination_connection_id.
            self._quic = self._server_connect(data)
        self._require_quic().receive_datagram(data, address, self._require_now())
        self._fetch_events()

    def datagrams_to_send(self) -> Sequence[tuple[bytes, AddressType]]:
        if self._quic is None and not self._configuration.is_client:
            # No packet was received yet.
            return []
        return self._require_quic().datagrams_to_send(self._require_now())

    def _fetch_events(self) -> None:
        quic = self._require_quic()
        http = self._require_http()
        for quic_event in iter(quic.next_event, None):
            self._event_buffer += self._map_quic_event(quic_event)
            for h3_event in http.handle_event(quic_event):
                self._event_buffer += self._map_h3_event(h3_event)

    def _map_quic_event(
        self, quic_event: aioquic.quic.events.QuicEvent
    ) -> Iterable[Event]:
        if isinstance(quic_event, aioquic.quic.events.ConnectionIdIssued):
            self._connection_ids.add(quic_event.connection_id)
        elif isinstance(quic_event, aioquic.quic.events.ConnectionIdRetired):
            self._connection_ids.remove(quic_event.connection_id)
        if isinstance(quic_event, aioquic.quic.events.HandshakeCompleted):
            pass
        elif isinstance(quic_event, aioquic.quic.events.ConnectionTerminated):
            self._terminated = True
            yield ConnectionTerminated(quic_event.error_code, quic_event.reason_phrase)
        elif isinstance(quic_event, aioquic.quic.events.StreamReset):
            yield StreamResetReceived(quic_event.stream_id, quic_event.error_code)

    def _map_h3_event(self, h3_event: aioquic.h3.events.H3Event) -> Iterable[Event]:
        if isinstance(h3_event, aioquic.h3.events.HeadersReceived):
            yield HeadersReceived(
                h3_event.stream_id, h3_event.headers, h3_event.stream_ended
            )
        elif isinstance(h3_event, aioquic.h3.events.DataReceived):
            yield DataReceived(h3_event.stream_id, h3_event.data, h3_event.stream_ended)

    def _require_http(self) -> aioquic.h3.connection.H3Connection:
        if self._http is None:
            self._http = aioquic.h3.connection.H3Connection(self._require_quic())
        return self._http

    def _require_quic(self) -> aioquic.quic.connection.QuicConnection:
        if self._quic is None:
            if self._configuration.is_client:
                # For clients, we initialize QUIC connection lazily, when first used.
                # By then, the clock should be set already.
                self._quic = self._client_connect()
            else:
                raise RuntimeError(
                    "QUIC connection has not been initialized yet. "
                    "Server connections are initialized when a first datagram "
                    "is received. It is an error to submit anything "
                    "before the first datagram from the client is received."
                )
        return self._quic

    def _require_now(self) -> float:
        if self._now is None:
            raise RuntimeError(
                "Clock has not been set. It is an error to call "
                "HTTP3Protocol methods without setting the clock first."
            )
        return self._now

    def _client_connect(self) -> aioquic.quic.connection.QuicConnection:
        assert self._remote_address is not None
        now = self._require_now()
        quic = aioquic.quic.connection.QuicConnection(configuration=self._configuration)
        quic.connect(self._remote_address, now)
        return quic

    def _server_connect(
        self, initial_data: bytes
    ) -> aioquic.quic.connection.QuicConnection:
        packet_info = sniff_packet(
            initial_data, connection_id_length=self._configuration.connection_id_length
        )
        quic = aioquic.quic.connection.QuicConnection(
            configuration=self._configuration,
            original_destination_connection_id=packet_info.destination_connection_id,
        )
        self._connection_ids.add(quic.original_destination_connection_id)
        self._connection_ids.add(quic.host_cid)
        return quic
