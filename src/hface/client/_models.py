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

from typing import NamedTuple
from urllib.parse import urlsplit

from hface import AddressType, HeadersType, HeaderType

DEFAULT_PORTS = {
    "http": 80,
    "https": 443,
}


class Origin(NamedTuple):
    """
    HTTP origin server.
    """

    #: Either ``"http"`` or ``"https"``.
    scheme: str
    #: A hostname or an IP address
    host: str
    #: A port number
    port: int

    def __repr__(self) -> str:
        return f"<{type(self).__name__}: {str(self)!r}>"

    def __str__(self) -> str:
        return f"{self.scheme}://{self.host}:{self.port}"

    @classmethod
    def parse(
        cls,
        value: str,
        *,
        default_scheme: str = "http",
    ) -> Origin:
        """
        Parse an origin from a string.

        :param value: string value
        :param default_scheme: default scheme
        :return: a new instance
        """
        if "//" not in value:
            value = "//" + value
        parsed = urlsplit(value, scheme=default_scheme)
        port = DEFAULT_PORTS[parsed.scheme] if parsed.port is None else parsed.port
        if not parsed.hostname:
            raise ValueError("Origin must have a host.")
        if parsed.path:
            raise ValueError("Origin must not have a path component")
        if parsed.query:
            raise ValueError("Origin must not have a query component")
        return Origin(parsed.scheme, parsed.hostname or "", port)

    @property
    def tls(self) -> bool:
        """Whether to use TLS"""
        return self.scheme == "https"

    @property
    def address(self) -> AddressType:
        """A tuple with a host and a port"""
        return self.host, self.port


class URL(NamedTuple):
    """
    URL
    """

    #: Either ``"http"`` or ``"https"``.
    scheme: str
    #: A hostname or an IP address
    host: str
    #: A port number
    port: int
    #: Path compoment
    path: str = "/"

    @classmethod
    def parse(cls, value: str, default_scheme: str = "http") -> URL:
        """
        Parse an URL from a string.

        :param value: string value
        :param default_scheme: default scheme
        :return: a new instance
        """
        if "//" not in value:
            value = "//" + value
        parsed = urlsplit(value, scheme=default_scheme)
        scheme = parsed.scheme
        if not scheme:
            raise ValueError("URL has no scheme.")
        if scheme not in DEFAULT_PORTS:
            raise ValueError(f"URL scheme is not supported: {scheme}")
        host = parsed.hostname
        if not host:
            raise ValueError("URL has no host.")
        port = DEFAULT_PORTS[scheme] if parsed.port is None else parsed.port
        path = parsed.path or "/"
        if parsed.query:
            path += "?" + parsed.query
        return URL(scheme, host, port, path)

    def __repr__(self) -> str:
        return f"<{type(self).__name__}: {str(self)!r}>"

    def __str__(self) -> str:
        return f"{self.scheme}://{self.authority}{self.path}"

    @property
    def origin(self) -> Origin:
        """HTTP server referenced by this URL."""
        return Origin(self.scheme, self.host, self.port)

    @property
    def authority(self) -> str:
        """Authority part of this URL (host + port if non-default)"""
        if self.port == DEFAULT_PORTS[self.scheme]:
            return self.host
        return f"{self.host}:{self.port}"


def _clean_headers(headers: HeadersType) -> HeadersType:
    return [(name.lower(), value) for name, value in headers]


class Request:
    """
    HTTP request

    :param method: HTTP method
    :param url: URL (either a string or an isntance)
    :param headers: HTTP headers (will be normalized to lowecase)
    :param content: Request body to send
    """

    __slots__ = ("method", "url", "headers", "content")

    #: HTTP method
    method: str

    #: URL
    url: URL

    #: HTTP headers
    headers: HeadersType

    #: Request body to send
    content: bytes

    def __init__(
        self,
        method: str,
        url: URL | str,
        *,
        headers: HeadersType | None = None,
        content: bytes | None = None,
    ) -> None:
        self.method = method
        self.url = url if isinstance(url, URL) else URL.parse(url)
        self.headers = [] if headers is None else _clean_headers(headers)
        self.content = b"" if content is None else content

    @property
    def protocol_headers(self) -> HeadersType:
        """
        HTTP headers including the pseudo one.
        """
        return [*self.pseudo_headers, *self.headers]

    @property
    def pseudo_headers(self) -> HeadersType:
        """
        Pseudo headers (``":method"``, ``":scheme"``, ``":authority"``, ``":path"``)
        """
        return [
            (b":method", self.method.encode()),
            (b":scheme", self.url.scheme.encode()),
            (b":authority", self.url.authority.encode()),
            (b":path", self.url.path.encode()),
        ]

    @classmethod
    def from_headers(cls, protocol_headers: HeadersType) -> Request:
        """
        Construct a new instance from headers (including pseudo headers).

        :param protocol_headers: HTTP headers
        :return: a new instance
        """
        method: str | None = None
        scheme: str | None = None
        authority: str | None = None
        path: str | None = None
        headers: list[HeaderType] = []
        for name, value in protocol_headers:
            if name == b":method":
                method = value.decode()
            elif name == b":scheme":
                scheme = value.decode()
            elif name == b":authority":
                authority = value.decode()
            elif name == b":path":
                path = value.decode()
            elif name.startswith(b":"):
                raise ValueError(f"Invalid request header: {name.decode()}")
            else:
                headers.append((name, value))

        if method == "PRI" and path == "*":
            raise ValueError(
                "Invalid headers: "
                "This looks like HTTP/2 preface over HTTP/1 connection."
            )
        if method is None:
            raise ValueError("Missing request header: :method")
        if scheme is None:
            raise ValueError("Missing request header: :scheme")
        if authority is None:
            raise ValueError("Missing request header: :authority")
        if path is None:
            raise ValueError("Missing request header: :path")
        if ":" in authority:
            host, _, str_port = authority.rpartition(":")
            port = int(str_port)
        else:
            host = authority
            port = DEFAULT_PORTS[scheme]
        url = URL(scheme, host, port, path)
        return Request(method, url, headers=headers)


class Response:
    """
    HTTP response

    :param status: HTTP status
    :param headers: HTTP headers
    :param content: Received HTTP body
    """

    __slots__ = ("status", "headers", "content")

    #: HTTP status
    status: int

    #: HTTP headers
    headers: HeadersType

    #: Received HTTP body
    content: bytes

    def __init__(
        self,
        status: int = 200,
        *,
        headers: HeadersType | None = None,
        content: bytes = b"",
    ) -> None:
        self.status = status
        self.headers = [] if headers is None else _clean_headers(headers)
        self.content = content

    @property
    def protocol_headers(self) -> HeadersType:
        """
        HTTP headers including the pseudo one.
        """
        return [*self.pseudo_headers, *self.headers]

    @property
    def pseudo_headers(self) -> HeadersType:
        """
        Pseudo headers (``":status"``)
        """
        return [
            (b":status", f"{self.status}".encode()),
        ]

    @classmethod
    def from_headers(cls, protocol_headers: HeadersType) -> Response:
        """
        Construct a new instance from headers (including pseudo headers).

        :param protocol_headers: HTTP headers
        :return: a new instance
        """
        status: int | None = None
        headers: list[HeaderType] = []
        for name, value in protocol_headers:
            if name == b":status":
                status = int(value.decode())
            elif name.startswith(b":"):
                raise ValueError(f"Invalid response header: {name.decode()}")
            else:
                headers.append((name, value))
        if status is None:
            raise ValueError("Missing response header: :status")
        return Response(status, headers=headers)
