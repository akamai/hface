
Server and Client
=================

The :mod:`hface.server` and :mod:`hface.client` modules provide ready-to-use server and client implementations.

The modules are a Python alternative to the :doc:`command-line interface <cli>`.
They offer a high-level facade to the :doc:`connection layer <connections>`.

Both the server and the client are asynchronous.
The examples here use asyncio_ :func:`asyncio.run()`, but Trio_ is supported too (thanks to AnyIO_).


ASGI server example
-------------------

:class:`hface.server.ASGIServer` can run a server with an ASGI_ application:

.. literalinclude:: ../examples/server.py

(The example should run as it is. It is available in `examples/server.py <https://github.com/akamai/hface/blob/main/examples/server.py>`_)


Proxy server example
--------------------

:class:`hface.server.ProxyServer` can run an HTTP proxy:

.. literalinclude:: ../examples/proxy_server.py

(The example should run as it is. It is available in `examples/proxy_server.py <https://github.com/akamai/hface/blob/main/examples/proxy_server.py>`_)


HTTP client example
-------------------

The :class:`hface.client.Client` can be used to issue an HTTP request:

.. literalinclude:: ../examples/client.py

(The example should run as it is. It is available in `examples/client.py <https://github.com/akamai/hface/blob/main/examples/client.py>`_)

Async context manager :meth:`.Client.session` must be entered to get :class:`.ClientSession`.
The :meth:`.ClientSession.dispatch` makes HTTP requests.

The use of the context manager ensures that no background tasks are left running
(background tasks are needed to maintain HTTP/2 and HTTP/3 connections).

The client has builtin support for HTTP proxies (in the tunneling mode only).


Proxy client example
--------------------

It may be desired to tunnel non-HTTP traffic through an HTTP proxy.
In such cases, it is possible to use directly :class:`hface.client.ProxyClient`:

.. literalinclude:: ../examples/proxy_client.py

(The example should run as it is. It is available in `examples/proxy_client.py <https://github.com/akamai/hface/blob/main/examples/proxy_client.py>`_)

Async context manager :meth:`.ProxyClient.session` must be used to get :class:`.ProxyClientSession`.
This class implements :class:`.ClientNetworking`, so it can be used to open network connections.


Server API
----------

.. module:: hface.server


ASGI server class
.................

.. autoclass:: ASGIServer

    .. autoattribute:: tls_config
    .. autoattribute:: protocol
    .. autoattribute:: http1_factory
    .. autoattribute:: http2_factory
    .. autoattribute:: http3_factory
    .. automethod:: run


Proxy server class
..................

.. autoclass:: ProxyServer

    .. autoattribute:: tls_config
    .. autoattribute:: protocol
    .. autoattribute:: http1_factory
    .. autoattribute:: http2_factory
    .. autoattribute:: http3_factory
    .. automethod:: run


Server models
.............

.. autoclass:: Endpoint
    :members:

.. autoclass:: ServerProtocol
    :members:


Client API
----------

.. module:: hface.client


Client class
............

.. autoclass:: Client

    .. autoattribute:: tls_config
    .. autoattribute:: protocol
    .. autoattribute:: proxy_origin
    .. autoattribute:: proxy_protocol

    .. autoattribute:: http1_factory
    .. autoattribute:: http2_factory
    .. autoattribute:: http3_factory

    .. automethod:: session()


.. autoclass:: ClientSession
    :members: dispatch, aclose


Proxy class
...........

.. autoclass:: ProxyClient

    .. autoattribute:: tls_config
    .. autoattribute:: protocol

    .. autoattribute:: http1_factory
    .. autoattribute:: http2_factory
    .. autoattribute:: http3_factory

    .. automethod:: session

.. autoclass:: ProxyClientSession
    :members: connect_tcp, aclose


Client models
.............

.. autoclass:: Request
    :members:

.. autoclass:: Response
    :members:


.. autoclass:: ClientProtocol
    :members:

.. autoclass:: URL
    :members:

.. autoclass:: Origin
    :members:


.. _asyncio: https://docs.python.org/3/library/asyncio.html
.. _AnyIO: https://anyio.readthedocs.io/
.. _Trio: https://anyio.readthedocs.io/en/stable/index.html
.. _ASGI: https://asgi.readthedocs.io/en/latest/