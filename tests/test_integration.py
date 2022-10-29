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

from typing import Iterator

import pytest
from helpers import build_request_headers, build_response_headers

from hface.events import (
    ConnectionTerminated,
    DataReceived,
    Event,
    HeadersReceived,
    StreamResetReceived,
)
from hface.protocols import HTTPOverTCPProtocol, protocol_registry


def _generate_http1_combinations() -> Iterator[
    tuple[str, tuple[HTTPOverTCPProtocol, HTTPOverTCPProtocol]]
]:
    for client_name, client_factory in protocol_registry.http1_clients.items():
        for server_name, server_factory in protocol_registry.http1_servers.items():
            client = client_factory(tls_version="TLS 1.2")
            server = server_factory(tls_version="TLS 1.2")
            yield f"http1-{client_name}-{server_name}", (client, server)


def _generate_http2_combinations() -> Iterator[
    tuple[str, tuple[HTTPOverTCPProtocol, HTTPOverTCPProtocol]]
]:
    for client_name, client_factory in protocol_registry.http2_clients.items():
        for server_name, server_factory in protocol_registry.http2_servers.items():
            client = client_factory(tls_version="TLS 1.2", alpn_protocol="h2")
            server = server_factory(tls_version="TLS 1.2", alpn_protocol="h2")
            yield f"http2-{client_name}-{server_name}", (client, server)


def pytest_generate_tests(metafunc: pytest.Metafunc) -> None:
    if "client" in metafunc.fixturenames or "server" in metafunc.fixturenames:
        ids = []
        values = []
        for id, value in _generate_http1_combinations():
            ids.append(id)
            values.append(value)
        for id, value in _generate_http2_combinations():
            ids.append(id)
            values.append(value)
        metafunc.parametrize(("client", "server"), values, ids=ids)


def xfer(source: HTTPOverTCPProtocol, target: HTTPOverTCPProtocol) -> list[Event]:
    data = source.bytes_to_send()
    if data:
        target.bytes_received(data)
    if source.has_expired():
        target.connection_lost()
    return list(iter(target.next_event, None))


def init_connection(client: HTTPOverTCPProtocol, server: HTTPOverTCPProtocol) -> None:
    xfer(client, server)
    xfer(server, client)


def do_get_request(client: HTTPOverTCPProtocol, server: HTTPOverTCPProtocol) -> int:
    request_headers = build_request_headers(method=b"GET")
    stream_id = client.get_available_stream_id()
    client.submit_headers(stream_id, request_headers, end_stream=True)
    assert xfer(client, server) == [
        HeadersReceived(stream_id, request_headers, end_stream=True),
    ]
    return stream_id


def do_post_request(client: HTTPOverTCPProtocol, server: HTTPOverTCPProtocol) -> int:
    request_headers = build_request_headers((b"content-length", b"11"), method=b"POST")
    stream_id = client.get_available_stream_id()
    client.submit_headers(stream_id, request_headers)
    client.submit_data(stream_id=stream_id, data=b"Hello HTTP!", end_stream=True)
    assert xfer(client, server) == [
        HeadersReceived(stream_id, request_headers),
        DataReceived(stream_id=1, data=b"Hello HTTP!", end_stream=True),
    ]
    return stream_id


def do_response(
    client: HTTPOverTCPProtocol, server: HTTPOverTCPProtocol, stream_id: int
) -> None:
    response_headers = build_response_headers((b"content-length", b"11"))
    server.submit_headers(stream_id, response_headers)
    server.submit_data(stream_id=stream_id, data=b"Hello HTTP!", end_stream=True)
    assert xfer(server, client) == [
        HeadersReceived(stream_id, response_headers),
        DataReceived(stream_id, b"Hello HTTP!", end_stream=True),
    ]


class TestIntegration:
    def test_get(
        self, client: HTTPOverTCPProtocol, server: HTTPOverTCPProtocol
    ) -> None:
        init_connection(client, server)
        stream_id = do_get_request(client, server)
        do_response(client, server, stream_id)

    def test_post(
        self, client: HTTPOverTCPProtocol, server: HTTPOverTCPProtocol
    ) -> None:
        init_connection(client, server)
        stream_id = do_post_request(client, server)
        do_response(client, server, stream_id)

    def test_serial(
        self, client: HTTPOverTCPProtocol, server: HTTPOverTCPProtocol
    ) -> None:
        init_connection(client, server)
        stream_id = do_get_request(client, server)
        do_response(client, server, stream_id)
        stream_id = do_get_request(client, server)
        do_response(client, server, stream_id)

    def test_parallel(
        self, client: HTTPOverTCPProtocol, server: HTTPOverTCPProtocol
    ) -> None:
        init_connection(client, server)
        if not (client.multiplexed and server.multiplexed):
            return
        stream_id_a = do_get_request(client, server)
        stream_id_b = do_get_request(client, server)
        do_response(client, server, stream_id_b)
        do_response(client, server, stream_id_a)

    def test_client_stream_rst(
        self, client: HTTPOverTCPProtocol, server: HTTPOverTCPProtocol
    ) -> None:
        init_connection(client, server)
        stream_id = client.get_available_stream_id()
        client.submit_headers(stream_id, build_request_headers(), end_stream=True)
        xfer(client, server)
        client.submit_stream_reset(stream_id)
        if not client.multiplexed:
            assert xfer(client, server) == [ConnectionTerminated()]
        else:
            assert xfer(client, server) == [StreamResetReceived(stream_id)]

    def test_server_stream_rst(
        self, client: HTTPOverTCPProtocol, server: HTTPOverTCPProtocol
    ) -> None:
        init_connection(client, server)
        stream_id = do_get_request(client, server)
        server.submit_stream_reset(stream_id)
        if not server.multiplexed:
            assert xfer(server, client) == [ConnectionTerminated()]
        else:
            assert xfer(server, client) == [StreamResetReceived(stream_id)]
