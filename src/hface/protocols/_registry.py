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

from dataclasses import dataclass, field
from typing import Any

import importlib_metadata

from . import http1, http2, http3
from ._factories import (
    HTTPOverQUICClientFactory,
    HTTPOverQUICServerFactory,
    HTTPOverTCPFactory,
)


def load_entry_points(factories: dict[str, Any], group: str) -> None:
    entry_points = importlib_metadata.entry_points(group=group)
    for entry_point in entry_points:
        factories[entry_point.name] = entry_point.load()


@dataclass
class ProtocolRegistry:
    """
    Registry of protocol implementations
    """

    #: HTTP/1 server implementations
    http1_servers: dict[str, HTTPOverTCPFactory] = field(default_factory=dict)

    #: HTTP/2 server implementations
    http2_servers: dict[str, HTTPOverTCPFactory] = field(default_factory=dict)

    #: HTTP/3 server implementations
    http3_servers: dict[str, HTTPOverQUICServerFactory] = field(default_factory=dict)

    #: HTTP/1 client implementations
    http1_clients: dict[str, HTTPOverTCPFactory] = field(default_factory=dict)

    #: HTTP/2 client implementations
    http2_clients: dict[str, HTTPOverTCPFactory] = field(default_factory=dict)

    #: HTTP/3 client implementations
    http3_clients: dict[str, HTTPOverQUICClientFactory] = field(default_factory=dict)

    def load(self) -> None:
        """
        Load known implementations.

        Combines :meth:`.load_defaults` and :meth:`.load_entry_points`.
        """
        self.load_defaults()
        self.load_entry_points()

    def load_defaults(self) -> None:
        """
        Load default protocol implementations.
        """
        self.http1_servers["default"] = http1.HTTP1ServerFactory()
        self.http2_servers["default"] = http2.HTTP2ServerFactory()
        self.http3_servers["default"] = http3.HTTP3ServerFactory()
        self.http1_clients["default"] = http1.HTTP1ClientFactory()
        self.http2_clients["default"] = http2.HTTP2ClientFactory()
        self.http3_clients["default"] = http3.HTTP3ClientFactory()

    def load_entry_points(self, prefix: str = "hface.protocols") -> None:
        """
        Load protocol implementations registered with setuptools entrypoints.

        Name of the entrypoint must follow the format:
        ``"hface.protocols.http{1,2,3}_{servers,clients}"``

        Value of the entrypoint must be in the format ``"<module>:<attr>"``,
        where ``<module>`` is a dotted path to Python module
        and ``<attr>`` is an attribute in that module.
        """
        load_entry_points(self.http1_servers, f"{prefix}.http1_servers")
        load_entry_points(self.http2_servers, f"{prefix}.http2_servers")
        load_entry_points(self.http3_servers, f"{prefix}.http3_servers")
        load_entry_points(self.http1_clients, f"{prefix}.http1_clients")
        load_entry_points(self.http2_clients, f"{prefix}.http2_clients")
        load_entry_points(self.http3_clients, f"{prefix}.http3_clients")
