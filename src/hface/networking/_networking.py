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

import socket as _socket
import ssl
from abc import ABCMeta, abstractmethod
from contextlib import AsyncExitStack
from socket import AddressFamily
from typing import Sequence, cast

import anyio
from anyio.abc import Listener
from anyio.streams.stapled import MultiListener
from anyio.streams.tls import TLSListener, TLSStream

from hface import AddressType, ClientTLSConfig, ServerTLSConfig

from ._quic import QUICListener, QUICStream
from ._typing import ByteStream, DatagramStream


def _client_ssl_context(
    tls_config: ClientTLSConfig | None, *, alpn_protocols: Sequence[str] | None
) -> ssl.SSLContext:
    if tls_config is None:
        tls_config = ClientTLSConfig()
    context = ssl.create_default_context(
        ssl.Purpose.SERVER_AUTH,
        cafile=tls_config.cafile,
        capath=tls_config.capath,
        cadata=tls_config.cadata,
    )
    if tls_config.insecure:
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
    if alpn_protocols is not None:
        context.set_alpn_protocols(alpn_protocols)
    return context


def _server_ssl_context(
    tls_config: ServerTLSConfig,
    *,
    alpn_protocols: Sequence[str] | None,
) -> ssl.SSLContext:
    if tls_config.certfile is None:
        raise ValueError("TLS certfile is required.")
    context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
    context.load_cert_chain(
        certfile=tls_config.certfile,
        keyfile=tls_config.keyfile,
    )
    if alpn_protocols is not None:
        context.set_alpn_protocols(alpn_protocols)
    return context


class TCPServerNetworking(metaclass=ABCMeta):
    """
    Interface for classes that provide networking for TCP servers.

    Allows to start listening for TCP connections, optionally secured using TLS.
    """

    @abstractmethod
    async def listen_tcp(self, local_address: AddressType) -> Listener[ByteStream]:
        """
        Listen for insecure TCP connections at the given local address.

        :param local_address: an IP address and a port number to listen on
        :return: a new listener instance
        """
        raise NotImplementedError

    async def listen_tcp_tls(
        self,
        local_address: AddressType,
        *,
        tls_config: ServerTLSConfig,
        alpn_protocols: Sequence[str] | None = None,
    ) -> Listener[ByteStream]:
        """
        Listen for TCP connections secured using TLS at the given local address.

        :param local_address: an IP address and a port number to listen on
        :param tls_config: TLS configuration
        :param alpn_protocols: ALPN protocols to offer in a TLS handshake
        :return: a new listener instance
        """
        ssl_context = _server_ssl_context(tls_config, alpn_protocols=alpn_protocols)
        tcp_listener = await self.listen_tcp(local_address)
        listener = TLSListener(
            tcp_listener,
            ssl_context,
            standard_compatible=False,  # HTTP requires this option to be False
        )
        # https://github.com/agronholm/anyio/pull/464
        return cast(Listener[ByteStream], listener)


class QUICServerNetworking(metaclass=ABCMeta):
    """
    Interface for classes that provide networking for QUIC servers.

    Allows to start listening for QUIC connections.
    """

    @abstractmethod
    async def listen_quic(
        self,
        local_address: AddressType,
        *,
        quic_connection_id_length: int,
        quic_supported_versions: Sequence[int],
    ) -> Listener[QUICStream]:
        """
        Listen for secure QUIC connections at the given local address.

        :param local_address: an IP address and a port number to listen on
        :return: a new listener instance
        """
        raise NotImplementedError


class ServerNetworking(TCPServerNetworking, QUICServerNetworking):
    """
    Interface for classes that provide networking for servers.

    Combines :class:`.TCPServerNetworking` and :class:`.QUICServerNetworking`.
    """


class TCPClientNetworking(metaclass=ABCMeta):
    """
    Interface for classes that provide networking for TCP clients.

    Allows to open TCP connections, optionally secured using TLS.
    """

    @abstractmethod
    async def connect_tcp(self, remote_address: AddressType) -> ByteStream:
        """
        Create an insecure TCP connection to the given address.

        :param remote_address: an IP address and a port number to connect to
        :return: a new byte stream
        """
        raise NotImplementedError

    async def connect_tcp_tls(
        self,
        remote_address: AddressType,
        *,
        tls_config: ClientTLSConfig | None = None,
        server_name: str | None = None,
        alpn_protocols: Sequence[str] | None = None,
    ) -> ByteStream:
        """
        Create a TCP connection to the given address secured using TLS.

        :param remote_address: an IP address and a port number to connect to
        :param tls_config: TLS configuration
        :param server_name: override server name sent in TLS SNI
        :param alpn_protocols: ALPN protocols to offer in a TLS handshake
        :return: a new byte stream
        """
        ssl_context = _client_ssl_context(tls_config, alpn_protocols=alpn_protocols)
        tcp_socket = await self.connect_tcp(remote_address)
        try:
            return await TLSStream.wrap(
                tcp_socket,
                server_side=False,
                hostname=server_name or remote_address[0],
                ssl_context=ssl_context,
                standard_compatible=False,  # HTTP requires this option to be False
            )
        except BaseException:
            await anyio.aclose_forcefully(tcp_socket)
            raise


