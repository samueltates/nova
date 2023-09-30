import asyncio
import json
import datetime 
from prisma import Prisma
from prisma import Json
from human_id import generate_id
import logging
logging.basicConfig()
prisma = Prisma()
import pytz
utc=pytz.UTC

async def clear_user_history(userID):
    await deleteLoadouts(userID)
    await deleteCartridges(userID)
    await deleteSummaries(userID)
    await deleteMessages(userID)

async def deleteSummaries(userID):
    summaries = await prisma.summary.delete_many(
        where = {'UserID' : userID,}
    )

async def deleteMessages(userID):
    messages = await prisma.message.delete_many(
        where = {'UserID' : userID,}
    )

async def deleteLoadouts(userID):
    loadouts = await prisma.loadout.delete_many(
        where = {'UserID' : userID,}
    )

async def deleteCartridges(userID):
    cartridges = await prisma.cartridge.delete_many(
        where = {'UserID' : userID,}
    )

async def findSummaries(userID, epoch = None, summarised = None):
    summaries = await prisma.summary.find_many(
                where = {'UserID' : userID}
    )

    latest_summaries = []
    summary_by_id = {}
    counter = 0
    for summary in summaries:
        id = summary.id
        blob = json.loads(summary.json())['blob']
        # print(blob)
        for key, val in blob.items():
            if 'summarised' in val :
                if not val['summarised']:
                    counter += 1
                    print(summary)
                    print('\n')
    print(counter)

    

                
async def sort_summaries(userID, epoch = None):
    summaries = await prisma.summary.find_many(
                where = {'UserID' : userID}
    )
    # print(len(summaries))
    
    # print(summaries)
    latest_summaries = []
    summary_by_id = {}
    for summary in summaries:
        id = summary.id
        # print(summary)
        # print('\n')
        obj = dict(summary.blob)
        for key, val in obj.items():
            if 'epoch' in val:
                if 'id' in val:
                    if val['id'] not in summary_by_id:
                        print('creating new ID record')
                        summary_by_id[val['id']] = []
                    summary_by_id[val['id']].append(summary)

    for id in summary_by_id:
        print(id)
        # print (summary_by_id[0]['title'])
        print(len(summary_by_id[id]))
        saved = False
        for summary in summary_by_id[id]:
            if saved == False:
                saved = True
                print('saved ' + str(summary.id))
            else:
                delete = await prisma.summary.delete(
                    where={'id': summary.id}
                )
                print('deleted ' + str(summary.id))
                


    




                # if epoch != None:
                #     if val['epoch'] == epoch:
                #         print(val)
                #         print('\n')
                # else:
                #     print(val)
                #     print('\n')
                # print(str(val['epoch']) + ' ' + str(val['summarised']))
                # print(val['summarised'])
    #             # print('found one')
    #             # if val['epoch'] == 1:
    #             #     latest_summaries.append(summary)
    #             # val['summarised'] = True
    #             # updateSummary = await prisma.summary.update(
    #             #     where={'id': id},
    #             #     data={'blob': Json(summary)}
    #             # )

        
    #             # latest_summaries.append(summary)

    #     # if 'summarised' in summary.blob:
    #     #     if summary.blob['summarised'] == True:
    #     #         pass
    #     # # print(summary)
    #     # # if 'epoch' in summary.blob:
    #     # for key, val in summary.blob.items():
    #     #     print(val)
    #     #     if val['epoch'] == 0:
    #     #         print('found one')
    #     #         latest_summaries.append(summary)

    #     # # latest_summaries.append(summary)
    # # for summary in latest_summaries:
    #     # print(summary)
    # # print(len(latest_summaries))
    
async def find_logs(userID):
    logs = await prisma.log.find_many(
        where = {'UserID' : userID,
                 'id': {'gt': 3000}
                 }
    )
    print(logs)
    print('\n')
    for log in logs:
        print(log)
        print('\n')


async def findMessages(userID):
    messages = await prisma.message.find_many(
        where = {
            'UserID' : userID,
            # 'id': {'lt': 1000}     
                 }
    )
    for message in messages:
        # print('\n')
        if message.summarised == False:
            print(message)
            # print('not summarised')


