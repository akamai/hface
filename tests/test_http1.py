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

from typing import Any

import pytest
from helpers import build_request_headers, build_response_headers

from hface import HeadersType
from hface.events import ConnectionTerminated, DataReceived, HeadersReceived
from hface.protocols import HTTP1Protocol, protocol_registry


@pytest.fixture(name="client", params=protocol_registry.http1_clients.keys())
def _client(request: Any) -> HTTP1Protocol:
    factory = protocol_registry.http1_clients[request.param]
    protocol = factory(tls_version="TLS 1.2")
    assert isinstance(protocol, HTTP1Protocol)
    return protocol


@pytest.fixture(name="server", params=protocol_registry.http1_servers.keys())
def _server(request: Any) -> HTTP1Protocol:
    factory = protocol_registry.http1_servers[request.param]
    protocol = factory(tls_version="TLS 1.2")
    assert isinstance(protocol, HTTP1Protocol)
    return protocol


def assert_connection_available(protocol: HTTP1Protocol) -> None:
    assert protocol.next_event() is None
    assert protocol.bytes_to_send() == b""
    assert protocol.is_available()
    assert not protocol.has_expired()


def assert_connection_active(protocol: HTTP1Protocol) -> None:
    assert protocol.next_event() is None
    assert protocol.bytes_to_send() == b""
    assert not protocol.is_available()
    assert not protocol.has_expired()


def assert_connection_expired(protocol: HTTP1Protocol) -> None:
    assert protocol.next_event() is None
    assert protocol.bytes_to_send() == b""
    assert not protocol.is_available()
    assert protocol.has_expired()


