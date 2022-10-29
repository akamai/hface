from __future__ import annotations

from .._asgi import ASGIMessageType, ASGIReceiveType, ASGISendType


async def application(
    scope: ASGIMessageType, receive: ASGIReceiveType, send: ASGISendType
) -> None:
    """
    A simple ASGI application that can be used for demo purposes

    Sends an Alt-Svc header so that browsers can switch to HTTP/3.
    """
    assert scope["type"] == "http"

    http_version = scope["http_version"]
    server_host, server_port = scope["server"]
    method = scope["method"]
    path = scope["path"]
    if scope["query_string"]:
        path += "?" + scope["query_string"]

    more_body = True
    while more_body:
        message = await receive()
        more_body = message.get("more_body", False)

    alt_svc = f'h3=":{server_port}"' if scope["scheme"] == "https" else None

    html = [
        "<h1>It works!</h1>",
        f"<p>{method} {path} HTTP/{http_version}</p>",
    ]
    if alt_svc:
        html.append(f"<p>Alt-Svc: {alt_svc}</p>")

    content = "\r\n".join(html).encode()
    headers = [
        (b"content-type", b"text/html"),
        (b"content-length", str(len(content)).encode()),
    ]
    if alt_svc:
        headers.append((b"alt-svc", alt_svc.encode()))

    await send({"type": "http.response.start", "status": 200, "headers": headers})
    await send({"type": "http.response.body", "body": content})
