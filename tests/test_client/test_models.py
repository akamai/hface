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

import pytest

from hface.client import URL, Origin, Request, Response


class TestOrigin:
    def test_basics(self) -> None:
        origin = Origin("https", "example.com", 443)
        assert origin == ("https", "example.com", 443)
        assert origin == Origin("https", "example.com", 443)
        assert str(origin) == "https://example.com:443"
        assert repr(origin) == "<Origin: 'https://example.com:443'>"
        assert hash(origin) == hash(("https", "example.com", 443))
        assert origin.address == ("example.com", 443)


class TestURL:
    def test_basics(self) -> None:
        url = URL("https", "example.com", 443, "/foo")
        assert url == ("https", "example.com", 443, "/foo")
        assert url == URL("https", "example.com", 443, "/foo")
        assert str(url) == "https://example.com/foo"
        assert repr(url) == "<URL: 'https://example.com/foo'>"
        assert hash(url) == hash(("https", "example.com", 443, "/foo"))
        assert url.origin == Origin("https", "example.com", 443)

    @pytest.mark.parametrize(
        "value, scheme, host, port, path",
        [
            ("example.com", "http", "example.com", 80, "/"),
            ("//example.com", "http", "example.com", 80, "/"),
            ("example.com:8080", "http", "example.com", 8080, "/"),
            ("http://example.com", "http", "example.com", 80, "/"),
            ("https://example.com", "https", "example.com", 443, "/"),
            ("http://example.com:8080", "http", "example.com", 8080, "/"),
            ("https://example.com:8443", "https", "example.com", 8443, "/"),
            ("example.com/foo", "http", "example.com", 80, "/foo"),
            ("example.com?q=a", "http", "example.com", 80, "/?q=a"),
            ("example.com/foo?q=a", "http", "example.com", 80, "/foo?q=a"),
            ("example.com:8080/foo", "http", "example.com", 8080, "/foo"),
        ],
    )
    def test_parse(
        self, value: str, scheme: str, host: str, port: int, path: str
    ) -> None:
        url = URL.parse(value)
        assert url.scheme == scheme
        assert url.host == host
        assert url.port == port
        assert url.path == path

    @pytest.mark.parametrize(
        "value",
        [
            "",
            "//",
            ":8080",
            "https://",
            "https://:8443",
        ],
    )
    def test_parse_invalid(self, value: str) -> None:
        with pytest.raises(ValueError):
            URL.parse(value)

    def test_authority(self) -> None:
        assert URL("http", "example.com", 80).authority == "example.com"
        assert URL("http", "example.com", 8080).authority == "example.com:8080"
        assert URL("https", "example.com", 443).authority == "example.com"
        assert URL("https", "example.com", 8443).authority == "example.com:8443"


def test_request() -> None:
    req = Request(
        "POST",
        "https://example.com:8443",
        headers=[(b"Content-Length", b"11")],
        content=b"Hello HTTP!",
    )
    assert req.method == "POST"
    assert req.url == URL("https", "example.com", 8443)
    assert req.headers == [(b"content-length", b"11")]
    assert req.content == b"Hello HTTP!"
    assert req.protocol_headers == [
        (b":method", b"POST"),
        (b":scheme", b"https"),
        (b":authority", b"example.com:8443"),
        (b":path", b"/"),
        (b"content-length", b"11"),
    ]


def test_request_from_headers() -> None:
    headers = [
        (b":method", b"POST"),
        (b":scheme", b"https"),
        (b":authority", b"example.com:8443"),
        (b":path", b"/"),
        (b"content-length", b"11"),
    ]
    req = Request.from_headers(headers)
    assert req.method == "POST"
    assert req.url == URL("https", "example.com", 8443)
    assert req.headers == [(b"content-length", b"11")]


def test_response() -> None:
    resp = Response(
        200,
        headers=[(b"Content-Length", b"11")],
        content=b"Hello HTTP!",
    )
    assert resp.status == 200
    assert resp.headers == [(b"content-length", b"11")]
    assert resp.content == b"Hello HTTP!"
    assert resp.protocol_headers == [
        (b":status", b"200"),
        (b"content-length", b"11"),
    ]


def test_response_from_headers() -> None:
    headers = [
        (b":status", b"200"),
        (b"content-length", b"11"),
    ]
    resp = Response.from_headers(headers)
    assert resp.status == 200
    assert resp.headers == [(b"content-length", b"11")]
