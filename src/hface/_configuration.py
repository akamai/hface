from __future__ import annotations

import dataclasses


@dataclasses.dataclass
class ClientTLSConfig:
    """
    Client TLS configuration.
    """

    #: Allows to proceed for server without valid TLS certificates.
    insecure: bool = False

    #: File with CA certificates to trust for server verification
    cafile: str | None = None

    #: Directory with CA certificates to trust for server verification
    capath: str | None = None

    #: Blob with CA certificates to trust for server verification
    cadata: bytes | None = None

    def clone(self) -> ClientTLSConfig:
        """
        Clone this instance.
        """
        return dataclasses.replace(self)


@dataclasses.dataclass
class ServerTLSConfig:
    """
    Server TLS configuration.
    """

    #: File with a server certificate.
    certfile: str | None = None

    #: File with a key for the server certificate.
    keyfile: str | None = None

    def clone(self) -> ServerTLSConfig:
        """
        Clone this instance.
        """
        return dataclasses.replace(self)
