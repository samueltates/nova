import asyncio
import json
from prisma import Prisma
from prisma import Json
from human_id import generate_id
import logging
logging.basicConfig()
prisma = Prisma()

async def findSummaries():
    summaries = await prisma.summary.find_many()
    print(summaries)


async def findMessages():
    messages = await prisma.message.find_many()
    print(messages)

async def findUsers():
    users = await prisma.user.find_many()
    print(users)
    
async def main() -> None:
    await prisma.connect()
    # await findSummaries()
    # await findMessages()
    await findUsers()
    ###### PRINTS MESSAGES#########
    # messages = await prisma.message.find_many()
    # print(messages)

    # ####### SCRAPES ALL DATABASE FROM SOURCE TO JSON#########
    # scrape = {'messages':[],'logs':[],'batches':[]}
    # messages = await prisma.message.find_many(
    #     where = {'SessionID' : '8fe6ef2a53c1378cf97884743765e66e22ebb3e2'},
    # )
    # print (messages)
    # for message in messages:
    #     messageObject ={
    #         "id": message.id,
    #         "SessionID": message.SessionID,
    #         "UserID": message.UserID,
    #         "name": message.name,
    #         "timestamp": message.timestamp,
    #         "body": message.body, 
    #     }
    #     # print (messageObject)
    #     scrape['messages'].append(messageObject)

    # logs = await prisma.log.find_many()
    # for log in logs:
    #     logObject ={
    #         "id": log.id,
    #         "SessionID": log.SessionID,
    #         "UserID": log.UserID,
    #         "date": log.date,
    #         "summary": log.summary,
    #         "body": log.body,
    #         "batched": log.batched,
    #     }
    #     scrape['logs'].append(logObject)

    # batches = await prisma.batch.find_many()

    # for batch in batches:
    #     batchObject ={
    #         "id": batch.id,
    #         "dateRange": batch.dateRange,
    #         "summary": batch.summary,
    #         "batched": log.batched,
    #         "UserID": batch.UserID,
    #     }
    #     scrape['batches'].append(batchObject)

    # with open("./scrape.json", "a") as scrapeJson:
    #     json.dump(scrape, scrapeJson)


    # cartridges = await prisma.cartridge.find_many()
    # for cartridge in cartridges:
    #     print(cartridge)
    # # #     # print(cartridge.id)
    # #     # print(cartridge.blob)
    # #     # val = list(cartridge.blob.values())[0]
    # #     # # subval = list(val.values())[0]
    # #     # print(val)
    # #     # print (val['label'])
    # #     # file = json.load(cartridge)
    # #     # print (file)
    # #     # for blob in cartridge['blob']:
    # #     #     print(blob)
    # #     # print(cartridges['blob']['id'])


#DELETES CARTRIDGES
    # delete = await prisma.cartridge.delete_many(
    #     where={'id': 72},
        
    # )
#     delete = await prisma.cartridge.delete_many(
#             where={'id': 69},
            
#         )

    # cartridges = json.load(open('./cartridges.json'))
    # cartridges = await prisma.cartridge.find_many()
    # print(cartridges)

##ADDS CARTRIDGES FROM JSON
    # for cartridge in cartridges:
    #     newCartridge = await prisma.cartridge.create(
    #         data={
    #             "UserID" : "sam",
    #             "blob": Json({generate_id() : cartridges[cartridge]})
    #         }
    #     )
        # print({cartridge : cartridges[cartridge]})

    ##### pushes DB #########

    # dbJson = json.load(open('./scrape.json'))
    # for message in dbJson['messages']:
    #     print(message)
    #     print('\n\n\n _________________________________________________________ \n\n\n')
    #     message = await prisma.message.create(
    #         data=message
    #     )
    # for log in dbJson['logs']:  
    #     print(log)  
    #     print('\n\n\n _________________________________________________________ \n\n\n')
    #     log = await prisma.log.create(
    #         data=log
    #     )               
    # for batch in dbJson['batches']:
    #     print(batch)
    #     print('\n\n\n _________________________________________________________ \n\n\n')
    #     batch = await prisma.batch.create(
    #         data=batch
    #     )

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

    ##### FINDS LOG SETS BATCHED TO FALSE #########

    ## and sets to true if they're too long
#     logs = await prisma.log.find_many(           
#         where = {'batched' : False,}  
# )

#     unsumarisedLogMessages= []
#     logsToBatch = []
#     for log in logs:
#         messages = await prisma.message.find_many(
#         where = {'SessionID' : log.SessionID,}
#         )
#         unsumarisedLogMessages.append(messages)
#         print(len(str(messages)))
#         logID = log.id
#         print( 'logID ' + str(logID))
#         if len(str(messages)) > 20000:
#             print('logID ' + str(logID))
#             logsToBatch.append(log)


#     print(logsToBatch)

    # print(unsumarisedLogMessages)


    # for log in logsToBatch:
    #     updatedLog = await prisma.log.update(
    #         where={'id': log.id},
    #         data={'batched': True,
    #               'summary': 'fix me'
    #               }
    #         # where={'SessionID': '7dcd4d0f753916c0ba0a8d91c53c97af1ab2f1f1'},
    #         # data={'batched': True,}
    #     )
    #     print(log)
    # #     print('\n\n\n _________________________________________________________ \n\n\n')

    ## FINDS LOG #########
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


    # #### DELETES MESSAGES #########

    # messages = await prisma.message.delete_many({})

    await prisma.disconnect()

if __name__ == '__main__':
    asyncio.run(main())
