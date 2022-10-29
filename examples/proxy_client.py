import asyncio

from hface.client import ProxyClient


async def main():
    proxy_client = ProxyClient("https://localhost:6443")
    async with proxy_client.session() as session:
        stream = await session.connect_tcp_tls(("localhost", 5443))
        await stream.send(b"GET / HTTP/1.1\r\nHost: localhost\r\n\r\n")
        response = await stream.receive()
    print(response.decode())


if __name__ == "__main__":
    asyncio.run(main())
