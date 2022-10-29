import asyncio

from hface import ServerTLSConfig
from hface.connections import HTTPConnection, HTTPOverTCPListener
from hface.events import ConnectionTerminated, HeadersReceived
from hface.protocols.http1 import HTTP1ServerFactory


async def handler(connection: HTTPConnection):
    print(f"Connection from {connection.remote_address}")
    while True:
        event = await connection.receive_event()
        if isinstance(event, HeadersReceived):
            response_headers = [(b":status", b"200")]
            await connection.send_headers(event.stream_id, response_headers)
            await connection.send_data(event.stream_id, b"It works!\n", end_stream=True)
        elif isinstance(event, ConnectionTerminated):
            break


async def main():
    tls_config = ServerTLSConfig(
        certfile="certs/cert.pem",
        keyfile="certs/key.pem",
    )
    async with await HTTPOverTCPListener.create(
        HTTP1ServerFactory(),
        local_address=("localhost", 5443),
        tls_config=tls_config,
    ) as listener:
        await listener.serve(handler)


if __name__ == "__main__":
    asyncio.run(main())
