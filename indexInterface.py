from prismaHandler import prisma

async def get_messages(userID):
    messages = await prisma.message.find_many(
        where={
            'userID': userID
        }
    )
    return messages