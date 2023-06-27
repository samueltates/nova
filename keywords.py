import asyncio
import json
from appHandler import websocket
from cartridges import update_cartridge_field
from prismaHandler import prisma
from sessionHandler import novaConvo, available_cartridges, current_loadout
from debug import eZprint

SKIP_KEYS = {'key', 'overview', 'timestamp', 'first-doc', 'last-doc', 'body', 'title', 'meta', 'epoch', 'sourceIDs', 'summarised', 'keywords', 'end', 'start', 'Participants', 'Session ID', 'sources', 'timeRange', 'end line', 'start line', 'insights'}

summaries_available = {}
keywords_available = {}
notes_available = {}

async def get_keywords_from_summaries(convoID, cartKey, cartVal, client_loadout = None, target_loadout = None):

    eZprint('getting keywords for ' + convoID + ' ' + cartKey)
    userID = novaConvo[convoID]['userID']
    if 'blocks' not in cartVal:
        cartVal['blocks'] = {}

    cartVal['state'] = 'loading'
    cartVal['status'] = 'getting keywords'

    input = { 
        'cartKey': cartKey,
        'convoID': convoID,
        'fields': {
            'state': cartVal['state'],
            'status': cartVal['status']
            },
        'loadout' : client_loadout 
    }

    await update_cartridge_field(input, client_loadout, system=True)


    summaries = await prisma.summary.find_many(
        where={ 
            "UserID": userID
        },
    )

    if summaries == None:
        return

    loadout_candidates = []

    for candidate in summaries:
        # print(candidate.SessionID)
        splitID = candidate.SessionID.split('-')
        # print(splitID)
        if len(splitID) >= 2:
            if splitID[2] == target_loadout:
                # print('found loadout candidate')
                loadout_candidates.append(candidate)
        elif target_loadout  == None:
            # print('adding on a none loadout')
            loadout_candidates.append(candidate)

    keywords_available = {}
    notes_available = {}

    for summary in loadout_candidates:
        blob = json.loads(summary.json())['blob']
        epoch = 0
        for key, val in blob.items():
            # if 'summarised' not in val or val['summarised'] == False:
                # print(summary)
            if 'keywords' in val:
                keywords = val['keywords']
            ## creates list for keyword
                for keyword in keywords:
                    keyword = keyword.lower()
                    if keyword not in keywords_available:
                        keywords_available[keyword] = []
                    if 'epoch' in val:
                        epoch = val['epoch']
                    
                    keywords_available[keyword].append({'source':val['key'], 'epoch': epoch, 'summarised' : val['summarised']})
            
                for key in val.keys():
                    if key in SKIP_KEYS: 
                        continue
                    #creates list for  note
                    if key not in notes_available:
                        # print('creating record for ' + key+ '\n')
                        notes_available[key] = []
                    if isinstance(val[key], str):
                        ## if its base then add it to the list
                        # print('adding line ' + val[key] + ' to ' + key + '\n')
                        if 'epoch' in val:
                            epoch = val['epoch']
                        notes_available[key].append({'line':val[key], 'timestamp': val['timestamp'], 'key':summary.key, 'active': False, 'type': 'summary', 'epoch': epoch} )
                    elif isinstance(val[key], dict):
                        ## if its a dict then add all the sub keys
                        ## could this be 'recusirve'?
                        for subKey, subVal in val[key].items():
                            if subKey in SKIP_KEYS:
                                continue
                            if subKey not in notes_available:
                                # print('creating record for ' + subKey + '\n')
                                notes_available[subKey] = []
                            if isinstance(subVal, str):
                                # print('adding sub line ' + subVal + ' to ' + subKey+ '\n' )
                                notes_available[subKey].append({'line':subVal, 'key':summary.key,'active': False, 'type': 'summary'})

                                # notes_available[userID+convoID][subKey].append({'line':subVal, 'timestamp':val['timestamp'],'summaryKey':summary.key,'active': False})
                            elif isinstance(subVal, dict):
                                for subSubKey, subSubVal in subVal[key].items():
                                    if subSubKey in SKIP_KEYS:
                                        continue
                                    if subSubKey not in notes_available:
                                        # print('creating record for ' + subSubKey + '\n')
                                        notes_available[subSubKey] = []
                                    if isinstance(subSubVal, str):
                                        if 'epoch' in val:
                                            epoch = val['epoch']
                                        notes_available[subSubKey].append({'line':subSubVal, 'timestamp':val['timestamp'], 'key':summary.key,'type': 'summary', 'active': False, 'epoch': epoch})

    cartVal['blocks']['keywords'] = keywords_available
    cartVal['blocks']['insights'] = notes_available

    cartVal['state'] = ''
    cartVal['status'] = ''

    input = { 
        'cartKey': cartKey,
        'convoID': convoID,
        'fields': {
            'state': cartVal['state'],
            'status': cartVal['status'],
            'blocks': cartVal['blocks']
            },
        'loadout' : client_loadout 
    }
    await update_cartridge_field(input, client_loadout, system=True)

async def get_summary_from_keyword(key, convoID, cartKey, client_loadout = None, target_loadout= None, user_requested = False):

    sources_to_return = []

    if isinstance(key, dict):
        for keyword, sources in key.items():
            if isinstance(sources, list):
                for meta in sources:
                    print(meta)
                    source_val = await get_source_by_key(meta['source'], convoID, target_loadout)
                    for key, val in source_val.items():
                        val.update({'type': 'summary'})
                        sources_to_return.append(val)

    if user_requested:
        print('sending preview content')
        payload = { 'parent': {'title':key}, 'children': sources_to_return, 'source': 'keyword'}    
        await  websocket.send(json.dumps({'event':'send_preview_content', 'payload':payload}))  

async def get_summary_from_insight(object, convoID, cartKey,  client_loadout = None, target_loadout= None, user_requested = False):
    sources_to_return = []

    if 'key' in object:
        source_val = await get_source_by_key(object['key'], convoID, target_loadout)
        for key, val in source_val.items():
            val.update({'type': 'summary'})
            sources_to_return.append(val)

    if user_requested:
        print('sending preview content')
        payload = { 'parent': {'title':object['line']}, 'children': sources_to_return, 'source': 'insight'}    
        await  websocket.send(json.dumps({'event':'send_preview_content', 'payload':payload}))


async def get_message_by_key(id):
    print('getting message by key')
    message = await prisma.message.find_first(
        where={
        'id': id,
        }
    )
    if message == None:
        print('message not found')
        return False
    else :
        print('message found')
        print(message)
        message_json = json.loads(message.json())
        print(message_json)
        message_json.update({'type': 'message'})
        return message_json

async def get_source_by_key(key, convoID, client_loadout = None):
    print('getting source by key')
    print('loadout: ' + str(client_loadout) + ' current loadout: ' + str(current_loadout[convoID]))
    if client_loadout == current_loadout[convoID]:
        print('getting summary by key')
        if isinstance(key, str):
            print('key is string')
            summary = await prisma.summary.find_first(
                where={
                    'key': str(key)
                }
            )

        if isinstance(key, int):
            print('key is int')
            summary = await prisma.summary.find_first(
                where={
                    'id': int(key)
                }
            )

        summary = json.loads(summary.json())['blob']
        return summary



    #     for records in keywords_available[userID+convoID][keywords]:
    #         print(records['title'])

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