class TestClient:
    def test_connection_made(self, client: HTTP1Protocol) -> None:
        """
        Test that no preface is sent for HTTP/1
        """
        assert_connection_available(client)

    def test_connection_lost(self, client: HTTP1Protocol) -> None:
        """
        Test connection lost without EOF before the first request.
        """
        client.connection_lost()
        assert client.next_event() == ConnectionTerminated()
        assert_connection_expired(client)

    def test_eof_received(self, client: HTTP1Protocol) -> None:
        """
        Test connection closed with EOF before the first request.
        """
        client.eof_received()
        assert client.next_event() == ConnectionTerminated()
        assert_connection_expired(client)
        client.connection_lost()
        assert_connection_expired(client)

    def test_send_get(self, client: HTTP1Protocol) -> None:
        """
        Test a GET request.
        """
        headers = build_request_headers()
        stream_id = client.get_available_stream_id()
        assert stream_id == 1
        client.submit_headers(stream_id, headers, end_stream=True)
        assert client.bytes_to_send() == b"GET / HTTP/1.1\r\nHost: example.com\r\n\r\n"
        assert client.bytes_to_send() == b""
        assert_connection_active(client)

    def test_send_post(self, client: HTTP1Protocol) -> None:
        """
        Test a POST request.
        """
        headers = build_request_headers((b"content-length", b"11"), method=b"POST")
        stream_id = client.get_available_stream_id()
        client.submit_headers(stream_id, headers)
        assert client.bytes_to_send() == (
            b"POST / HTTP/1.1\r\n"
            b"Host: example.com\r\n"
            b"Content-Length: 11\r\n"
            b"\r\n"
        )
        client.bytes_to_send()
        client.submit_data(stream_id, b"Hello HTTP!", end_stream=True)
        assert client.bytes_to_send() == b"Hello HTTP!"
        assert_connection_active(client)

    def test_send_post_at_once(self, client: HTTP1Protocol) -> None:
        """
        Test a POST request when headers are sent with data.
        """
        headers = build_request_headers((b"content-length", b"11"), method=b"POST")
        stream_id = client.get_available_stream_id()
        client.submit_headers(stream_id, headers)
        client.submit_data(stream_id, b"Hello HTTP!", end_stream=True)
        assert client.bytes_to_send() == (
            b"POST / HTTP/1.1\r\n"
            b"Host: example.com\r\n"
            b"Content-Length: 11\r\n"
            b"\r\n"
            b"Hello HTTP!"
        )
        assert_connection_active(client)

    def test_send_post_in_parts(self, client: HTTP1Protocol) -> None:
        """
        Test a POST request when data are not provided at once.
        """
        headers = build_request_headers((b"content-length", b"11"), method=b"POST")
        stream_id = client.get_available_stream_id()
        client.submit_headers(stream_id, headers)
        client.bytes_to_send()
        client.submit_data(stream_id, b"H")
        client.submit_data(stream_id, b"el")
        client.submit_data(stream_id, b"lo HTTP!")
        assert client.bytes_to_send() == b"Hello HTTP!"
        assert_connection_active(client)

    def test_send_post_wo_content_length(self, client: HTTP1Protocol) -> None:
        """
        Test a POST request uses transfer-encoding if content-length is not given.
        """
        headers = build_request_headers(method=b"POST")
        stream_id = client.get_available_stream_id()
        client.submit_headers(stream_id, headers)
        assert client.bytes_to_send() == (
            b"POST / HTTP/1.1\r\n"
            b"Host: example.com\r\n"
            b"Transfer-Encoding: chunked\r\n"
            b"\r\n"
        )
        client.submit_data(stream_id, b"Hello HTTP!", end_stream=True)
        assert client.bytes_to_send() == b"b\r\nHello HTTP!\r\n0\r\n\r\n"
        assert_connection_active(client)

    @classmethod
    def _send_request(
        cls,
        client: HTTP1Protocol,
        headers: HeadersType | None = None,
        end_stream: bool = True,
    ) -> int:
        if headers is None:
            headers = build_request_headers()
        stream_id = client.get_available_stream_id()
        client.submit_headers(stream_id, headers, end_stream=end_stream)
        client.bytes_to_send()
        return stream_id

    @pytest.mark.parametrize(
        "payload,error_code",
        [
            pytest.param(b"\r\n\r\n", 400, id="empty"),
            pytest.param(b"\r\nContent-Length: 11\r\n\r\n", 400, id="status_empty"),
            pytest.param(
                b"XXX\r\nContent-Length: 11\r\n\r\n", 400, id="status_invalid"
            ),
            pytest.param(b"X" * 100_000, 431, id="status_too_long"),
        ],
    )
    def test_recv_invalid(
        self, client: HTTP1Protocol, payload: bytes, error_code: int
    ) -> None:
        """
        Test that invalid response causes an error.
        """
        self._send_request(client)
        client.bytes_received(payload)
        assert client.next_event() == ConnectionTerminated(error_code)
        assert_connection_expired(client)

    def test_recv(self, client: HTTP1Protocol) -> None:
        """
        Test receive a response.
        """
        stream_id = self._send_request(client)
        expected_headers = build_response_headers((b"content-length", b"11"))
        client.bytes_received(
            b"HTTP/1.1 200 OK\r\nContent-Length: 11\r\n\r\nHello HTTP!"
        )
        assert client.next_event() == HeadersReceived(stream_id, expected_headers)
        assert client.next_event() == DataReceived(
            stream_id, b"Hello HTTP!", end_stream=True
        )
        assert_connection_available(client)

    def test_recv_fragmented(self, client: HTTP1Protocol) -> None:
        """
        Test receive a response in multiple fragments.
        """
        stream_id = self._send_request(client)
        expected_headers = build_response_headers((b"content-length", b"11"))
        client.bytes_received(b"HTTP/1.1 200 OK\r\nContent-Len")
        assert client.next_event() is None
        client.bytes_received(b"gth: 11\r\n\r\nHello ")
        assert client.next_event() == HeadersReceived(stream_id, expected_headers)
        assert client.next_event() == DataReceived(
            stream_id, b"Hello ", end_stream=False
        )
        assert client.next_event() is None
        client.bytes_received(b"HTTP!")
        assert client.next_event() == DataReceived(stream_id, b"HTTP!", end_stream=True)
        assert_connection_available(client)

    def test_recv_response_to_head_request(self, client: HTTP1Protocol) -> None:
        """
        Test receive a response to a HEAD request.

        Response to HEAD has never body so headers should end the stream,
        even if Content-Length header is present.
        """
        request_headers = build_request_headers(method=b"HEAD")
        stream_id = self._send_request(client, request_headers)
        expected_headers = build_response_headers((b"content-length", b"11"))
        client.bytes_received(b"HTTP/1.1 200 OK\r\nContent-Length: 11\r\n\r\n")
        assert client.next_event() == HeadersReceived(
            stream_id, expected_headers, end_stream=True
        )
        assert_connection_available(client)

    def test_recv_transfer_encoding_chunked(self, client: HTTP1Protocol) -> None:
        """
        Test receive a response with transfer-encoding instead of content-length.
        """
        stream_id = self._send_request(client)
        expected_headers = build_response_headers((b"transfer-encoding", b"chunked"))
        client.bytes_received(b"HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\n\r\n")
        assert client.next_event() == HeadersReceived(stream_id, expected_headers)
        assert client.next_event() is None
        client.bytes_received(b"6\r\nHello \r\n")
        assert client.next_event() == DataReceived(
            stream_id, b"Hello ", end_stream=False
        )
        assert client.next_event() is None
        client.bytes_received(b"5\r\nHTTP!\r\n0\r\n\r\n")
        assert client.next_event() == DataReceived(stream_id, b"HTTP!", end_stream=True)
        assert_connection_available(client)

    def test_recv_http_10(self, client: HTTP1Protocol) -> None:
        """
        Test receive a response without content-length or transfer-encoding.
        """
        stream_id = self._send_request(client)
        expected_headers = build_response_headers()
        client.bytes_received(b"HTTP/1.0 200 OK\r\n\r\n")
        assert client.next_event() == HeadersReceived(stream_id, expected_headers)
        assert client.next_event() is None
        client.bytes_received(b"Hello ")
        assert client.next_event() == DataReceived(
            stream_id, b"Hello ", end_stream=False
        )
        assert client.next_event() is None
        client.bytes_received(b"HTTP!")
        assert client.next_event() == DataReceived(
            stream_id, b"HTTP!", end_stream=False
        )
        assert client.next_event() is None
        client.eof_received()
        assert client.next_event() == DataReceived(stream_id, b"", end_stream=True)
        assert client.next_event() == ConnectionTerminated()
        assert_connection_expired(client)

    def test_recv_connection_close(self, client: HTTP1Protocol) -> None:
        """
        Test receive a response without content-length or transfer-encoding.
        """
        self._send_request(client)
        response = (
            b"HTTP/1.1 200 OK\r\n"
            b"Content-Length: 11\r\n"
            b"Connection: close\r\n"
            b"\r\n"
            b"Hello HTTP!"
        )
        client.bytes_received(response)
        assert isinstance(client.next_event(), HeadersReceived)
        assert isinstance(client.next_event(), DataReceived)
        assert client.next_event() == ConnectionTerminated()
        assert_connection_expired(client)

    @pytest.mark.parametrize(
        "payload",
        [
            pytest.param(b"HTTP/1.1 200 OK\r\n", id="partial-headers"),
            pytest.param(
                b"HTTP/1.1 200 OK\r\nContent-Length: 11\r\n\r\n", id="headers"
            ),
            pytest.param(
                b"HTTP/1.1 200 OK\r\nContent-Length: 11\r\n\r\nHello ",
                id="partial-body",
            ),
            pytest.param(b"HTTP/1.0 200 OK\r\n", id="http10-partial-headers"),
            pytest.param(b"HTTP/1.0 200 OK\r\n\r\n", id="http10-headers"),
            pytest.param(b"HTTP/1.0 200 OK\r\n\r\nHello ", id="http10-partial-body"),
        ],
    )
    def test_connection_lost_during_response(
        self, client: HTTP1Protocol, payload: bytes
    ) -> None:
        """
        Test connection lost without EOF when receiving a response.
        """
        self._send_request(client)
        client.bytes_received(payload)
        client.connection_lost()
        event = client.next_event()
        while isinstance(event, (HeadersReceived, DataReceived)):
            event = client.next_event()
        assert event == ConnectionTerminated()
        assert_connection_expired(client)

    @pytest.mark.parametrize(
        "payload",
        [
            pytest.param(b"HTTP/1.1 200 OK\r\n", id="partial-headers"),
            pytest.param(
                b"HTTP/1.1 200 OK\r\nContent-Length: 11\r\n\r\n", id="headers"
            ),
            pytest.param(
                b"HTTP/1.1 200 OK\r\nContent-Length: 11\r\n\r\nHello ",
                id="partial-body",
            ),
            pytest.param(b"HTTP/1.0 200 OK\r\n", id="http10-partial-headers"),
        ],
    )
    def test_eof_received_during_response(
        self, client: HTTP1Protocol, payload: bytes
    ) -> None:
        """
        Test connection closed with EOF when receiving a response.
        """
        self._send_request(client)
        client.bytes_received(payload)
        client.eof_received()
        event = client.next_event()
        while isinstance(event, (HeadersReceived, DataReceived)):
            event = client.next_event()
        assert event == ConnectionTerminated(400)
        assert_connection_expired(client)

    def test_stream_reset(self, client: HTTP1Protocol) -> None:
        """
        Test that stream reset for HTTP/1 is translated to connection reset.
        """
        self._send_request(client)
        client.bytes_received(b"HTTP/1.1 200 OK\r\n")
        client.submit_stream_reset(1)
        assert client.next_event() == ConnectionTerminated()
        assert_connection_expired(client)

    @classmethod
    def _recv_response(
        cls, client: HTTP1Protocol, response: bytes | None = None
    ) -> None:
        if response is None:
            response = b"HTTP/1.1 200 OK\r\nContent-Length: 11\r\n\r\nHello HTTP!"
        client.bytes_received(response)
        event = client.next_event()
        assert isinstance(event, HeadersReceived)
        while event is not None:
            event = client.next_event()

    def test_connection_lost_after_response(self, client: HTTP1Protocol) -> None:
        self._send_request(client)
        self._recv_response(client)
        client.connection_lost()
        assert client.next_event() == ConnectionTerminated()
        assert_connection_expired(client)

    def test_eof_received_after_response(self, client: HTTP1Protocol) -> None:
        self._recv_response(client)
        client.eof_received()
        assert client.next_event() == ConnectionTerminated()
        assert_connection_expired(client)

    def test_multiple_requests(self, client: HTTP1Protocol) -> None:
        """
        Test multiple requests.

        HTTP/1 supports serial requests only.
        """
        assert self._send_request(client) == 1
        expected_headers = build_response_headers((b"content-length", b"11"))
        client.bytes_received(
            b"HTTP/1.1 200 OK\r\nContent-Length: 11\r\n\r\nHello HTTP!"
        )
        assert client.next_event() == HeadersReceived(1, expected_headers)
        assert client.next_event() == DataReceived(1, b"Hello HTTP!", end_stream=True)
        assert client.next_event() is None

        assert self._send_request(client) == 2
        expected_headers = build_response_headers((b"content-length", b"12"))
        client.bytes_received(
            b"HTTP/1.1 200 OK\r\nContent-Length: 12\r\n\r\nHello again!"
        )
        assert client.next_event() == HeadersReceived(2, expected_headers)
        assert client.next_event() == DataReceived(2, b"Hello again!", end_stream=True)
        assert_connection_available(client)

    _connect_request_headers = [
        (b":method", b"CONNECT"),
        (b":authority", b"example.com:443"),
    ]

    def test_http_connect(self, client: HTTP1Protocol) -> None:
        """
        Test CONNECT request and response.
        """
        stream_id = client.get_available_stream_id()
        client.submit_headers(stream_id, self._connect_request_headers)
        assert client.bytes_to_send() == (
            # fmt: off
            b"CONNECT example.com:443 HTTP/1.1\r\n"
            b"Host: example.com:443\r\n"
            b"\r\n"
        )
        client.bytes_received(b"HTTP/1.1 200 OK\r\n\r\n")
        assert client.next_event() == HeadersReceived(stream_id, [(b":status", b"200")])
        assert_connection_active(client)

    def test_http_connect_trailing_data(self, client: HTTP1Protocol) -> None:
        """
        Test data sent with a response to a CONNECT request.
        """
        stream_id = client.get_available_stream_id()
        client.submit_headers(stream_id, self._connect_request_headers)
        assert client.bytes_to_send()
        client.bytes_received(b"HTTP/1.1 200 OK\r\n\r\nHello")
        assert isinstance(client.next_event(), HeadersReceived)
        assert client.next_event() == DataReceived(stream_id, b"Hello")
        assert_connection_active(client)

    def _http_connect(self, client: HTTP1Protocol) -> int:
        stream_id = client.get_available_stream_id()
        client.submit_headers(stream_id, self._connect_request_headers)
        assert client.bytes_to_send()
        client.bytes_received(b"HTTP/1.1 200 OK\r\n\r\n")
        assert isinstance(client.next_event(), HeadersReceived)
        assert client.next_event() is None
        return stream_id

    def test_http_connect_data(self, client: HTTP1Protocol) -> None:
        """
        Data can be exchanged after a CONNECT request.
        """
        stream_id = self._http_connect(client)
        client.submit_data(stream_id, b"Ping")
        assert client.bytes_to_send() == b"Ping"
        client.bytes_received(b"Pong")
        assert client.next_event() == DataReceived(stream_id, b"Pong")
        assert_connection_active(client)

    def test_http_connect_client_end_stream(self, client: HTTP1Protocol) -> None:
        stream_id = self._http_connect(client)
        client.submit_data(stream_id, b"Bye", end_stream=True)
        assert client.bytes_to_send() == b"Bye"
        assert client.next_event() == ConnectionTerminated()
        assert_connection_expired(client)

    def test_http_connect_eof_received(self, client: HTTP1Protocol) -> None:
        self._http_connect(client)
        client.eof_received()
        assert client.next_event() == ConnectionTerminated()
        assert_connection_expired(client)

    def test_http_connect_connection_lost(self, client: HTTP1Protocol) -> None:
        self._http_connect(client)
        client.connection_lost()
        assert client.next_event() == ConnectionTerminated()
        assert_connection_expired(client)


