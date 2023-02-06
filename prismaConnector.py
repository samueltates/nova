import asyncio
from prisma import Prisma


async def main() -> None:
    prisma = Prisma()
    await prisma.connect()

    # # write your queries here
    log = await prisma.log.create(
        data={
            "SessionID": "12c2c62b0aa4666a1939892941108dac1885d986",
            "UserID": "sam",
            "date": "20230204031257",
            "summary": "",
            "body": "",
            "batched": False,
        }
    )

    # print(log)

    logs = await prisma.log.find_many()
    messages = await prisma.message.find_many()
    print(logs)
    print(messages)
    await prisma.disconnect()

if __name__ == '__main__':
    asyncio.run(main())
