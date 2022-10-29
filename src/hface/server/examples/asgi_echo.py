from __future__ import annotations

import json

from .._asgi import ASGIMessageType, ASGIReceiveType, ASGISendType


def _to_serializable(obj: object) -> str:
    if isinstance(obj, bytes):
        return obj.decode("latin-1")
    return repr(obj)


def _response_start() -> ASGIMessageType:
    return {
        "type": "http.response.start",
        "status": 200,
        "headers": [
            (b"content-type", b"text/plain"),
        ],
    }


def _response_body(
    message: ASGIMessageType, *, more_body: bool = True
) -> ASGIMessageType:
    body = json.dumps(message, default=_to_serializable) + "\r\n"
    return {
        "type": "http.response.body",
        "body": body.encode(),
        "more_body": more_body,
    }


async def application(
    scope: ASGIMessageType, receive: ASGIReceiveType, send: ASGISendType
) -> None:
    """
    A simple ASGI application that can be used for demo purposes

    Writes JSON-serialized ASGI events to an HTTP response.
    """
    assert scope["type"] == "http"
    await send(_response_start())
    await send(_response_body(scope))
    more_body = True
    while more_body:
        message = await receive()
        assert message["type"] == "http.request"
        more_body = message.get("more_body", False)
        await send(_response_body(message, more_body=more_body))
