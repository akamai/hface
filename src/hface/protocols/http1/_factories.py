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

import h11

from hface.protocols import HTTP1Protocol, HTTPOverTCPFactory

from ._protocol import HTTP1ProtocolImpl

ALPN_PROTOCOL = "http/1.1"


class HTTP1ClientFactory(HTTPOverTCPFactory):
    """
    Creates a default HTTP/1 protocol for client-side usage.

    The HTTP/1 implementation is built on the top of the h11_ library.

    .. _h11: https://h11.readthedocs.io/

    Implements :class:`.HTTPOverTCPFactory`.
    """

    alpn_protocols = [ALPN_PROTOCOL]

    def __call__(
        self,
        *,
        tls_version: str | None = None,
        alpn_protocol: str | None = None,
    ) -> HTTP1Protocol:
        connection = h11.Connection(our_role=h11.CLIENT)
        scheme = "http" if tls_version is None else "https"
        return HTTP1ProtocolImpl(connection, scheme=scheme)


class HTTP1ServerFactory(HTTPOverTCPFactory):
    """
    Creates a default HTTP/1 protocol for server-side usage.

    The HTTP/1 implementation is built on the top of the h11_ library.

    .. _h11: https://h11.readthedocs.io/

    Implements :class:`.HTTPOverTCPFactory`.
    """

    alpn_protocols = [ALPN_PROTOCOL]

    def __call__(
        self,
        *,
        tls_version: str | None = None,
        alpn_protocol: str | None = None,
    ) -> HTTP1Protocol:
        connection = h11.Connection(our_role=h11.SERVER)
        scheme = "http" if tls_version is None else "https"
        return HTTP1ProtocolImpl(connection, scheme=scheme)
