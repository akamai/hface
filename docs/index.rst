
=====
hface
=====

*Hackable HTTP/{1,2,3} {client,server,proxy}*

* HTTP client and server written in Python
* HTTP/1.1, HTTP/2, and HTTP/3 support
* Sans-IO_ core with pluggable protocol implementations
* asyncio_ or Trio_ support thanks to AnyIO_
* Layered design with well-defined APIs

hface is hosted at GitHub_ and it can be installed from PyPI_.

This documentation is available online at `Read the Docs`_.

.. _GitHub: https://github.com/akamai/hface
.. _PyPI: https://pypi.org/project/hface/
.. _Read the Docs: https://hface.readthedocs.io/


About hface
-----------

.. toctree::
    :maxdepth: 2

    intro
    changelog
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