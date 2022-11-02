
Introduction
============


Why?
----

pip install hface
.................

You cannot ``pip install`` curl or Nginx and their packages do not support HTTP/3 yet.

Think of ``python3 -m http.server`` with HTTP/3 support.
You would never use the builtin server in production,
but it is handy and always available.


High degree of control
......................

The predecessor of hface was created to
`test HTTP/3 proxies <https://www.youtube.com/watch?v=omALOImZpGo>`_.
High-level clients cannot send CONNECT requests over HTTP/3,
they do not deliberately create thousands of parallel streams,
and they cannot be customized to measure every event.

The flexibility of hface makes it a great fit for testing.


Common HTTP interface
.....................

If you write a new HTTP tool, maybe you are considering HTTP/2 and HTTP/3 support.
You probably do want to write logic for each of the versions separately.

hface abstracts out differences between the HTTP versions.
The modular design allows to swap not only HTTP protocols, but also their implementations.
For example, to replace Python code by compiled libraries.


HTTP/3 in Python
................

Most existing Python libraries support HTTP/1 only.
For HTTP/2, httpx_ client or Quart_ server are available,
but there is no ready-to-use HTTP/3 tooling.

The only HTTP/3 implementation in Python is aioquic_.
hface uses aioquic internally and adds higher layers that are easier to use.
Unlike aioquic alone, hface supports all HTTP versions.


Why not?
--------

Development status
..................

hface is a proof of concept that will need lots of work before it becomes stable.

It would be a bad idea to use hface in production today.
The library does very few validation, error handling is non-existent,
and many corner cases are not covered yet. Flow control is totally missing.

hface in its current condition can be great if you want to play with HTTP/3 or HTTP/2.
If you care about HTTP in Python, your feedback will be very welcome.


Low-level only
..............

hface is not a replacement for Requests_, httpx_, or urllib3_.
These libraries offer a nice interface for day-to-day use,
with many high-level functionalities that are not in scope of hface.

If hface becomes stable enough, it should be possible to build
something like the mentioned libraries on top of hface.


Written in Python
.................

hface is a toy compared curl or Nginx. Use them if they solve your use case.

If you must build something on your own, consider whether Python the best language for the task.
It's not a coincidence that most HTTP implementations are written in C, C++, or Rust.

To compensate for Python disadvantages,
hface allows to plug in wrappers for libraries written in other languages.


.. _aioquic: https://aioquic.readthedocs.io/
.. _httpx: https://www.python-httpx.org
.. _Quart: https://quart.palletsprojects.com/
.. _Requests: https://requests.readthedocs.io/
.. _urllib3: https://urllib3.readthedocs.io/
