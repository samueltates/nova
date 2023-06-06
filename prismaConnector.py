import asyncio
import json
from datetime import datetime
from prisma import Prisma
from prisma import Json
from human_id import generate_id
import logging
logging.basicConfig()
prisma = Prisma()
import pytz
utc=pytz.UTC

async def deleteSummaries():
    summaries = await prisma.summary.delete_many(
        where = {'UserID' : '110327569930296986874',}
    )

async def findSummaries():
    summaries = await prisma.summary.find_many(
                where = {'UserID' : '110327569930296986874'}

    )

    
    # print(summaries)
    latest_summaries = []
    for summary in summaries:
        id = summary.id
        summary = dict(summary.blob)
        for key, val in summary.items():
            if 'epoch' in val:
                print(val)
                print('found one')
                # if val['epoch'] == 1:
                #     latest_summaries.append(summary)
                # val['summarised'] = True
                # updateSummary = await prisma.summary.update(
                #     where={'id': id},
                #     data={'blob': Json(summary)}
                # )

        
                # latest_summaries.append(summary)

        # if 'summarised' in summary.blob:
        #     if summary.blob['summarised'] == True:
        #         pass
        # # print(summary)
        # # if 'epoch' in summary.blob:
        # for key, val in summary.blob.items():
        #     print(val)
        #     if val['epoch'] == 0:
        #         print('found one')
        #         latest_summaries.append(summary)

        # # latest_summaries.append(summary)
    # for summary in latest_summaries:
        # print(summary)
    # print(len(latest_summaries))
    


async def findMessages():
    messages = await prisma.message.find_many(
        where = {'UserID' : '110327569930296986874',}

    )
    print(messages)


async def findMessages_set_unsummarised():
    messages = await prisma.message.find_many(
        where = {'UserID' : '110327569930296986874',}

    )
    # print(messages)
    
    message_counter = 0
    for message in messages:
        updatedMessage = await prisma.message.update(
            where={'id': message.id},
            data={'summarised': False}
        )
        print(updatedMessage)
        # message_counter += 1
        # if message_counter > 500:
        #     break

    # startDate = datetime(2023,4,1)
    # startDate = utc.localize(startDate)
    # endDate = datetime(2023,4,30)
    # endDate = utc.localize(endDate)
    # messages_in_range = []
    # for message in messages:
    #     timestamp = message.timestamp
    #     # print(timestamp)
    #     format = '%Y-%m-%dT%H:%M:%S.%fz'

    #     date = datetime.strptime(timestamp, format)

    #     if date > startDate and date < endDate:
    #         messages_in_range.append(message)

    # print(messages_in_range)
    # print(len(str(messages)))

async def findUsers():
    users = await prisma.user.find_many(
        where = {'name' : 'Samuel'}

    )
    print(users)
 
async def findCartridges():
    cartridges = await prisma.cartridge.find_many(
        where = {'UserID' : 'guest'}

    )

    
    # lastCart = cartridges[-1]
    # for cartridge in cartridges:
    # await prisma.cartridge.delete_many(
    #     where = {'UserID' : '110327569930296986874',}
    # )
    for each in cartridges:
        print(each)
    # print(cartridges)

async def editCartridge():
    cartridge = await prisma.cartridge.find_first(
        where = {'userID' : 'guest'}

    )

async def deleteCartridges():
    cartridges = await prisma.cartridge.delete_many(
        where = {'UserID' : 'notSet'}
    )
    print(cartridges)

async def portUser():

    ###CLEARING ALL RECORDS OF THAT USER
    deleteLogs = await prisma.user.delete_many(
        where={'UserID': '110327569930296986874'},   
    )
    deleteCartridges = await prisma.cartridge.delete_many(
        where={'UserID': '110327569930296986874'},
    )
    deleteMessages = await prisma.message.delete_many(
        where={'UserID': '110327569930296986874'},
    )

    deleteBatches = await prisma.batch.delete_many(
        where={'UserID': '110327569930296986874'},
    )

    deleteSummary = await prisma.summary.delete_many(
        where={'UserID': '110327569930296986874'},
    )

    deleteSession = await prisma.session.delete_many(
        where={'UserID': '110327569930296986874'},
    )




    updateLogs = await prisma.log.update_many(
        where={'UserID': '108238407115881872743'},
        data={'UserID': '110327569930296986874'}
    )

    updateMessages = await prisma.message.update_many(
        where={'UserID': '108238407115881872743'},
        data={'UserID': '110327569930296986874'}
    )

    updateBatches = await prisma.batch.update_many(
        where={'UserID': '108238407115881872743'},
        data={'UserID': '110327569930296986874'}
    )
    
    updateSummary = await prisma.summary.update_many(
        where={'UserID': '108238407115881872743'},
        data={'UserID': '110327569930296986874'}
    )

    updateSession = await prisma.session.update_many(
        where={'UserID': '108238407115881872743'},
        data={'UserID': '110327569930296986874'}
    )

    updateCartridges = await prisma.cartridge.update_many(
        where={'UserID': '108238407115881872743'},
        data={'UserID': '110327569930296986874'}
    )


    # delete = await prisma.cartridge.delete_many(

#     users
async def findLogSummaries():
    logs = await prisma.log.find_many(
        where = {'UserID' : '110327569930296986874',}
    )
    for log in logs:
        print(f'{log.summary}')


async def findBatches():
    batches = await prisma.batch.find_many(
        where = {'UserID' : '110327569930296986874',}
    )
    for batch in batches:
        print(f'{batch}')

async def findAndMarkLogsOver2k():
       # and sets to true if they're too long
    logs = await prisma.log.find_many(           
        where = {'batched' : False,}  
)

    unsumarisedLogMessages= []
    logsToBatch = []
    for log in logs:
        messages = await prisma.message.find_many(
        where = {'SessionID' : log.SessionID,}
        )
        unsumarisedLogMessages.append(messages)
        print(len(str(messages)))
        logID = log.id
        # print( 'logID ' + str(logID))
        if len(str(messages)) > 20000:
            print('logID ' + str(logID))
            logsToBatch.append(log)
        
        for log in logsToBatch:
            updatedLog = await prisma.log.update(
                where={'id': log.id},
                data={'batched': True,
                    'summary': 'fix me'
                    }
                # where={'SessionID': '7dcd4d0f753916c0ba0a8d91c53c97af1ab2f1f1'},
                # data={'batched': True,}
            )
            print(log)

async def findLogs():
       # and sets to true if they're too long
    logs = await prisma.log.find_many(
        where = {'UserID' : '108238407115881872743',}

    )
    print(logs)

    
async def main() -> None:
    await prisma.connect()
    # await findBatches()
    # await findLogSummaries()
    # await findLogs()
    await deleteSummaries()
    await findMessages_set_unsummarised()
    # await findCartridges()
    # await findAndMarkLogsOver2k()
    # await findUsers()
    # await portUser()
    # await deleteCartridges()

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
