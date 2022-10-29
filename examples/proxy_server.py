import asyncio

from hface.server import Endpoint, ProxyServer


async def main():
    server = ProxyServer()
    server.tls_config.certfile = "certs/cert.pem"
    server.tls_config.keyfile = "certs/key.pem"
    endpoint = Endpoint("https", "localhost", 6443)
    await server.run([endpoint])


if __name__ == "__main__":
    asyncio.run(main())
