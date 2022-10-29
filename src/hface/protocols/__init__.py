from ._factories import (
    ALPNHTTPFactory,
    HTTPOverQUICClientFactory,
    HTTPOverQUICServerFactory,
    HTTPOverTCPFactory,
)
from ._protocols import (
    HTTP1Protocol,
    HTTP2Protocol,
    HTTP3Protocol,
    HTTPOverQUICProtocol,
    HTTPOverTCPProtocol,
    HTTPProtocol,
)
from ._registry import ProtocolRegistry

#: Global instance of :class:`ProtocolRegistry`
#:
#: Use setuptools entrypoints to register new implementations:
#: See :meth:`.ProtocolRegistry.load_entry_points` how.
#:
#: :type: ProtocolRegistry
protocol_registry = ProtocolRegistry()
protocol_registry.load()
