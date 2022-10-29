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

from typing import Any, Callable, Coroutine, Dict
from urllib.parse import unquote

from hface import AddressType, HeadersType, HeaderType

ASGIMessageType = Dict[str, Any]
ASGIReceiveType = Callable[[], Coroutine[Any, Any, ASGIMessageType]]
ASGISendType = Callable[[ASGIMessageType], Coroutine[Any, Any, None]]
ASGIAppType = Callable[
    [ASGIMessageType, ASGIReceiveType, ASGISendType], Coroutine[Any, Any, None]
]


class ASGIError(Exception):
    """
    ASGI application misbehaved.
    """


def _split_headers(
    headers: HeadersType,
) -> tuple[dict[bytes, bytes], HeadersType]:
    seen_host: bytes | None = None
    pseudo_headers: dict[bytes, bytes] = {}
    regular_headers: list[HeaderType] = []

    for name, value in headers:
        name = name.lower()
        if name in {b":authority", b"host"}:
            # Translate :authority to Host. From ASGI specs:
            # > Pseudo headers (present in HTTP/2 and HTTP/3) must be removed;
            # > if :authority is present its value must be added to the start
            # > of the iterable with host as the header name or replace any
            # > existing host header already present.
            if seen_host is None:
                seen_host = value
                regular_headers.append((b"host", value))
            elif seen_host != value:
                raise ValueError("Host is ambiguous.")
        elif name.startswith(b":"):
            pseudo_headers[name] = value
        else:
            regular_headers.append((name, value))
    return pseudo_headers, regular_headers


def headers_to_asgi_scope(
    headers: HeadersType,
    *,
    server_address: AddressType,
    client_address: AddressType,
    http_version: str,
) -> ASGIMessageType:
    pseudo_headers, regular_headers = _split_headers(headers)
    raw_path, _, raw_query = pseudo_headers[b":path"].partition(b"?")

    return {
        "type": "http",
        "asgi": {
            "version": "3.0",
            "spec_version": "2.3",
        },
        "http_version": http_version,
        "method": pseudo_headers[b":method"].decode(),
        "scheme": pseudo_headers.get(b":scheme", b"http").decode(),
        "path": unquote(raw_path.decode()),
        "raw_path": raw_path,
        "query_string": unquote(raw_query.decode()),
        "headers": regular_headers,
        "client": tuple(client_address),
        "server": tuple(server_address),
    }


def data_to_asgi_message(data: bytes, end_stream: bool) -> dict[str, object]:
    return {
        "type": "http.request",
        "body": data,
        "more_body": not end_stream,
    }


def reset_to_asgi_message() -> dict[str, object]:
    return {
        "type": "http.disconnect",
    }


def _clean_app_status(event: ASGIMessageType) -> bytes:
    try:
        status = event["status"]
    except KeyError:
        raise ASGIError(f"ASGI {event['type']!r}: missing 'status'")
    if not (isinstance(status, int) and 200 <= status < 600):
        raise ASGIError(f"ASGI {event['type']!r}: invalid 'status'")
    return str(status).encode()


def _clean_app_headers(event: ASGIMessageType) -> HeadersType:
    headers = []
    try:
        for name, value in event.get("headers", ()):
            if not name.islower():
                raise ValueError("Header names must be lowercase.")
            headers.append((name, value))
    except (TypeError, ValueError) as e:
        raise ASGIError(f"ASGI {event['type']!r}: invalid 'headers'") from e
    return headers


def _clean_app_data(event: ASGIMessageType) -> bytes:
    try:
        body = event["body"]
    except KeyError:
        raise ASGIError(f"ASGI {event['type']!r}: missing 'body'") from None
    if not isinstance(body, bytes):
        # TODO: should we support bytes-like objects (buffers)?
        raise ASGIError(f"ASGI {event['type']!r}: invalid 'body'")
    return body


def asgi_message_to_headers(event: ASGIMessageType) -> HeadersType:
    assert event["type"] == "http.response.start"
    return [
        (b":status", _clean_app_status(event)),
        *_clean_app_headers(event),
    ]


def asgi_message_to_data(event: ASGIMessageType) -> tuple[bytes, bool]:
    assert event["type"] == "http.response.body"
    end_stream = not event.get("more_body", False)
    return _clean_app_data(event), end_stream
