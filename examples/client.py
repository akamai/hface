import asyncio

from hface.client import Client, Request


async def main():
    client = Client()
    async with client.session() as session:
        request = Request("GET", "https://localhost:5443/")
        response = await session.dispatch(request)
    print(response.status)
    print(response.content.decode())


if __name__ == "__main__":
    asyncio.run(main())
