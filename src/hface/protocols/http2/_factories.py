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

import h2.config
import h2.connection

from hface.protocols import HTTP2Protocol, HTTPOverTCPFactory

from ._protocol import HTTP2ProtocolImpl

ALPN_PROTOCOL = "h2"


def _get_configuration(*, client_side: bool) -> h2.config.H2Configuration:
    # We cannot validate headers because the h2 library
    # wronly requires :path and :scheme for CONNECT requests:
    # - https://github.com/python-hyper/h2/issues/1247
    # - https://github.com/python-hyper/h2/issues/319
    #
    # Client outbound headers and server inbound headers are problematic.
    # But it does not make sense to validate different headers
    # for the server and the client, so we validate none.
    return h2.config.H2Configuration(
        client_side=client_side,
        validate_outbound_headers=False,
        validate_inbound_headers=False,
    )


def _check_alpn(tls_version: str | None, alpn_protocol: str | None) -> None:
    """
    Raise an exception if HTTP/2 was not negotiated during a TLS handshake.
    """
    #
    # From RFC 9113 (HTTP/2):
    #
    # > A client that knows that a server supports HTTP/2 can establish
    # > a TCP connection and send the connection preface (Section 3.4)
    # > followed by HTTP/2 frames. [...]
    # > This only affects the establishment of HTTP/2 connections over
    # > cleartext TCP; HTTP/2 connections over TLS MUST use protocol
    # > negotiation in TLS [TLS-ALPN].
    if alpn_protocol is None and tls_version is not None:
        raise ValueError("HTTP/2 was not negotiated using ALPN in a TLS handshake.")


class HTTP2ClientFactory(HTTPOverTCPFactory):
    """
    Creates a default HTTP/2 protocol for client-side usage.

    The HTTP/2 implementation is built on the top of the Hyper h2_ library.

    .. _h2: https://python-hyper.org/projects/hyper-h2/

    Implements :class:`.HTTPOverTCPFactory`.
    """

    alpn_protocols = [ALPN_PROTOCOL]

    def __call__(
        self,
        *,
        tls_version: str | None = None,
        alpn_protocol: str | None = None,
    ) -> HTTP2Protocol:
        _check_alpn(tls_version, alpn_protocol)
        config = _get_configuration(client_side=True)
        connection = h2.connection.H2Connection(config)
        return HTTP2ProtocolImpl(connection)


class HTTP2ServerFactory(HTTPOverTCPFactory):
    """
    Creates a default HTTP/2 protocol for server-side usage.

    The HTTP/2 implementation is built on the top of the Hyper h2_ library.

    .. _h2: https://python-hyper.org/projects/hyper-h2/

    Implements :class:`.HTTPOverTCPFactory`.
    """

    alpn_protocols = [ALPN_PROTOCOL]

    def __call__(
        self,
        *,
        tls_version: str | None = None,
        alpn_protocol: str | None = None,
    ) -> HTTP2Protocol:
        _check_alpn(tls_version, alpn_protocol)
        config = _get_configuration(client_side=False)
        connection = h2.connection.H2Connection(config)
        return HTTP2ProtocolImpl(connection)
