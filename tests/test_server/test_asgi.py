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

import pytest

from hface.server._asgi import (
    ASGIError,
    asgi_message_to_data,
    asgi_message_to_headers,
    data_to_asgi_message,
    headers_to_asgi_scope,
    reset_to_asgi_message,
)


class TestHeadersToASGIScope:
    def test_basic(self) -> None:
        headers = [
            (b":method", b"GET"),
            (b":scheme", b"https"),
            (b":authority", b"example.com"),
            (b":path", b"/El%20Ni%C3%B1o?q=La%20Ni%C3%B1a"),
            (b"Content-Length", b"42"),
        ]
        assert headers_to_asgi_scope(
            headers,
            server_address=("192.168.1.1", 443),
            client_address=("192.168.1.2", 10000),
            http_version="HTTP/1.1",
        ) == {
            "type": "http",
            "asgi": {"version": "3.0", "spec_version": "2.3"},
            "http_version": "HTTP/1.1",
            "method": "GET",
            "scheme": "https",
            "path": "/El Niño",
            "raw_path": b"/El%20Ni%C3%B1o",
            "query_string": "q=La Niña",
            "headers": [(b"host", b"example.com"), (b"content-length", b"42")],
            "client": ("192.168.1.2", 10000),
            "server": ("192.168.1.1", 443),
        }

    def test_host_header(self) -> None:
        headers = [
            (b":method", b"GET"),
            (b":scheme", b"https"),
            (b":authority", b"example.com"),
            (b":path", b"/"),
            (b"Host", b"example.com"),
            (b"Content-Length", b"42"),
        ]
        assert headers_to_asgi_scope(
            headers,
            server_address=("192.168.1.1", 443),
            client_address=("192.168.1.2", 10000),
            http_version="HTTP/1.1",
        )["headers"] == [(b"host", b"example.com"), (b"content-length", b"42")]

    def test_host_header_mismatch(self) -> None:
        headers = [
            (b":method", b"GET"),
            (b":scheme", b"https"),
            (b":authority", b"example.com"),
            (b":path", b"/"),
            (b"Host", b"evil.com"),
            (b"Content-Length", b"42"),
        ]
        with pytest.raises(ValueError):
            headers_to_asgi_scope(
                headers,
                server_address=("192.168.1.1", 443),
                client_address=("192.168.1.2", 10000),
                http_version="HTTP/1.1",
            )


def test_data_to_asgi_message() -> None:
    assert data_to_asgi_message(b"foo", True) == {
        "type": "http.request",
        "body": b"foo",
        "more_body": False,
    }


def test_reset_to_asgi_message() -> None:
    assert reset_to_asgi_message() == {
        "type": "http.disconnect",
    }


class TestaASGIMessageToHeaders:
    def test_basic(self) -> None:
        message = {
            "type": "http.response.start",
            "status": 200,
            "headers": [(b"content-length", b"42")],
        }
        assert asgi_message_to_headers(message) == [
            (b":status", b"200"),
            (b"content-length", b"42"),
        ]

    def test_missing_status(self) -> None:
        message = {
            "type": "http.response.start",
            "headers": [(b"content-length", b"42")],
        }
        with pytest.raises(ASGIError):
            asgi_message_to_headers(message)

    @pytest.mark.parametrize(
        "status",
        [
            "x",
            "200",
            0,
            100,
            600,
        ],
    )
    def test_invalid_status(self, status: object) -> None:
        message = {
            "type": "http.response.start",
            "status": status,
            "headers": [(b"content-length", b"42")],
        }
        with pytest.raises(ASGIError):
            asgi_message_to_headers(message)

    def test_missing_headers(self) -> None:
        message = {
            "type": "http.response.start",
            "status": 200,
        }
        assert asgi_message_to_headers(message) == [
            (b":status", b"200"),
        ]

    @pytest.mark.parametrize(
        "headers",
        [
            "x",
            0,
            [
                b"content-length",
            ],
            [(b"content-length",)],
            [(b"Content-Length", b"42")],
        ],
    )
    def test_invalid_headers(self, headers: object) -> None:
        message = {
            "type": "http.response.start",
            "status": 200,
            "headers": headers,
        }
        with pytest.raises(ASGIError):
            asgi_message_to_headers(message)


class TestASGIMessageToData:
    def test_basic(self) -> None:
        message = {
            "type": "http.response.body",
            "body": b"foo",
            "more_body": True,
        }
        assert asgi_message_to_data(message) == (b"foo", False)

    def test_without_more_body(self) -> None:
        message = {
            "type": "http.response.body",
            "body": b"foo",
        }
        assert asgi_message_to_data(message) == (b"foo", True)

    def test_missing_body(self) -> None:
        message = {
            "type": "http.response.body",
        }
        with pytest.raises(ASGIError):
            asgi_message_to_data(message)

    @pytest.mark.parametrize(
        "body",
        [
            0,
            "x",
            [],
            [b"foo"],
        ],
    )
    def test_invalid_body(self, body: object) -> None:
        message = {
            "type": "http.response.body",
            "body": body,
        }
        with pytest.raises(ASGIError):
            asgi_message_to_data(message)
