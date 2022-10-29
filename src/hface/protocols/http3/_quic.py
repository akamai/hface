from __future__ import annotations

from dataclasses import dataclass

import aioquic.buffer
import aioquic.quic.packet


class InvalidPacket(ValueError):
    pass


@dataclass
class PacketInfo:

    version: int | None
    packet_type: int
    destination_connection_id: bytes
    source_connection_id: bytes

    length: int

    @property
    def is_initial_packet(self) -> bool:
        if self.length < 1200:
            return False
        return self.packet_type == aioquic.quic.packet.PACKET_TYPE_INITIAL


def sniff_packet(data: bytes, *, connection_id_length: int) -> PacketInfo:
    buf = aioquic.buffer.Buffer(data=data)
    try:
        header = aioquic.quic.packet.pull_quic_header(
            buf, host_cid_length=connection_id_length
        )
    except ValueError:
        raise InvalidPacket("Invalid header")
    return PacketInfo(
        version=header.version,
        packet_type=header.packet_type,
        destination_connection_id=header.destination_cid,
        source_connection_id=header.source_cid,
        length=len(data),
    )
