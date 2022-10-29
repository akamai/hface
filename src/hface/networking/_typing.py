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
