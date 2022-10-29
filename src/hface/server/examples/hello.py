from __future__ import annotations

from .._asgi import ASGIMessageType, ASGIReceiveType, ASGISendType


async def application(
    scope: ASGIMessageType, receive: ASGIReceiveType, send: ASGISendType
) -> None:
    """
    A simple ASGI application that can be used for demo purposes

    Writes JSON-serialized ASGI events to an HTTP response.
    """
    assert scope["type"] == "http"
    body = (
        f"{scope['method']} {scope['path']} HTTP/{scope['http_version']}\r\n"
    ).encode()
    headers = [
        (b"content-type", b"text/plain"),
        (b"content-length", str(len(body)).encode()),
    ]
    await send({"type": "http.response.start", "status": 200, "headers": headers})
    await send({"type": "http.response.body", "body": body})
