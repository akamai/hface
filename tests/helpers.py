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

import hface


def build_request_headers(
    *extra_headers: hface.HeaderType,
    method: bytes = b"GET",
    scheme: bytes = b"https",
    authority: bytes = b"example.com",
    path: bytes = b"/",
) -> list[hface.HeaderType]:
    return [
        (b":method", method),
        (b":scheme", scheme),
        (b":authority", authority),
        (b":path", path),
    ] + list(extra_headers)


def build_response_headers(
    *extra_headers: hface.HeaderType,
    status: bytes = b"200",
) -> list[hface.HeaderType]:
    return [
        (b":status", status),
    ] + list(extra_headers)