async def find_and_delete_messages():
    messages = await prisma.message.find_many(
        where = {'UserID' : '108238407115881872743',}
    )
    for message in messages:
        if message.id < 5286:
            await prisma.message.delete(
                where={'id': message.id}
            )
        


async def findMessages_set_unsummarised(userID):
    messages = await prisma.message.find_many(
        where = {'UserID' : userID,
                # 'id' :{'lt': 1500}
                 }

    )
    # print(messages)
    
    message_counter = 0
    for message in messages:
        updatedMessage = await prisma.message.update(
            where={'id': message.id},
            data={'summarised': False}
        )
        # print(updatedMessage)
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
 
async def findCartridges(userID = None):

    if userID == None:
        cartridges = await prisma.cartridge.find_many()
    else:
        cartridges = await prisma.cartridge.find_many(
            where = {'UserID' :userID}

        )

    print(cartridges)
    
    # lastCart = cartridges[-1]
    # for cartridge in cartridges:
    # await prisma.cartridge.delete_many(
    #     where = {'UserID' : '110327569930296986874',}
    # )
    # for each in cartridges:
    #     print(each)
    # print(cartridges)

async def editCartridge(userID):
    cartridges = await prisma.cartridge.find_many(
        where = {'UserID' : userID}
    ) 
    for cartridge in cartridges:
        blob = json.loads(cartridge.json())['blob']
        # if 'index' in blob:
        #     await
        for key, val in blob.items():
            val['enabled'] = True
            updatedCartridge = await prisma.cartridge.update(
                where={'id': cartridge.id},
                data={ 
                    'key': key,
                    'blob': Json(blob)}
            )

async def portIndexesFromCartridges(userID):


    ##gets cartridges
    cartridges = await prisma.cartridge.find_many(
        where = {'UserID' : userID}
    ) 

    ##makes list of keep / stay
    keep_cartridges = []
    delete_cartridges = []

    #cycles through
    for cartridge in cartridges:
        blob = json.loads(cartridge.json())['blob']
        # print(blob)
        doc_store = ''
        index_store = ''
        vector_store = ''

        #cycles through keep, adds to delete if already there
        for cart in keep_cartridges:
            if cart == cartridge.key:
                delete_cartridges.append(cartridge)
                break
            else :
                keep_cartridges.append(cartridge.key)
        for key, value in blob.items():
            if 'index' in value:
                print('index found' ) 
                ##gets vector store
                if 'docstore' in value['index']:
                    print(value['index']['docstore'])
                    docstore = value['index']['docstore']
                if 'index_store' in value['index']:
                    print(value['index']['index_store'])
                    index_store = value['index']['index_store']
                if 'vector_store' in value['index']:
                    print(value['index']['vector_store'])
                    vector_store = value['index']['vector_store']
                # continue
                index_key = generate_id()
                index_key = str(index_key)
                index = await prisma.index.create(
                    data={
                        'UserID': userID,
                        'key': index_key,
                        'docstore': Json(docstore),
                        'index_store': Json(index_store),
                        'vector_store': Json(vector_store),
                    }
                )
                print(index)
                ##deltes blob replaces with key
                del value['index']
                value['index'] = index_key
                #updates cart
                updatedCartridge = await prisma.cartridge.update(
                    where={'id': cartridge.id},
                    data={
                        # 'key': key,
                        'blob': Json(blob)}
                )
                print(updatedCartridge)

    #deletes unused cartridges
    for cartridge in delete_cartridges:
        await prisma.cartridge.delete(
            where={'id': cartridge.id}
        )

async def findIndexes(userID):
    indexes = await prisma.index.find_many(
        where = {'UserID' : userID}
    ) 
    print(indexes)

