from session.prismaHandler import prisma


async def init_message_index(indexID, userID, loadout):
        remote_index = await prisma.index.find_first(
                where = {
                'key' : indexID
                }
        )

        if remote_index:
                #create   index
                print('')



async def get_messages(userID, loadout):
    
        messages = {}

        conversations = await prisma.log.find_many(
                where={
                'SessionID': { 'contains': str(loadout) },
                }
        )

        for conversation in conversations:

                remote_messages = await prisma.message.find_many(
                        where={
                        'SessionID': { 'contains': str(conversation.SessionID) },
                        }
                )
                messages.update({conversation.SessionID:remote_messages})





