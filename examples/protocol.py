from hface.events import DataReceived, HeadersReceived
from hface.protocols.http1 import HTTP1ClientFactory


def main():
    protocol_factory = HTTP1ClientFactory()
    protocol = protocol_factory()

    stream_id = protocol.get_available_stream_id()
    headers = [
        (b":method", b"GET"),
        (b":scheme", b"https"),
        (b":authority", b"localhost"),
        (b":path", b"/"),
    ]
    protocol.submit_headers(stream_id, headers, end_stream=True)
    assert protocol.bytes_to_send() == b"GET / HTTP/1.1\r\nHost: localhost\r\n\r\n"

    protocol.bytes_received(b"HTTP/1.1 200 OK\r\nContent-Length: 10\r\n\r\n")
    assert protocol.next_event() == HeadersReceived(
        stream_id,
        [(b":status", b"200"), (b"content-length", b"10")],
    )

    protocol.bytes_received(b"It works!\n")
    assert protocol.next_event() == DataReceived(
        stream_id,
        b"It works!\n",
        end_stream=True,
    )


if __name__ == "__main__":
    main()
