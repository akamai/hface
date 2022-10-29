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

from typing import NamedTuple
from urllib.parse import urlsplit

from hface import AddressType


class Endpoint(NamedTuple):
    """
    An endpoing where a server can listen.
    """

    #: Either ``"http"`` or ``"https"``.
    scheme: str
    #: A hostname or an IP address
    host: str
    #: A port number
    port: int

    def __repr__(self) -> str:
        return f"<{type(self).__name__}: {str(self)!r}>"

    def __str__(self) -> str:
        return f"{self.scheme}://{self.host}:{self.port}"

    @classmethod
    def parse(cls, value: str) -> Endpoint:
        """
        Parse an endpoint from a string.

        :param value: string value
        :return: a new instance
        """
        if "//" not in value:
            value = "//" + value
        parsed = urlsplit(value, scheme="http")
        if parsed.scheme not in {"http", "https"}:
            raise ValueError("Invalid scheme.")
        if parsed.port is None:
            raise ValueError("Endpoint port is required.")
        if parsed.path:
            raise ValueError("Endpoint must not have a path component.")
        if parsed.query:
            raise ValueError("Endpoint must not have a query component.")
        return cls(parsed.scheme, parsed.hostname or "", parsed.port)

    @property
    def tls(self) -> bool:
        """Whether to use TLS"""
        return self.scheme == "https"

    @property
    def address(self) -> AddressType:
        """A tuple with a host and a port"""
        return self.host, self.port