async def deleteDuplicateCartridges(UserID):

    ##gets cartridges
    cartridges = await prisma.cartridge.find_many(
        where = {'UserID' : UserID}
    ) 

    ##makes list of keep / stay
    keep_cartridges = []
    delete_cartridges = []

    for cartridge in cartridges:
        blob = json.loads(cartridge.json())['blob']
        
        #cycles through keep, adds to delete if already there

        keep = True

        for key, val in blob.items():

            for cart in keep_cartridges:
                if 'label' in val and 'label' in cart and cart['label'] == val['label']:
                    print('found duplicate ' + val['label'])
                    delete_cartridges.append(cartridge)
                    keep = False
                    break
            if keep:
                keep_cartridges.append(val)

    #deletes unused cartridges
    for cartridge in delete_cartridges:
        await prisma.cartridge.delete(
            where={'id': cartridge.id}
        )



            


async def editCartridgeKeys(UserID):
    cartridges = await prisma.cartridge.find_many(
        where = {'UserID' : UserID}
    ) 
    for cartridge in cartridges:
        blob = json.loads(cartridge.json())['blob']

        if cartridge.key == '':

            for key, val in blob.items():
                if 'key' in val and val['key'] != '':
                    update = await prisma.cartridge.update(
                        where={'id': cartridge.id},
                        data={'key': key}
                    )

                else :
                    newKey = generate_id()
                    val['key'] = newKey
                    update = await prisma.cartridge.update(
                        where={'id': cartridge.id},
                        data={'key': key,
                            'blob': Json({key:val})}
                    )
        else:
            for key, val in blob.items():
                if 'key' not in val or val['key'] == '':
                    val['key'] = cartridge.key
                    update = await prisma.cartridge.update(
                        where={'id': cartridge.id},
                        data={'blob': Json({key:val})}
                    )

async def updateIndex(userID = None):
    cartridges = await prisma.cartridge.find_many(
            where = {'UserID' :userID}
        )
    
    for cartridge in cartridges:
        for key, val in cartridge.blob.items():
            if 'key' not in val or val['key'] == '':
                val['key'] = cartridge.key
                update = await prisma.cartridge.update(
                    where={'id': cartridge.id},
                    data={'blob': Json({key:val})}
                )


    

# async def deleteCartridges():
#     cartridges = await prisma.cartridge.delete_many(
#         where = {'UserID' : 'notSet'}
#     )
#     print(cartridges)

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

async def findLogs(userID):
       # and sets to true if they're too long
    logs = await prisma.log.find_many(
        where = {'UserID' : userID}

    )
    for log in logs:
        print(log)
        print('\n')

async def find_messages(userID):
    messages = await prisma.message.find_many(
        where = {
            'UserID' : userID,
            'id': {'gt': 3000}     
            }
    )
    for message in messages:
        print(message)
        print('\n')
    
async def update_summaries_for_testing(userID):
    summaries = await prisma.summary.find_many(
        where = {
            'UserID' : userID,
            }
    )
    for summary in summaries:

        # print(summary)
        blob = json.loads(summary.json())['blob']
        # print(blob)
        for key, val in blob.items():
            # epoch = int(val['epoch'])
            # if epoch == 2:
            #     val['summarised'] = False
            #     update = await prisma.summary.update(
            #         where={'id': summary.id},
            #         data={'blob':Json({key: val})}
            #     )
            #     print(update)
            # if epoch > 2:
            delete = await prisma.summary.delete(
                where={'id': summary.id},
            )

async def find_users():
    users = await prisma.user.find_many(
    )
    for user in users:

        messages = await prisma.message.find_many(
            where = {'UserID' : user.UserID}
        )
        print (len(messages))
        print(user)
        print('\n')

async def find_messages_after(gt):
    messages = await prisma.message.find_many(
        where = {
                'id': {'gt': gt}     
                }
    )
    for message in messages:
        print(message)
        print('\n')

async def delete_summaries_in_range():
    summaries = await prisma.summary.find_many(
        where = {
                'id': {'gt': 14000, 'lt': 14100
                       } 


                }
    )
    for summary in summaries:
        delete = await prisma.summary.delete(
            where={'id': summary.id}
        )
        print(delete)

