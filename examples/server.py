import asyncio

from hface.server import ASGIServer, Endpoint
from hface.server.examples.hello import application


async def main():
    server = ASGIServer(application)
    server.tls_config.certfile = "certs/cert.pem"
    server.tls_config.keyfile = "certs/key.pem"
    endpoint = Endpoint("https", "localhost", 5443)
    await server.run([endpoint])


if __name__ == "__main__":
    asyncio.run(main())
