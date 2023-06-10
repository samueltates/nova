import asyncio
import json
from appHandler import websocket
from prismaHandler import prisma
from sessionHandler import novaConvo
from debug import eZprint

SKIP_KEYS = {'key', 'overview', 'timestamp', 'first-doc', 'last-doc', 'body', 'title', 'meta', 'epoch', 'sourceIDs', 'summarised', 'keywords'}

keywords_available = {}
notes_available = {}

async def get_summary_keywords(convoID, cartKey, cartVal):

    eZprint('getting keywords for ' + convoID + ' ' + cartKey)
    userID = novaConvo[convoID]['userID']

    cartVal['state'] = 'loading'
    payload = { 'key': cartKey,
               'fields': {
                'state': cartVal['state']
                    }}
    await  websocket.send(json.dumps({'event':'updateCartridgeFields', 'payload':payload})) 

    if userID+convoID not in keywords_available:
        keywords_available[userID+convoID] = {}

    if userID+convoID not in notes_available:
        notes_available[userID+convoID] = {}

    summaries = await prisma.summary.find_many(
        where={ 
            "UserID": userID
        },
    )

    # print(summaries)

    for summary in summaries:
        blob = json.loads(summary.json())['blob']
        for key, val in blob.items():
            if val['summarised'] == False:
                # # print(summary)
                keywords = val['keywords']
                ## creates list for keyword
                for keyword in keywords:
                    if keyword not in keywords_available:
                        keywords_available[userID+convoID][keyword] = []
                    keywords_available[userID+convoID][keyword].append({'title':val['title'], 'body':val['body'],'sourceID':summary.id})
                
                # await sort_layers_by_key(val)

                for key in val.keys():
                    if key in SKIP_KEYS: 
                        continue
                    #creates list for  note
                    if key not in notes_available[userID+convoID]:
                        print('creating record for ' + key+ '\n')
                        notes_available[userID+convoID][key] = []
                    if isinstance(val[key], str):
                        ## if its base then add it to the list
                        print('adding line ' + val[key] + ' to ' + key + '\n')
                        notes_available[userID+convoID][key].append({'line':val[key], 'timestamp': val['timestamp'], 'sourceID':summary.id} )
                    elif isinstance(val[key], dict):
                        ## if its a dict then add all the sub keys
                        ## could this be 'recusirve'?
                        for subKey, subVal in val[key].items():
                            if subKey in SKIP_KEYS:
                                continue
                            if subKey not in notes_available[userID+convoID]:
                                print('creating record for ' + subKey + '\n')
                                notes_available[userID+convoID][subKey] = []
                            if isinstance(subVal, str):
                                print('adding sub line ' + subVal + ' to ' + subKey+ '\n' )
                                notes_available[userID+convoID][subKey].append({'line':subVal, 'timestamp':val['timestamp'], 'sourceID':summary.id})
                            elif isinstance(subVal, dict):
                                for subSubKey, subSubVal in subVal[key].items():
                                    if subSubKey in SKIP_KEYS:
                                        continue
                                    if subSubKey not in notes_available:
                                        print('creating record for ' + subSubKey + '\n')
                                        notes_available[userID+convoID][subSubKey] = []
                                    if isinstance(subSubVal, str):
                                        notes_available[userID+convoID][subSubKey].append({'line':subSubVal, 'timestamp':val['timestamp'], 'sourceID':summary.id})

    keyword_string = ''
    for keyword in keywords_available[userID+convoID]:
        keyword_string += keyword + ', '

    if 'blocks' not in cartVal:
        cartVal['blocks'] = []
    cartVal['blocks'].append({'keywords': keyword_string})
    cartVal['state'] = ''
    payload = { 'key': cartKey,
               'fields': {
                'state': cartVal['state'],
                'blocks': cartVal['blocks']
                        }}
    
    await  websocket.send(json.dumps({'event':'updateCartridgeFields', 'payload':payload})) 



    #     for records in keywords_available[userID+convoID][keywords]:
    #         print(records['title'])
      
    # print('notes')
    # for key, val in notes_available[userID+convoID].items():
    #     print('--'+key) 
    #     for note in val:
    #         print(note['line'] + ' from ' + str(note['sourceID']) + ' at ' + str(note['timestamp']))

    

    
# async def sort_layers_by_key(object):
#     for key in object.keys():
#             if key in SKIP_KEYS: 
#                 continue
#             print('key: ' + key + '\n')
#             #creates list for  note
#             if key not in notes_available:
#                 print('creating record for ' + key+ '\n')
#                 notes_available[key] = []
#             if isinstance(object[key], str):
#                 ## if its base then add it to the list
#                 print('adding line ' + object[key] + ' to ' + key + '\n')
#                 notes_available[key].append({'line':object[key], 'timestamp': object['timestamp'], 'key':object['key']} )
#             elif isinstance(object[key], dict):
#                 sort_layers_by_key(object[key])


async def main() -> None:
    await prisma.connect()
    eZprint('running main')
    # await get_keywords()

if __name__ == '__main__':
    asyncio.run(main())