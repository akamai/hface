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

import os
import ssl
from typing import Sequence

import aioquic.h3.connection
import aioquic.quic.configuration
import aioquic.quic.connection
from aioquic.quic.packet import QuicProtocolVersion

from hface import AddressType, ClientTLSConfig, ServerTLSConfig
from hface.protocols import (
    HTTP3Protocol,
    HTTPOverQUICClientFactory,
    HTTPOverQUICServerFactory,
)

from ._protocol import HTTP3ProtocolImpl


class HTTP3ClientFactory(HTTPOverQUICClientFactory):
    """
    Creates a default HTTP/3 protocol for client-side usage.

    The HTTP/3 implementation is built on the top of the aioquic_ library.

    .. _aioquic: https://aioquic.readthedocs.io/

    Implements :class:`.HTTPOverQUICClientFactory`.
    """

    def __call__(
        self,
        *,
        remote_address: AddressType,
        server_name: str,
        tls_config: ClientTLSConfig,
    ) -> HTTP3Protocol:
        configuration = self._build_configuration(tls_config=tls_config)
        configuration.server_name = server_name
        return HTTP3ProtocolImpl(configuration, remote_address=remote_address)

    def _build_configuration(
        self, *, tls_config: ClientTLSConfig
    ) -> aioquic.quic.configuration.QuicConfiguration:
        # OpenSSL (so Python builtin ssl.SSLContext) trusts to SSL_CERT_FILE by default.
        # We set it here explicitly, so that TLS implementations not using OpenSSL
        # (namely aioquic and our default HTTP/3 implementation) use this variable too.
        #
        # We could (and probably should) be more sophisticated in unifying
        # TLS configuration, but just this one hack helps a lot.
        tls_cafile = tls_config.cafile or os.environ.get("SSL_CERT_FILE")
        return aioquic.quic.configuration.QuicConfiguration(
            is_client=True,
            verify_mode=ssl.CERT_NONE if tls_config.insecure else ssl.CERT_REQUIRED,
            cafile=tls_cafile,
            capath=tls_config.capath,
            cadata=tls_config.cadata,
            alpn_protocols=["h3"],
        )


class HTTP3ServerFactory(HTTPOverQUICServerFactory):
    """
    Creates a default HTTP/3 protocol for server-side usage.

    The HTTP/3 implementation is built on the top of the aioquic_ library.

    .. _aioquic: https://aioquic.readthedocs.io/

    Implements :class:`.HTTPOverQUICServerFactory`.
    """

    quic_connection_id_length: int = 8
    quic_supported_versions: Sequence[int] = [QuicProtocolVersion.VERSION_1]

    def __call__(
        self,
        *,
        tls_config: ServerTLSConfig,
    ) -> HTTP3Protocol:
        configuration = self._build_configuration(tls_config=tls_config)
        return HTTP3ProtocolImpl(configuration)

    def _build_configuration(
        self, *, tls_config: ServerTLSConfig
    ) -> aioquic.quic.configuration.QuicConfiguration:
        if tls_config.certfile is None:
            raise ValueError("TLS certfile is required.")
        configuration = aioquic.quic.configuration.QuicConfiguration(
            is_client=False,
            connection_id_length=self.quic_connection_id_length,
            supported_versions=list(self.quic_supported_versions),
            alpn_protocols=["h3"],
        )
        configuration.load_cert_chain(
            tls_config.certfile, tls_config.keyfile  # type: ignore
        )
        return configuration
