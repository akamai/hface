
Command-line Interface
======================

When hface is installed, it can be run using the ``hface`` command:

.. code-block:: shell

    hface --help

Alternatively, you can run it as a Python package:

.. code-block:: shell

    python3 -m hface --help


Server
------

An HTTP server can be started using the ``hface server`` subcommand:

.. code-block:: shell

    hface server \
        --cert certs/cert.pem --key certs/key.pem \
        hface.server.examples.hello \
        http://localhost:5080 https://localhost:5443

The first positional argument is a dotted path to a Python module with an ASGI_ application.
The ASGI standard is supported by many application frameworks.

The rest of positional arguments specify endpoints where the server should listen.
The server can listen to both secure (HTTPS) and insecure (HTTP) connections simultaneously.
It can listen at both IPv4 and IPv6.

The server supports all HTTP versions: HTTP/1, HTTP/2, and HTTP/3.
To check HTTP/3 support in a browser, your application has to send the ``Alt-Svc`` header.
You can use ``hface.server.examples.alt_svc`` for that purpose.

.. hint::

    Google Chrome may not switch to HTTP/3 if you are not using
    a TLS certificate from a well-known certificate authority.

    To bypass that limitation, you can run Chrome with a command-line option
    ``--origin-to-force-quic-on=localhost:5443`` or similar.

Run ``hface server --help`` to see all server options.


Client
------

A command-line HTTP client is included too:

.. code-block:: shell

    hface client https://localhost:5443

.. hint::

    If you are using mkcert and the client fails with an SSL error,
    make sure that you ``export SSL_CERT_FILE="$(mkcert -CAROOT)/rootCA.pem"``.

    If you get SSL error when accessing public URL,
    make sure that you did NOT export ``SSL_CERT_FILE``.


By default, the client opens a TPC connection and chooses between HTTP/1 or HTTP/2
based on ALPN in a TLS handshake. The client does not process the Alt-Svc header.
Use the ``--http3`` option to open a QUIC (HTTP/3) connection.

Run ``hface client --help`` to see all client options.


Proxy
-----

An HTTP proxy is included in hface.

The proxy works in the tunneling mode only (the tunneling mode is typically used
for HTTPS URLs, but can be used for insecure requests too).

.. code-block:: shell

    hface proxy \
        --cert certs/cert.pem --key certs/key.pem \
        http://localhost:6080 https://localhost:6443

The hface client has proxy support:

.. code-block:: shell

    hface client --proxy https://localhost:6443 https://localhost:5443

The proxy can accept HTTP/1, HTTP/2, and HTTP/3 connections.
In the tunneling mode, HTTP proxies can tunnel any TCP traffic.
Try to pass combination of ``--proxy-http{1,2,3} --http{1,2}`` options to the client.
Support for proxying UDP (HTTP/3) traffic is planned.

Run ``hface proxy --help`` to see all proxy options.


.. _ASGI: https://asgi.readthedocs.io/