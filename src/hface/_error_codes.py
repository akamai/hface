from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class HTTPErrorCodes:
    """
    Provides commonly used error codes for a version of the HTTP protocol.

    Each HTTP version uses different error codes,
    so we provide a few error codes for common use cases.
    """

    # Generic error when a peer violated our expectations.
    protocol_error: int

    # Generic error when something went wrong at our side.
    internal_error: int

    # The TCP connection established in response to a CONNECT request
    # was reset or abnormally closed.
    connect_error: int
