
Sans-IO Protocols
=================

The :mod:`hface.protocols` module is the lowest layer of hface.
It provides sans-IO_ (bring-your-own-IO) implementation of HTTP protocols.

The sans-IO approach means that the HTTP implementation never touch a network:

- When you submit HTTP actions, you should ask for data to be sent over the network.
- When you feed data from the network, you should ask for HTTP events.


Sans-IO example
---------------

The following example shows how a protocol class
builds an HTTP request and parses an HTTP response:

.. literalinclude:: ../examples/protocol.py

(The example should run as it is. It is available in `examples/protocol.py <https://github.com/akamai/hface/blob/main/examples/protocol.py>`_)

Notice that the example uses an HTTP/1 protocol,
but the class takes HTTP/2-like headers.
The protocol class translates the headers internally.
This is how hface can offer one interface for all HTTP versions.


How does it work?
-----------------

The central point of the sans-IO layers is the :class:`.HTTPProtocol` interface.
Instances of this interface represent an HTTP connection.
Implementations have to translate HTTP events to network traffic and vice versa.

.. note::

    The protocol interface is heavily inspired by the existing sans-IO libraries:
    h11_, h2_, and aioquic_. At the same time, these libraries are used internally by hface.

    The lowest level of hface can be seen as a unifying interface
    on top of the existing HTTP implementations.


The HTTP-facing side is defined in the :class:`.HTTPProtocol` interface
– it includes methods like :meth:`~.HTTPProtocol.submit_headers`
or :meth:`~.HTTPProtocol.submit_data` for sending.
For receiving, we have the :meth:`~.HTTPProtocol.next_event` method.

The network-facing side is defined in subclasses:

* :class:`.HTTPOverTCPProtocol` should be extended by HTTP/1 and HTTP/2 implementations.
  It has methods like :meth:`~.HTTPOverTCPProtocol.bytes_received`
  and :meth:`~.HTTPOverTCPProtocol.bytes_to_send`.
* :class:`.HTTPOverQUICProtocol` should be extended by HTTP/3 implementations.
  It has methods like :meth:`~.HTTPOverQUICProtocol.datagram_received`
  and :meth:`~.HTTPOverQUICProtocol.datagrams_to_send`.

All of the above classes are abstract.
They define the interfaces, maybe provide some common functionality,
but the actual protocol implementation must be implemented in subclasses.

Protocol implementations are not initialized directly, but through factories.
Thanks to the factories, higher layers (like :class:`.HTTPListener` and :class:`.HTTPOpener`)
have a well-defined interface how to construct protocols for new connections.

* :class:`.HTTPOverTCPFactory` is an interface for creating
  :class:`.HTTPOverTCPProtocol` instances.
* :class:`.HTTPOverQUICServerFactory` and :class:`HTTPOverQUICClientFactory`
  are interfaces for creating :class:`.HTTPOverQUICProtocol` instances.

hface offers default protocols for all HTTP versions:

* :mod:`hface.protocols.http1` offers :class:`.HTTP1ClientFactory` and :class:`.HTTP1ServerFactory`
* :mod:`hface.protocols.http2` offers :class:`.HTTP2ClientFactory` and :class:`.HTTP2ServerFactory`
* :mod:`hface.protocols.http3` offers :class:`.HTTP3ClientFactory` and :class:`.HTTP3ServerFactory`

Known protocol implementations are tracked by :class:`.ProtocolRegistry`
and its global instance :data:`.protocol_registry`.
More implementations can be registered using setuptools entrypoints.


Protocol API
------------

.. module:: hface.protocols

Protocols
.........

.. autoclass:: HTTPProtocol

    .. autoproperty:: http_version
    .. autoproperty:: multiplexed
    .. autoproperty:: error_codes
    .. automethod:: is_available
    .. automethod:: get_available_stream_id
    .. automethod:: submit_headers
    .. automethod:: submit_data
    .. automethod:: submit_stream_reset
    .. automethod:: submit_close
    .. automethod:: next_event



.. autoclass:: HTTPOverTCPProtocol

    .. automethod:: connection_lost
    .. automethod:: eof_received
    .. automethod:: bytes_received
    .. automethod:: bytes_to_send



.. autoclass:: HTTPOverQUICProtocol

    .. autoproperty:: connection_ids
    .. automethod:: clock
    .. automethod:: get_timer
    .. automethod:: connection_lost
    .. automethod:: datagram_received
    .. automethod:: datagrams_to_send

.. autoclass:: HTTP1Protocol
.. autoclass:: HTTP2Protocol
.. autoclass:: HTTP3Protocol


Factories
.........

.. autoclass:: HTTPOverTCPFactory
    :members:

    .. automethod:: __call__

.. autoclass:: HTTPOverQUICClientFactory
    :members:

    .. automethod:: __call__

.. autoclass:: HTTPOverQUICServerFactory
    :members:

    .. automethod:: __call__

.. autoclass:: ALPNHTTPFactory


Registry of implementations
...........................

.. autoclass:: ProtocolRegistry()
    :members:

.. autodata:: protocol_registry
    :annotation:


Default implementations
-----------------------

.. module:: hface.protocols.http1

.. autoclass:: HTTP1ClientFactory

.. autoclass:: HTTP1ServerFactory


.. module:: hface.protocols.http2

.. autoclass:: HTTP2ClientFactory

.. autoclass:: HTTP2ServerFactory


.. module:: hface.protocols.http3

.. autoclass:: HTTP3ClientFactory

.. autoclass:: HTTP3ServerFactory



.. _sans-io: https://sans-io.readthedocs.io
.. _h11: https://h11.readthedocs.io/
.. _h2: https://python-hyper.org/projects/hyper-h2/
.. _aioquic: https://aioquic.readthedocs.io/