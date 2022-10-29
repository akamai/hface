from __future__ import annotations

import hface


def build_request_headers(
    *extra_headers: hface.HeaderType,
    method: bytes = b"GET",
    scheme: bytes = b"https",
    authority: bytes = b"example.com",
    path: bytes = b"/",
) -> list[hface.HeaderType]:
    return [
        (b":method", method),
        (b":scheme", scheme),
        (b":authority", authority),
        (b":path", path),
    ] + list(extra_headers)


def build_response_headers(
    *extra_headers: hface.HeaderType,
    status: bytes = b"200",
) -> list[hface.HeaderType]:
    return [
        (b":status", status),
    ] + list(extra_headers)
