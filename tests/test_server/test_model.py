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

import pytest

from hface.server import Endpoint


class TestEndpoint:
    @pytest.mark.parametrize(
        "value, scheme, host, port",
        [
            (":8080", "http", "", 8080),
            ("//:8080", "http", "", 8080),
            ("http://:8080", "http", "", 8080),
            ("https://:8443", "https", "", 8443),
            ("example.com:8080", "http", "example.com", 8080),
            ("//example.com:8080", "http", "example.com", 8080),
            ("http://example.com:8080", "http", "example.com", 8080),
            ("https://example.com:8443", "https", "example.com", 8443),
            ("0.0.0.0:8080", "http", "0.0.0.0", 8080),
            ("[::]:8080", "http", "::", 8080),
            ("https://0.0.0.0:8443", "https", "0.0.0.0", 8443),
            ("https://[::]:8443", "https", "::", 8443),
        ],
    )
    def test_parse(self, value: str, scheme: str, host: str, port: int) -> None:
        assert Endpoint.parse(value) == Endpoint(scheme, host, port)

    @pytest.mark.parametrize(
        "value",
        [
            "//",
            "http://",
            "example.com",
            "//example.com",
            "http://example.com",
            "example.com:8080/foo",
            "example.com:8080?bar",
        ],
    )
    def test_parse_invalid(self, value: str) -> None:
        with pytest.raises(ValueError):
            Endpoint.parse(value)
