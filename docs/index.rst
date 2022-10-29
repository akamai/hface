
=====
hface
=====

*Hackable HTTP/{1,2,3} {client,server,proxy}*

* HTTP client and server written in Python
* HTTP/1.1, HTTP/2, and HTTP/3 support
* Sans-IO_ core with pluggable protocol implementations
* asyncio_ or Trio_ support thanks to AnyIO_
* Layered design with well-defined APIs


About hface
-----------

.. toctree::
    :maxdepth: 2

    intro
    license


Reference
---------

.. toctree::
    :maxdepth: 2

    install
    cli
    facade
    connections
    protocols
    common


* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`


.. _Sans-IO: https://sans-io.readthedocs.io/
.. _AnyIO: https://anyio.readthedocs.io/
.. _asyncio: https://docs.python.org/3/library/asyncio.html
.. _Trio: https://trio.readthedocs.io/en/stable/