
Common Models
=============

The root :mod:`hface` module defines a few classes that are reused
at multiple layers of hface.

For example, TLS configuration is needed by the lowest
:doc:`protocol layer <protocols>` (because TLS handled by QUIC),
it used by the middle :doc:`connection layer <connections>`,
but it can be configured at the highest :doc:`server or client <facade>` layer.

The events defined in the :mod:`hface.events` module are returned
from both sans-IO :meth:`.HTTPProtocol.next_event` and con-IO :meth:`.HTTPConnection.receive_event`


Common API
----------

.. module:: hface


.. autoclass:: ServerTLSConfig
    :members:


.. autoclass:: ClientTLSConfig
    :members:


.. autoclass:: HTTPErrorCodes
    :members:


.. py:class:: hface.AddressType

    Alias of :class:`Tuple[str, int]`


.. py:class:: hface.DatagramType

    Alias of :class:`Tuple[bytes, AddressType]`


.. py:class:: hface.HeaderType

    Alias of :class:`Tuple[bytes, bytes]`


.. py:class:: hface.HeadersType

    Alias of :class:`Sequence[HeaderType]`


Events API
----------

.. module:: hface.events


.. autoclass:: Event


.. autoclass:: ConnectionTerminated()

    .. autoattribute:: error_code
    .. autoattribute:: message


.. autoclass:: GoawayReceived()

    .. autoattribute:: last_stream_id
    .. autoattribute:: error_code


.. autoclass:: StreamEvent()

    .. autoattribute:: stream_id


.. autoclass:: HeadersReceived()

    .. autoattribute:: stream_id
    .. autoattribute:: headers
    .. autoattribute:: end_stream


.. autoclass:: DataReceived()

    .. autoattribute:: stream_id
    .. autoattribute:: data
    .. autoattribute:: end_stream


.. autoclass:: StreamReset()

    .. autoattribute:: stream_id
    .. autoattribute:: error_code


.. autoclass:: StreamResetReceived()

    .. autoattribute:: stream_id
    .. autoattribute:: error_code


.. autoclass:: StreamResetSent()

    .. autoattribute:: stream_id
    .. autoattribute:: error_code