async def get_daily_messages_report():
    # get the current date
    today = datetime.date.today()

    # query the messages from today
    messages_today = await prisma.message.find_many(
        where={'timestamp': {'gte': today.strftime('%Y-%m-%d')}}
    )

    print(f'Total messages for today: {len(messages_today)}')

    # get unique user IDs from the messages
    user_ids = set([message.UserID for message in messages_today])

    # query and print messages per user
    for user_id in user_ids:
        user_messages = await prisma.message.find_many(
            where={'timestamp': {'gte': today.strftime('%Y-%m-%d')}, 'UserID': user_id}
        )

        print(f'Messages from UserID {user_id} today: {len(user_messages)}')

    return

async def get_messages_report(start_date, end_date, exclude_uuid):
    # date range
    date_range = [start_date + datetime.timedelta(days=x) for x in range((end_date-start_date).days + 1)]

    for date in date_range:
        # query the messages from the date
        messages = await prisma.message.find_many(
            where={'timestamp': {'gte': date.strftime('%Y-%m-%d'), 'lt': (date + datetime.timedelta(days=1)).strftime('%Y-%m-%d')}}
        )

        print(f"Total messages for {date.strftime('%Y-%m-%d')}: {len(messages)}")

        # get unique user IDs from the messages
        user_ids = set([message.UserID for message in messages if message.UserID != exclude_uuid])

        # query and print messages per user
        for user_id in user_ids:
            user_messages = await prisma.message.find_many(
                where={'timestamp': {'gte': date.strftime('%Y-%m-%d'), 'lt': (date + datetime.timedelta(days=1)).strftime('%Y-%m-%d')}, 'UserID': user_id}
            )

            print(f"Messages from UserID {user_id} on {date.strftime('%Y-%m-%d')}: {len(user_messages)}")

    return

async def get_messages_report_aggregate(start_date, end_date, exclude_uuid):
    # date range
    date_range = [start_date + datetime.timedelta(days=x) for x in range((end_date-start_date).days + 1)]

    for date in date_range:
        # query the messages from the date
        messages = await prisma.message.find_many(
            where={'timestamp': {'gte': date.strftime('%Y-%m-%d'), 'lt': (date + datetime.timedelta(days=1)).strftime('%Y-%m-%d')}}
        )

        # Initialize dictionaries for logged in and guest users for the day
        logged_in_users, guest_users = {}, {}

        # get unique user IDs from the messages
        user_ids = set([message.UserID for message in messages if message.UserID != exclude_uuid])

        # query and process messages per user
        for user_id in user_ids:
            user_messages = await prisma.message.find_many(
                where={'timestamp': {'gte': date.strftime('%Y-%m-%d'), 'lt': (date + datetime.timedelta(days=1)).strftime('%Y-%m-%d')}, 'UserID': user_id}
            )

            # count messages only for users with more than one message
            if len(user_messages) > 1:
                if 'guest' in user_id:
                    guest_users[user_id] = len(user_messages)
                else:
                    logged_in_users[user_id] = len(user_messages)

        print(f"Date: {date.strftime('%Y-%m-%d')}")
        print(f'Logged in users ({len(logged_in_users)}): Message total ({sum(logged_in_users.values())})')
        print(f'Guests ({len(guest_users)}): Message total ({sum(guest_users.values())})')

    return


async def retrieve_logs_and_messages():
    messages = await prisma.message.find_many(
        where={'SessionID': {'contains': '7531ab40afd82ba4'}},
    )
    message_data = [{'id': message.id, 'key': message.key, 'SessionID': message.SessionID, 'UserID': message.UserID, 'name': message.name, 'timestamp': message.timestamp, 'body': message.body, 'batched': message.batched, 'summarised': message.summarised, 'minimised': message.minimised, 'muted': message.muted, 'blob': message.blob} for message in messages]

    with open('messages_backup.json', 'w') as f:
        json.dump(message_data, f)

