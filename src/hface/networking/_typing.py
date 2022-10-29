from __future__ import annotations

from abc import abstractmethod
from typing import Sequence

import anyio.abc

from hface import DatagramType

ByteStream = anyio.abc.ByteStream
DatagramStream = anyio.abc.UnreliableObjectStream[DatagramType]


class QUICStream(DatagramStream):
    """
    Datagram stream aware of QUIC connection IDs.

    HTTP/3 abstraction used by hface is designed as HTTP-over-UDP,
    hiding the QUIC in the middle.
    So QUIC streams extend :class:`hface.networking.DatagramStream`.

    This abstraction is not sufficient at one place - HTTP/3 servers
    need to share one UDP socket between multiple connections.
    In order to make that work, users of QUIC server sockets
    have to call the :meth:`.update_connection_ids` method.
    """

    @abstractmethod
    def update_connection_ids(self, connection_ids: Sequence[bytes]) -> None:
        """
        Update QUIC connection IDs received by this stream.

        :param connection_ids: connection IDs receive by this stream
        """
        raise NotImplementedError
