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
