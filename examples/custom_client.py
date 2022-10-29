import asyncio

from hface.connections import HTTPConnection, HTTPOverTCPOpener
from hface.events import ConnectionTerminated, DataReceived, HeadersReceived
from hface.protocols.http1 import HTTP1ClientFactory


async def make_request(connection: HTTPConnection):
    stream_id = connection.get_available_stream_id()
    headers = [
        (b":method", b"GET"),
        (b":scheme", b"https"),
        (b":authority", b"localhost"),
        (b":path", b"/"),
    ]
    await connection.send_headers(stream_id, headers, end_stream=True)
    data = b""
    end = False
    while not end:
        event = await connection.receive_event()
        if isinstance(event, HeadersReceived):
            end = event.end_stream
        elif isinstance(event, DataReceived):
            data += event.data
            end = event.end_stream
        elif isinstance(event, ConnectionTerminated):
            end = True
    return data


async def main():
    open_connection = HTTPOverTCPOpener(HTTP1ClientFactory())
    async with await open_connection(("localhost", 5443), tls=True) as connection:
        data = await make_request(connection)
    print(data.decode())


if __name__ == "__main__":
    asyncio.run(main())
