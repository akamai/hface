import asyncio

from anyio import EndOfStream

from hface.client import ProxyClient


async def main():
    proxy_client = ProxyClient("https://localhost:6443")
    async with proxy_client.session() as session:
        stream = await session.connect_tcp_tls(("localhost", 5443))
        await stream.send(
            b"GET / HTTP/1.1\r\n"
            b"Host: localhost\r\n"
            b"Connection: close\r\n"
            b"\r\n"
        )
        while True:
            try:
                chunk = await stream.receive()
            except EndOfStream:
                break
            print(chunk.decode(), end="")


if __name__ == "__main__":
    asyncio.run(main())
