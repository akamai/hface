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

"""
HTTP factories create HTTP protools based on defined set of arguments.

We define the :class:`HTTPProtocol` interface to allow interchange
HTTP versions and protocol implementations. But constructors of
the class is not part of the interface. Every implementation
can use a different options to init instances.

Factories unify access to the creation of the protocol instances,
so that clients and servers can swap protocol implementations,
delegating the initialization to factories.
"""
from __future__ import annotations

from abc import ABCMeta, abstractmethod
from typing import Sequence

from hface import AddressType, ClientTLSConfig, ServerTLSConfig

from ._protocols import HTTPOverQUICProtocol, HTTPOverTCPProtocol


class HTTPOverTCPFactory(metaclass=ABCMeta):
    """
    Interface for factories that create :class:`HTTPOverTCPProtocol` instances.
    """

    @property
    @abstractmethod
    def alpn_protocols(self) -> Sequence[str]:
        """
        ALPN protocols to be offered in TLS handshake.

        Ordered from the most preferred to the least.
        """
        raise NotImplementedError

    @abstractmethod
    def __call__(
        self,
        *,
        tls_version: str | None = None,
        alpn_protocol: str | None = None,
    ) -> HTTPOverTCPProtocol:
        """
        Create :class:`HTTPOverTCPProtocol` managing an HTTP connection.

        :param tls_version: TLS version if the connection is secure.
            This will be ``None`` for insecure connection.
        :param alpn_protocol: an ALPN protocol negotiated during a TLS handshake.
            This will be ``None`` for insecure connection and for HTTP/3,
            because the TLS handshake happens at the QUIC layer.
        :return: a fresh instance of an HTTP protocol
        """
        raise NotImplementedError


class ALPNHTTPFactory(HTTPOverTCPFactory):
    """
    A factory that select between other factories based on ALPN.

    Implements :class:`.HTTPOverTCPFactory`.

    :param factories: supported protocols
    :param default_alpn_protocol: ALPN of the default protocol
    """

    _factories: dict[str, HTTPOverTCPFactory]
    _default_alpn_protocol: str

    def __init__(
        self,
        factories: Sequence[HTTPOverTCPFactory],
        default_alpn_protocol: str = "http/1.1",
    ):
        self._factories = {}
        for factory in factories:
            for alpn in factory.alpn_protocols:
                self._factories.setdefault(alpn, factory)
        self._default_alpn_protocol = default_alpn_protocol

    @property
    def alpn_protocols(self) -> Sequence[str]:
        return list(self._factories.keys())

    def __call__(
        self,
        *,
        tls_version: str | None = None,
        alpn_protocol: str | None = None,
    ) -> HTTPOverTCPProtocol:
        if alpn_protocol is None:
            alpn_protocol = self._default_alpn_protocol
        return self._factories[alpn_protocol](
            tls_version=tls_version,
            alpn_protocol=alpn_protocol,
        )


class HTTPOverQUICClientFactory(metaclass=ABCMeta):
    """
    Interface for factories that create :class:`HTTPOverQUICProtocol` for clients.
    """

    @abstractmethod
    def __call__(
        self,
        *,
        remote_address: AddressType,
        server_name: str,
        tls_config: ClientTLSConfig,
    ) -> HTTPOverQUICProtocol:
        """
        Create :class:`HTTPOverQUICProtocol` managing an HTTP connection.

        :param remote_address: network address of the peer.
            This is necessary for client HTTP/3 connections because destination
            addresses for UDP packets are select at the QUIC layer.
        :param server_name: a server name sent in SNI.
            This is necessary for HTTP/3 connections because TLS
            handshake happens at the QUIC layer.
        :param: tls_config: TLS configuration
            This is necessary for HTTP/3 connections because TLS
            handshake happens at the QUIC layer.
        :return: a fresh instance of an HTTP protocol
        """
        raise NotImplementedError


class HTTPOverQUICServerFactory(metaclass=ABCMeta):
    """
    Interface for factories that create :class:`HTTPOverQUICProtocol` for servers.
    """

    # The quic_connection_id_length and quic_supported_versions attributes
    # are necessary for server implementations, which need to sniff
    # and route packets before any a connection protocol is initialized.

    @property
    @abstractmethod
    def quic_connection_id_length(self) -> int:
        """
        Length in bytes of QUIC connection IDs.

        Can be used by servers to sniff and route QUIC packets
        before thay are passed to a protocol instance.
        """
        raise NotImplementedError

    @property
    @abstractmethod
    def quic_supported_versions(self) -> Sequence[int]:
        """
        List of supported QUIC versions.

        Can be used by servers to sniff and route QUIC packets
        before thay are passed to a protocol instance.
        """
        raise NotImplementedError

    @abstractmethod
    def __call__(
        self,
        *,
        tls_config: ServerTLSConfig,
    ) -> HTTPOverQUICProtocol:
        """
        Create :class:`HTTPOverQUICProtocol` managing an HTTP connection.

        :param: tls_config: TLS configuration
            This is necessary for HTTP/3 connections because TLS
            handshake happens at the QUIC layer.
        :return: a fresh instance of an HTTP protocol
        """
        raise NotImplementedError