class TestServer:
    def test_connection_made(self, server: HTTP1Protocol) -> None:
        """
        Test that init is no-op for HTTP/1.
        """
        assert_connection_available(server)

    def test_connection_lost(self, server: HTTP1Protocol) -> None:
        """
        Test connection lost without EOF before the first request.
        """
        server.connection_lost()
        assert server.next_event() == ConnectionTerminated()
        assert_connection_expired(server)

    def test_eof_received(self, server: HTTP1Protocol) -> None:
        """
        Test connection closed with EOF before the first request.
        """
        server.eof_received()
        assert server.next_event() == ConnectionTerminated()
        assert_connection_expired(server)
        server.connection_lost()
        assert_connection_expired(server)

    @pytest.mark.parametrize(
        "payload,error_code",
        [
            pytest.param(b"\r\n\r\n", 400, id="empty"),
            pytest.param(b"\r\nHost: example.com\r\n\r\n", 400, id="req_empty"),
            pytest.param(b"XXX\r\nHost: example.com\r\n\r\n", 400, id="req_invalid"),
            pytest.param(b"X" * 100000, 431, id="req_too_long"),
            pytest.param(b"GET / HTTP/1.1\r\n\r\n", 400, id="missing_host"),
        ],
    )
    def test_recv_invalid(
        self, server: HTTP1Protocol, payload: bytes, error_code: int
    ) -> None:
        server.bytes_received(payload)
        assert server.next_event() == ConnectionTerminated(error_code)
        assert_connection_expired(server)

    def test_recv_get(self, server: HTTP1Protocol) -> None:
        """
        Test receive a GET request.
        """
        headers = build_request_headers()
        server.bytes_received(b"GET / HTTP/1.1\r\nHost: example.com\r\n\r\n")
        assert server.next_event() == HeadersReceived(1, headers, end_stream=True)
        assert_connection_active(server)

    def test_recv_get_fragmented(self, server: HTTP1Protocol) -> None:
        """
        Test receive a GET request in multiple fragments.
        """
        headers = build_request_headers()
        server.bytes_received(b"GET / HTTP/1.1")
        server.bytes_received(b"\r\nHost: example.com\r\n\r\n")
        assert server.next_event() == HeadersReceived(1, headers, end_stream=True)
        assert_connection_active(server)

    def test_recv_post(self, server: HTTP1Protocol) -> None:
        """
        Test receive a POST request.
        """
        headers = build_request_headers((b"content-length", b"11"), method=b"POST")
        server.bytes_received(
            b"POST / HTTP/1.1\r\n"
            b"Host: example.com\r\n"
            b"Content-Length: 11\r\n"
            b"\r\n"
            b"Hello HTTP!"
        )
        assert server.next_event() == HeadersReceived(1, headers)
        assert server.next_event() == DataReceived(1, b"Hello HTTP!", end_stream=True)
        assert_connection_active(server)

    def test_recv_post_fragmented(self, server: HTTP1Protocol) -> None:
        """
        Test receive a POST request in multiple fragments.
        """
        headers = build_request_headers((b"content-length", b"11"), method=b"POST")
        server.bytes_received(b"POST / HTTP/1.1\r\nHost: example.com\r\nContent-Len")
        assert server.next_event() is None
        server.bytes_received(b"gth: 11\r\n\r\nHello ")
        assert server.next_event() == HeadersReceived(1, headers)
        assert server.next_event() == DataReceived(1, b"Hello ")
        assert server.next_event() is None
        server.bytes_received(b"HTTP!")
        assert server.next_event() == DataReceived(1, b"HTTP!", end_stream=True)
        assert_connection_active(server)

    def test_recv_post_with_empty_data(self, server: HTTP1Protocol) -> None:
        """
        Test receive a POST request with empty data.
        """
        headers = build_request_headers((b"content-length", b"0"), method=b"POST")
        server.bytes_received(
            b"POST / HTTP/1.1\r\n"
            b"Host: example.com\r\n"
            b"Content-Length: 0\r\n"
            b"\r\n"
        )
        assert server.next_event() == HeadersReceived(1, headers, end_stream=True)
        assert_connection_active(server)

    def test_recv_no_content_length(self, server: HTTP1Protocol) -> None:
        """
        Test that a default content-length is 0, event for POST request.
        """
        headers = build_request_headers(method=b"POST")
        server.bytes_received(b"POST / HTTP/1.1\r\nHost: example.com\r\n\r\n")
        assert server.next_event() == HeadersReceived(1, headers, end_stream=True)
        assert_connection_active(server)

    def test_recv_transfer_encoding_chunked(self, server: HTTP1Protocol) -> None:
        """
        Test receive request with Transfer-Encoding chunked instead of Content-Length.
        """
        headers = build_request_headers(
            (b"transfer-encoding", b"chunked"), method=b"POST"
        )
        server.bytes_received(
            b"POST / HTTP/1.1\r\n"
            b"Host: example.com\r\n"
            b"Transfer-Encoding: chunked\r\n"
            b"\r\n"
        )
        assert server.next_event() == HeadersReceived(1, headers)
        assert server.next_event() is None
        server.bytes_received(b"6\r\nHello \r\n")
        assert server.next_event() == DataReceived(1, b"Hello ")
        assert server.next_event() is None
        server.bytes_received(b"5\r\nHTTP!\r\n0\r\n\r\n")
        assert server.next_event() == DataReceived(1, b"HTTP!", end_stream=True)
        assert_connection_active(server)

    def test_recv_http_10(self, server: HTTP1Protocol) -> None:
        server.bytes_received(b"GET / HTTP/1.0\r\n\r\n")
        expected_headers = [
            (b":method", b"GET"),
            (b":scheme", b"https"),
            (b":authority", b""),
            (b":path", b"/"),
        ]
        assert server.next_event() == HeadersReceived(
            1, expected_headers, end_stream=True
        )
        # assert_connection_active(server)  # FIXME

    @pytest.mark.parametrize(
        "payload",
        [
            pytest.param(b"GET / HTTP/1.1\r\n", id="partial-headers"),
            pytest.param(
                b"POST / HTTP/1.1\r\n"
                b"Host: example.com\r\n"
                b"Content-Length: 11\r\n"
                b"\r\n",
                id="headers",
            ),
            pytest.param(
                b"POST / HTTP/1.1\r\n"
                b"Host: example.com\r\n"
                b"Content-Length: 11\r\n"
                b"\r\n"
                b"Hello",
                id="partial-body",
            ),
        ],
    )
    def test_connection_lost_during_request(
        self, server: HTTP1Protocol, payload: bytes
    ) -> None:
        """
        Test connection lost without EOF when receiving a request.
        """
        server.bytes_received(payload)
        server.connection_lost()
        event = server.next_event()
        while isinstance(event, (HeadersReceived, DataReceived)):
            event = server.next_event()
        assert event == ConnectionTerminated()
        assert_connection_expired(server)

    @pytest.mark.parametrize(
        "payload",
        [
            pytest.param(b"GET / HTTP/1.1\r\n", id="partial-headers"),
            pytest.param(
                b"POST / HTTP/1.1\r\n"
                b"Host: example.com\r\n"
                b"Content-Length: 11\r\n"
                b"\r\n",
                id="headers",
            ),
            pytest.param(
                b"POST / HTTP/1.1\r\n"
                b"Host: example.com\r\n"
                b"Content-Length: 11\r\n"
                b"\r\n"
                b"Hello",
                id="partial-body",
            ),
        ],
    )
    def test_eof_received_during_request(
        self, server: HTTP1Protocol, payload: bytes
    ) -> None:
        """
        Test connection closed with EOF when receiving a request.
        """
        server.bytes_received(payload)
        server.eof_received()
        event = server.next_event()
        while isinstance(event, (HeadersReceived, DataReceived)):
            event = server.next_event()
        assert event == ConnectionTerminated(400)
        assert_connection_expired(server)

    @classmethod
    def _recv_request(cls, server: HTTP1Protocol, request: bytes | None = None) -> int:
        if request is None:
            request = b"GET / HTTP/1.1\r\nHost: example.com\r\n\r\n"
        server.bytes_received(request)
        event = server.next_event()
        assert isinstance(event, HeadersReceived)
        stream_id = event.stream_id
        end_stream = event.end_stream
        while not end_stream:
            event = server.next_event()
            assert isinstance(event, DataReceived)
            end_stream = event.end_stream
        return stream_id

    def test_send_response(self, server: HTTP1Protocol) -> None:
        """
        Test sending a response.
        """
        stream_id = self._recv_request(server)
        headers = build_response_headers((b"content-length", b"11"))
        server.submit_headers(stream_id, headers)
        # TODO: This assert will work for h11 only (it has not ascii status messages)
        assert server.bytes_to_send() == b"HTTP/1.1 200 \r\nContent-Length: 11\r\n\r\n"
        server.submit_data(stream_id, b"Hello HTTP!", end_stream=True)
        assert server.bytes_to_send() == b"Hello HTTP!"
        assert_connection_available(server)

    def test_send_response_at_once(self, server: HTTP1Protocol) -> None:
        """
        Test sending response headers with body at once.
        """
        stream_id = self._recv_request(server)
        headers = build_response_headers((b"content-length", b"11"))
        server.submit_headers(stream_id, headers)
        server.submit_data(stream_id, b"Hello HTTP!", end_stream=True)
        assert server.bytes_to_send() == (
            b"HTTP/1.1 200 \r\nContent-Length: 11\r\n\r\nHello HTTP!"
        )
        assert_connection_available(server)

    def test_response_in_parts(self, server: HTTP1Protocol) -> None:
        """
        Test sending a response when data are not given at once.
        """
        stream_id = self._recv_request(server)
        headers = build_response_headers((b"content-length", b"11"))
        server.submit_headers(stream_id, headers)
        assert server.bytes_to_send() == b"HTTP/1.1 200 \r\nContent-Length: 11\r\n\r\n"
        server.submit_data(stream_id, b"Hello ")
        assert server.bytes_to_send() == b"Hello "
        server.submit_data(stream_id, b"HTTP!", end_stream=True)
        assert server.bytes_to_send() == b"HTTP!"
        assert_connection_available(server)

    def test_response_transfer_encoding_chunked(self, server: HTTP1Protocol) -> None:
        """
        Test sending a response when Content-Length is not known.
        """
        stream_id = self._recv_request(server)
        headers = build_response_headers()
        server.submit_headers(stream_id, headers)
        assert (
            server.bytes_to_send()
            == b"HTTP/1.1 200 \r\nTransfer-Encoding: chunked\r\n\r\n"
        )
        server.submit_data(stream_id, b"Hello ")
        assert server.bytes_to_send() == b"6\r\nHello \r\n"
        server.submit_data(stream_id, b"HTTP!", end_stream=True)
        assert server.bytes_to_send() == b"5\r\nHTTP!\r\n0\r\n\r\n"
        assert_connection_available(server)

    def test_response_to_http_10(self, server: HTTP1Protocol) -> None:
        stream_id = self._recv_request(server, b"GET / HTTP/1.0\r\n\r\n")
        headers = build_response_headers((b"content-length", b"11"))
        server.submit_headers(stream_id, headers)
        assert server.bytes_to_send() == (
            b"HTTP/1.1 200 \r\n"
            b"Content-Length: 11\r\n"
            b"Connection: close\r\n"
            b"\r\n"
        )
        server.submit_data(stream_id, b"Hello HTTP!", end_stream=True)
        assert server.bytes_to_send() == b"Hello HTTP!"
        assert server.next_event() == ConnectionTerminated()
        assert_connection_expired(server)

    def test_response_to_connection_close(self, server: HTTP1Protocol) -> None:
        request = (
            b"GET / HTTP/1.1\r\n"
            b"Host: example.com\r\n"
            b"Connection: close\r\n"
            b"\r\n"
        )
        stream_id = self._recv_request(server, request)
        headers = build_response_headers((b"content-length", b"11"))
        server.submit_headers(stream_id, headers)
        assert server.bytes_to_send() == (
            b"HTTP/1.1 200 \r\n"
            b"Content-Length: 11\r\n"
            b"Connection: close\r\n"
            b"\r\n"
        )
        server.submit_data(stream_id, b"Hello HTTP!", end_stream=True)
        assert server.bytes_to_send() == b"Hello HTTP!"
        assert server.next_event() == ConnectionTerminated()
        assert_connection_expired(server)

    @classmethod
    def _send_response(cls, server: HTTP1Protocol, stream_id: int) -> None:
        headers = build_response_headers((b"content-length", b"11"))
        server.submit_headers(stream_id, headers)
        server.submit_data(stream_id, b"Hello HTTP!", end_stream=True)
        assert server.bytes_to_send().startswith(b"HTTP/1.1 200")

    def test_connection_lost_before_response(self, server: HTTP1Protocol) -> None:
        """
        Test connection lost without EOF between a requests and a response.
        """
        self._recv_request(server)
        server.connection_lost()
        assert server.next_event() == ConnectionTerminated()
        assert_connection_expired(server)

    def test_eof_received_before_response(self, server: HTTP1Protocol) -> None:
        """
        Test connection closed with EOF between a requests and a response.
        """
        self._recv_request(server)
        server.eof_received()
        assert server.next_event() == ConnectionTerminated()
        assert_connection_expired(server)

    def test_connection_lost_after_response(self, server: HTTP1Protocol) -> None:
        """
        Test connection lost without EOF after a response.
        """
        stream_id = self._recv_request(server)
        self._send_response(server, stream_id)
        server.connection_lost()
        assert server.next_event() == ConnectionTerminated()
        assert_connection_expired(server)

    def test_eof_received_after_response(self, server: HTTP1Protocol) -> None:
        """
        Test connection closed with EOF after a response.
        """
        stream_id = self._recv_request(server)
        self._send_response(server, stream_id)
        server.eof_received()
        assert server.next_event() == ConnectionTerminated()
        assert_connection_expired(server)

    def test_multiple_requests(self, server: HTTP1Protocol) -> None:
        # Request 1
        assert self._recv_request(server) == 1
        server.submit_headers(1, build_response_headers((b"content-length", b"11")))
        assert server.bytes_to_send() == b"HTTP/1.1 200 \r\nContent-Length: 11\r\n\r\n"
        server.submit_data(1, b"Hello HTTP!", end_stream=True)
        assert server.bytes_to_send() == b"Hello HTTP!"
        # Request 2
        assert self._recv_request(server) == 2
        server.submit_headers(2, build_response_headers((b"content-length", b"12")))
        assert server.bytes_to_send() == b"HTTP/1.1 200 \r\nContent-Length: 12\r\n\r\n"
        server.submit_data(2, b"Hello again!", end_stream=True)
        assert server.bytes_to_send() == b"Hello again!"
        assert_connection_available(server)

    _connect_request = (
        # fmt: off
        b"CONNECT example.com:80 HTTP/1.1\r\n"
        b"Host: example.com:80\r\n"
        b"\r\n"
    )

    def test_http_connect(self, server: HTTP1Protocol) -> None:
        """
        Test CONNECT request and response.
        """
        server.bytes_received(self._connect_request)
        assert server.next_event() == HeadersReceived(
            1, [(b":method", b"CONNECT"), (b":authority", b"example.com:80")]
        )
        assert_connection_active(server)
        server.submit_headers(1, [(b":status", b"200")])
        assert server.bytes_to_send() == b"HTTP/1.1 200 \r\n\r\n"
        assert_connection_active(server)

    def test_http_connect_trailing_data(self, server: HTTP1Protocol) -> None:
        """
        Test data sent with a CONNECT request.
        """
        server.bytes_received(self._connect_request + b"Hello")
        assert isinstance(server.next_event(), HeadersReceived)
        server.submit_headers(1, [(b":status", b"200")])
        assert server.bytes_to_send() == b"HTTP/1.1 200 \r\n\r\n"
        assert server.next_event() == DataReceived(1, b"Hello")
        assert_connection_active(server)

    def _http_connect(self, server: HTTP1Protocol) -> int:
        server.bytes_received(self._connect_request)
        headers_event = server.next_event()
        assert isinstance(headers_event, HeadersReceived)
        stream_id = headers_event.stream_id
        server.submit_headers(stream_id, [(b":status", b"200")])
        assert server.bytes_to_send()
        return stream_id

    def test_http_connect_data(self, server: HTTP1Protocol) -> None:
        """
        Data can be exchanged after a CONNECT request.
        """
        stream_id = self._http_connect(server)
        server.bytes_received(b"Ping")
        assert server.next_event() == DataReceived(stream_id, b"Ping")
        server.submit_data(stream_id, b"Pong")
        assert server.bytes_to_send() == b"Pong"
        assert_connection_active(server)

    def test_http_connect_end_stream(self, server: HTTP1Protocol) -> None:
        stream_id = self._http_connect(server)
        server.submit_data(stream_id, b"Bye", end_stream=True)
        assert server.bytes_to_send() == b"Bye"
        assert server.next_event() == ConnectionTerminated()

    def test_http_connect_eof_received(self, server: HTTP1Protocol) -> None:
        self._http_connect(server)
        server.eof_received()
        assert server.next_event() == ConnectionTerminated()
        assert_connection_expired(server)

    def test_http_connect_connection_lost(self, server: HTTP1Protocol) -> None:
        self._http_connect(server)
        server.connection_lost()
        assert server.next_event() == ConnectionTerminated()
        assert_connection_expired(server)