class UDPClientNetworking(metaclass=ABCMeta):
    """
    Interface for classes that provide networking for UDP clients.

    Allows to bind UDP ports.
    """

    @abstractmethod
    async def connect_udp(self, remote_address: AddressType) -> DatagramStream:
        """
        Create a UDP socket that can send packets to the given address.

        The socket is not connected (it can be used to send packets to any address),
        but this will likely change in the future.

        :param remote_address: Remote address. Used to choose between IPv4 and IPv6
        :return: a new datagram stream
        """
        raise NotImplementedError


class ClientNetworking(TCPClientNetworking, UDPClientNetworking):
    """
    Networking for HTTP clients

    Combines :class:`.TCPClientNetworking` and :class:`.UDPClientNetworking`.
    """


class SystemNetworking(ServerNetworking, ClientNetworking):
    """
    Default networking implementation that uses system sockets.

    Implements :class:`.ServerNetworking` and :class:`.ClientNetworking`
    """

    async def connect_tcp(self, remote_address: AddressType) -> ByteStream:
        host, port = remote_address
        return await anyio.connect_tcp(host, port)

    async def listen_tcp(self, local_address: AddressType) -> Listener[ByteStream]:
        local_host, local_port = local_address
        listener = await anyio.create_tcp_listener(
            local_host=local_host, local_port=local_port
        )
        # https://github.com/agronholm/anyio/pull/464
        return cast(Listener[ByteStream], listener)

    async def connect_udp(self, remote_address: AddressType) -> DatagramStream:
        host, port = remote_address
        gai_res = await anyio.getaddrinfo(host, port, type=_socket.SOCK_DGRAM)
        # Prefer IPv4 until we implement happy eyeballs for QUIC connections.
        families = {family for family, _, _, _, _ in gai_res}
        if AddressFamily.AF_INET in families:
            return await anyio.create_udp_socket(family=AddressFamily.AF_INET)
        elif AddressFamily.AF_INET6 in families:
            return await anyio.create_udp_socket(family=AddressFamily.AF_INET6)
        raise ValueError(f"Address cannot be resolved: {remote_address}")

    async def listen_quic(
        self,
        local_address: AddressType,
        *,
        quic_connection_id_length: int,
        quic_supported_versions: Sequence[int],
    ) -> Listener[QUICStream]:
        local_host, local_port = local_address
        # Note about systems without IPv6 support (e.g. Docker on macOS):
        #
        # With the AI_ADDRCONFIG flag, IPv6 addresses should be returned only
        # if the local system has at least one IPv6 address configured.
        # This flag is necessary to avoid:
        # "socket.gaierror: [Errno -9] Address family for hostname not supported"
        #
        # But when this flag is used, we can get duplicate entries because of
        # https://sourceware.org/bugzilla/show_bug.cgi?id=14969
        # The duplicate gai results have to be removed to prevent:
        # "OSError: [Errno 98] Address already in use"
        #
        # The solution with AI_ADDRCONFIG and `sorted(set(gai_res))` is copied from
        # anyio.create_tcp_listener(). And the lesson is recorded in this comment.
        gai_res = await anyio.getaddrinfo(
            local_host, local_port, type=_socket.SOCK_DGRAM, flags=_socket.AI_ADDRCONFIG
        )
        listeners = []
        async with AsyncExitStack() as stack:
            for _, _, _, _, (socket_host, socket_port) in sorted(set(gai_res)):
                socket = await anyio.create_udp_socket(
                    local_host=socket_host, local_port=socket_port
                )
                await stack.enter_async_context(socket)
                listener = QUICListener(
                    socket,
                    quic_connection_id_length=quic_connection_id_length,
                    quic_supported_versions=quic_supported_versions,
                )
                listeners.append(listener)
            stack.pop_all()  # Do not close sockets on success
        return MultiListener(listeners)
