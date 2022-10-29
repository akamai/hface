from __future__ import annotations

from typing import Sequence, Tuple

HeaderType = Tuple[bytes, bytes]
HeadersType = Sequence[HeaderType]

AddressType = Tuple[str, int]
DatagramType = Tuple[bytes, AddressType]
