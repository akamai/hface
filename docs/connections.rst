
Connection Layer
================

hface offers  :doc:`ready-to-use <facade>` server and client,
but the true power of this library is in its connection layer
offered by the :mod:`hface.connections` module.

This module should allow others to build new HTTP servers or clients on the top of hface.
The idea is to allow tools to implement their logic using the :class:`.HTTPConnection` class.
This class abstract differences between HTTP versions and their implementation.


Custom server example
---------------------

The following example shows a minimal HTTP server:

.. literalinclude:: ../examples/custom_server.py

(The example should run as it is. It is available in `examples/custom_server.py <https://github.com/akamai/hface/blob/main/examples/custom_server.py>`_)

HTTP connections are handled in the ``handler()`` function.
The example function consumes HTTP events: when it receives request headers,
it sends an HTTP response (ignoring any request body).

The ``handler()`` function can process connection of any HTTP version.
From the ``:status`` pseudo header, the example may appear like HTTP/2, but it uses HTTP/1.
hface translates requests and responses to and from one common format.

You can modify the ``main()`` function to support other HTTP versions:

 - The example uses :class:`.HTTPOverTCPListener` with :class:`.HTTP1ServerFactory`
   to listen for HTTP/1 connections.
 - The factory class can be replaced by :class:`.HTTP2ServerFactory` for HTTP/2 connections.
 - :class:`.HTTPOverQUICListener` together with :class:`.HTTP3ServerFactory`
   offer HTTP/3 support.
 - And finally, :class:`.HTTPMultiListener` and :class:`.ALPNHTTPFactory`
   can provide support for multiple HTTP versions at once.


Custom client example
---------------------

The next example is a simple HTTP client:

.. literalinclude:: ../examples/custom_client.py

(The example should run as it is. It is available in `examples/custom_client.py <https://github.com/akamai/hface/blob/main/examples/custom_client.py>`_)

The ``make_request()`` function send an HTTP request
and waits for HTTP events with response headers and response data.

The function can work with any HTTP version:

 - The example uses :class:`.HTTPOverTCPOpener` with :class:`.HTTP1ClientFactory`
   to open HTTP/1 connections.
 - The factory class can be replaced by :class:`.HTTP2ClientFactory` for HTTP/2 connections.
 - :class:`.HTTPOverQUICOpener` together with :class:`.HTTP3ClientFactory`
   offer HTTP/3 support.
 - :class:`.ALPNHTTPFactory` can choose between HTTP/1 and HTTP/2.

Servers advertise HTTP/3 support using an Alt-Svc header, which is not processed by hface yet.
Selection between TCP and QUIC connections has to be implemented in a higher layer.


How it works?
-------------

The :class:`.HTTPConnection` class provides an unified interface to HTTP connections,
independently on their version.

Each connection combines a sans-IO_ :class:`.HTTPProtocol` with a AnyIO_ stream for IO:

* For HTTP/1 and HTTP/2:

  - :class:`.HTTPOverTCPProtocol` provides sans-IO logic
  - :class:`.ByteStream` can be used to receive and send data.

* For HTTP/3:

  - :class:`.HTTPOverQUICProtocol` provides sans-IO logic
  - :class:`.DatagramStream` can be used to receive and send data.

Both the sans-io and IO parts are represented by an interface (abstract base classes),
so it is possible to plug in own implementations.

HTTP connections cannot be construct directly.
To accept server connections, you need an implementation of the :class:`.HTTPListener` interface:

* :class:`.HTTPOverTCPListener` can accept HTTP/1 and HTTP/2 connections. It consists of:

  - :class:`.HTTPOverTCPFactory` as the sans-IO part,
    which creates instances of :class:`.HTTPOverTCPProtocol`.
  - :class:`.TCPServerNetworking` to provide IO,
    which can listen for :class:`.ByteStream` connections.

* :class:`.HTTPOverQUICListener` can accept HTTP/3 connections. It consists of:

  - :class:`.HTTPOverQUICServerFactory` as the sans-IO part,
    which creates instances of :class:`.HTTPOverQUICProtocol`.
  - :class:`.QUICServerNetworking` to provide IO,
    which can listen for :class:`.QUICStream` connections
    (:class:`.QUICStream` extends :class:`.DatagramStream`).

To open client connection, you need an implementation of the :class:`.HTTPOpener` interface:

* :class:`.HTTPOverTCPOpener` can open HTTP/1 and HTTP/2 connections. It consists of:

  - :class:`.HTTPOverTCPFactory` as the sans-io part,
    which creates instances of :class:`.HTTPOverTCPProtocol`.
  - :class:`.TCPClientNetworking`,
    which can open :class:`.ByteStream` connections.

* :class:`.HTTPOverQUICOpener` can open HTTP/3 connections. It consists of:

  - :class:`.HTTPOverQUICClientFactory` as the sans-io part,
    which creates instances of :class:`.HTTPOverQUICProtocol`.
  - :class:`.UDPClientNetworking`,
    which can open :class:`.DatagramStream` connections.


The sans-IO classes are documented at the :doc:`protocols` page.

Default networking is :class:`.SystemNetworking`, which implements
both :class:`.ServerNetworking` and :class:`.ClientNetworking`.


Connection API
--------------

.. module:: hface.connections


The Connection class
....................

.. autoclass:: HTTPConnection

    .. autoproperty:: http_version
    .. autoproperty:: multiplexed
    .. autoproperty:: local_address
    .. autoproperty:: remote_address
    .. autoproperty:: error_codes
    .. autoproperty:: extra_attributes
    .. automethod:: __aenter__
    .. automethod:: __aexit__
    .. automethod:: open
    .. automethod:: aclose
    .. automethod:: is_available
    .. automethod:: get_available_stream_id
    .. automethod:: send_headers
    .. automethod:: send_data
    .. automethod:: send_stream_reset
    .. automethod:: receive_event


Listeners
.........

.. autoclass:: HTTPListener

    .. automethod:: serve
    .. automethod:: aclose


.. autoclass:: HTTPOverTCPListener

    .. automethod:: create


.. autoclass:: HTTPOverQUICListener

    .. automethod:: create

.. autoclass:: HTTPMultiListener
    :members:


Openers
.......

.. autoclass:: HTTPOpener

    .. automethod:: __call__

.. autoclass:: HTTPOverTCPOpener

.. autoclass:: HTTPOverQUICOpener


Networking API
--------------

.. module:: hface.networking


Networking backends
...................

.. autoclass:: hface.networking.SystemNetworking

    .. automethod:: listen_tcp
    .. automethod:: listen_tcp_tls
    .. automethod:: listen_quic
    .. automethod:: connect_tcp
    .. automethod:: connect_tcp_tls
    .. automethod:: connect_udp


.. autoclass:: hface.networking.ServerNetworking
    :members:


.. autoclass:: hface.networking.TCPServerNetworking
    :members:


.. autoclass:: hface.networking.QUICServerNetworking
    :members:


.. autoclass:: hface.networking.ClientNetworking
    :members:


.. autoclass:: hface.networking.TCPClientNetworking
    :members:


.. autoclass:: hface.networking.UDPClientNetworking
    :members:


Streams
.......

.. py:class:: hface.networking.ByteStream

    Alias of :class:`anyio.abc.ByteStream`


.. py:class:: hface.networking.DatagramStream

    Alias of :class:`anyio.abc.UnreliableObjectStream[hface.DatagramType]`


.. autoclass:: hface.networking.QUICStream()
    :members:


.. _sans-IO: https://sans-io.readthedocs.io
.. _AnyIO: https://anyio.readthedocs.io/
