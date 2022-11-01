
Installation
============


Installing the package
----------------------

hface requires Python 3.7 or better. It can be installed using pip:

.. code-block:: shell

    python3 -m pip install hface[all]

When the ``[all]`` extra is selected, all optional dependencies are installed:

* ``[trio]`` - Trio_ support
* ``[uvloop]`` - uvloop_ support



TLS certificates
----------------

To run a server, you will need a TLS certificate.
You can use mkcert_ to generate a certificate that will be trusted by your operating system and your browsers.
Python programs (including hface) do not trust to system certificates, but you can export ``SSL_CERT_DIR`` to fix that.

.. code-block:: shell

    mkdir -p certs/
    mkcert -cert-file certs/cert.pem -key-file certs/key.pem localhost localhost 127.0.0.1 ::1
    export SSL_CERT_FILE="$(mkcert -CAROOT)/rootCA.pem"


.. _Trio: https://github.com/python-trio/trio
.. _uvloop: https://github.com/MagicStack/uvloop
.. _mkcert: https://github.com/FiloSottile/mkcert