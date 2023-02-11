import asyncio
from prisma import Prisma


async def main() -> None:
    prisma = Prisma()
    await prisma.connect()

    ###### PRINTS MESSAGES#########
    messages = await prisma.message.find_many()
    for message in messages:
        print('\n\n\n _________________________________________________________ \n\n\n printing message \n\n\n _________________________________________________________ \n\n\n')
        print(message)

    ###### CREATES LOG #########
    # log = await prisma.log.create(
    #     data={
    #         "SessionID": "bff6ee401dfee717d3ce351243947bd30663b7b6",
    #         "UserID": "sam",
    #         "date": "20230209000000",
    #         "summary": "",
    #         "body": "",
    #         "batched": False,
    #     }
    # )

    ###### FINDS LOG SETS BATCHED TO FALSE #########
    # logs = await prisma.log.find_many()
    # for log in logs:
    #     updatedLog = await prisma.log.update(
    #         where={'id': log.id},
    #         data={'batched': False,
    #               }
    #     )
    #     print(log)
    #     print('\n\n\n _________________________________________________________ \n\n\n')

    #### FINDS LOG #########
    # logs = await prisma.log.find_many()
    # for log in logs:
    #     print(log)
    #     print('\n\n\n _________________________________________________________ \n\n\n')

    # updatedLog = await prisma.log.find_many(
    #     where={'SessionID': 'bff6ee401dfee717d3ce351243947bd30663b7b6', }

    # )

    # print(updatedLog)
    ###### DELETES LOGS #########
    # # logToDelete = await prisma.log.delete_many(
    # #     where={'id': 1}

    # # )
    # logToDelete = await prisma.log.delete_many(
    #     where={'summary': ''}

    # )

    ##### FINDS BATCHES #########
    # batches = await prisma.batch.find_many()
    # print(batches)
    # for batch in batches:
    #     print('\n\n\n _________________________________________________________ \n\n\n')
    #     print(batch)
    #     print('\n\n\n _________________________________________________________ \n\n\n')

    ##### DELETES BATCHES #########

    # batches = await prisma.batch.delete_many({})

    await prisma.disconnect()

if __name__ == '__main__':
    asyncio.run(main())