async def write_recovered_messages():
    with open('messages_backup.json', 'r') as f:
        messages_from_backup = json.load(f)

    for message in messages_from_backup:

        await prisma.message.create(
            data={
                'id': message['id'],
                'key': message['key'],
                'SessionID': message['SessionID'],
                'UserID': message['UserID'],
                'name': message['name'],
                'timestamp': message['timestamp'],
                'body': message['body'],
                'batched': message['batched'],
                'summarised': message['summarised'],
                'minimised': message['minimised'],
                'muted': message['muted'],
                'blob': Json(message['blob']),
            }
        )

async def delete_logs_and_messages():
    messages = await prisma.message.find_many(
        where={'SessionID': {'contains': '7531ab40afd82ba4'}},
    )
    sessions = {}
    for message in messages:
        if message.SessionID not in sessions:
            sessions[message.SessionID] = []
        sessions[message.SessionID].append(message)

    sessions_with_one_message = 0
    sessions_with_more_than_one_message = 0
    for key, val in sessions.items():
        # print('new session')
        if len(val) <= 1:
            # print(val)
            sessions_with_one_message += 1
            # carpark_message = await prisma.message.update(
            #     where={'id': val[0].id},
            #     data={'SessionID': 'Carpark message'}
            # )
        else:
            sessions_with_more_than_one_message += 1
        
    print(f'Sessions with one message: {sessions_with_one_message}')
    print(f'Sessions with more than one message: {sessions_with_more_than_one_message}')

async def delete_summary_with_content():
    summaries = await prisma.summary.find_many(
    )

    for summary in summaries:
        blob = json.loads(summary.json())['blob']
        for key, val in blob.items():
            # print(val)
            if 'body' in val:
                if 'B-roll' in val['body']:
                    # print(summary)
                    delete = await prisma.summary.delete(
                        where={'id': summary.id}
                    )
            if 'Keywords' in val:
                if 'B-roll' in val['Keywords']:
                    # print(summary)
                    delete = await prisma.summary.delete(
                        where={'id': summary.id}
                    )
            if 'title' in val:
                if 'B-roll' in val['title']:
                    # print(summary)
                    delete = await prisma.summary.delete(
                        where={'id': summary.id}
                    )

async def add_nova_coin_to_user(userID):
    user = await prisma.user.find_first(
        where={'UserID': userID},
    )

    print(user)
    blob = json.loads(user.json())['blob']
    print(blob)
    blob['tokensUsed'] = -1500
    print(blob)
    update = await prisma.user.update(
        where={'id': user.id},
        data={'blob': Json(blob)}
    )
    print(update)

async def main() -> None:
    await prisma.connect()
    # await delete_summary_with_content()
    # await get_daily_messages_report()
    # await get_messages_report(datetime.date(2023, 7, 11), datetime.date(2023, 8, 11), '110327569930296986874')
    await get_messages_report_aggregate(datetime.date(2023, 9, 16), datetime.date(2023, 9, 29), '110327569930296986874')
    # await retrieve_logs_and_messages()
    # await write_recovered_messages()
    # await delete_logs_and_messages()
    # await delete_summaries_in_range()
    await find_users()
    # await clear_user_history( '108238407115881872743')
    # await findIndexes('108238407115881872743')
    # await findBatches()
    # await findLogSummaries()
    # await add_nova_coin_to_user('112850279287928312114')

    # await findLogs('108238407115881872743')
    # await findSummaries('110327569930296986874')
    # await findMessages('110327569930296986874')
    # await find_messages_after(5286)
    # await deleteMessages('108238407115881872743')
    # await deleteSummaries('110327569930296986874')
    # await deleteCartridges( '108238407115881872743')
    # await findMessages_set_unsummarised('110327569930296986874')
    # await update_summaries_for_testing('110327569930296986874')
    # await find_messages('110327569930296986874')
    # await findLogs('110327569930296986874')
    # await findCartridges()
    # await editCartridge('110327569930296986874')
    # await deleteDuplicateCartridges('110327569930296986874')
    # await portIndexesFromCartridges('110327569930296986874')

    # await findCartridges()

    # await findAndMarkLogsOver2k()
    # await find_and_delete_messages()
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
