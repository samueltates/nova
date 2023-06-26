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

async def get_keywords_from_summaries(convoID, cartKey, cartVal, loadout = None):

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
        'loadout' : loadout 
    }

    await update_cartridge_field(input, loadout, system=True)

    if userID+convoID not in keywords_available:
        keywords_available[userID+convoID+str(loadout)] = {}

    if userID+convoID not in notes_available:
        notes_available[userID+convoID+str(loadout)] = {}

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
            if splitID[2] == loadout:
                # print('found loadout candidate')
                loadout_candidates.append(candidate)
        elif loadout  == None:
            # print('adding on a none loadout')
            loadout_candidates.append(candidate)

    # print(summaries)
    # print(len(loadout_candidates))
    
    for summary in loadout_candidates:
        blob = json.loads(summary.json())['blob']
        epoch = 0
        for key, val in blob.items():
            # if 'summarised' not in val or val['summarised'] == False:
                # print(summary)
            if userID+convoID not in summaries_available:
                summaries_available[userID+convoID+str(loadout)] = []
            summaries_available[userID+convoID+str(loadout)].append({key:val})
            if 'keywords' in val:
                keywords = val['keywords']
            ## creates list for keyword
                for keyword in keywords:
                    if keyword not in keywords_available:
                        keywords_available[userID+convoID+str(loadout)][keyword] = []
                    if 'epoch' in val:
                        epoch = val['epoch']
                    
                    keywords_available[userID+convoID+str(loadout)][keyword].append({'title':val['title'], 'body':val['body'],'key':summary.key,'type': 'summary', 'active': False, 'epoch': epoch})
            
            # await sort_layers_by_key(val)

                for key in val.keys():
                    if key in SKIP_KEYS: 
                        continue
                    #creates list for  note
                    if key not in notes_available[userID+convoID+str(loadout)]:
                        # print('creating record for ' + key+ '\n')
                        notes_available[userID+convoID+str(loadout)][key] = []
                    if isinstance(val[key], str):
                        ## if its base then add it to the list
                        # print('adding line ' + val[key] + ' to ' + key + '\n')
                        if 'epoch' in val:
                            epoch = val['epoch']
                        notes_available[userID+convoID+str(loadout)][key].append({'line':val[key], 'timestamp': val['timestamp'], 'key':summary.key, 'active': False, 'type': 'summary', 'epoch': epoch} )
                    elif isinstance(val[key], dict):
                        ## if its a dict then add all the sub keys
                        ## could this be 'recusirve'?
                        for subKey, subVal in val[key].items():
                            if subKey in SKIP_KEYS:
                                continue
                            if subKey not in notes_available[userID+convoID+str(loadout)]:
                                # print('creating record for ' + subKey + '\n')
                                notes_available[userID+convoID+str(loadout)][subKey] = []
                            if isinstance(subVal, str):
                                # print('adding sub line ' + subVal + ' to ' + subKey+ '\n' )
                                notes_available[userID+convoID+str(loadout)][subKey].append({'line':subVal, 'key':summary.key,'active': False, 'type': 'summary'})

                                # notes_available[userID+convoID][subKey].append({'line':subVal, 'timestamp':val['timestamp'],'summaryKey':summary.key,'active': False})
                            elif isinstance(subVal, dict):
                                for subSubKey, subSubVal in subVal[key].items():
                                    if subSubKey in SKIP_KEYS:
                                        continue
                                    if subSubKey not in notes_available:
                                        # print('creating record for ' + subSubKey + '\n')
                                        notes_available[userID+convoID+str(loadout)][subSubKey] = []
                                    if isinstance(subSubVal, str):
                                        if 'epoch' in val:
                                            epoch = val['epoch']
                                        notes_available[userID+convoID+str(loadout)][subSubKey].append({'line':subSubVal, 'timestamp':val['timestamp'], 'key':summary.key,'type': 'summary', 'active': False, 'epoch': epoch})

    cartVal['blocks']['keywords'] = []
    for keyword in keywords_available[userID+convoID+str(loadout)]:
        cartVal['blocks']['keywords'].append({'keyword': keyword, 'active': False, 'summaries': keywords_available[userID+convoID+str(loadout)][keyword]})

        
    cartVal['blocks']['insights'] = []
    for key, val in notes_available[userID+convoID+str(loadout)].items():
        # print('--'+key) 
        line = ''
        lastline = ''
        for note in val:
            # print(note['line'])
            if note['line'] == lastline:
                continue
            line += str(note['line']) + '\n'
            lastline = note['line']
        cartVal['blocks']['insights'].append({'title': key, 'text' : line})
        # cartVal['blocks']['keywords_object']['insights_object'] = notes_available[userID+convoID+str(loadout)]

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
            'loadout' : loadout 
        }
        await update_cartridge_field(input, loadout, system=True)

async def get_summary_from_keyword(keyword, convoID, cartKey, loadout= None, user_requested = False):

    print('getting summary from keyword')
    if convoID not in novaConvo:
        return False

    if convoID not in available_cartridges:
        return False
    
    if cartKey in available_cartridges[convoID]:
        cartVal = available_cartridges[convoID][cartKey]

    userID = novaConvo[convoID]['userID']
    if userID+convoID+str(loadout) not in summaries_available:
        summaries_available[userID+convoID+str(loadout)] = {}
    summaries_to_return = []
    # print('keyword: ' + keyword + '\n')
    # print(keywords_available[userID+convoID+str(loadout)])


    if userID+convoID+str(loadout) in keywords_available:
        for key, val in keywords_available[userID+convoID+str(loadout)].items():
            # print(key)
            if key == keyword:
                for summary in val:
                    # print(summary['title'])
                    summary['active'] = True
                    if summary not in summaries_to_return:
                        # print('adding summary to return')
                        summary_object = await get_source_by_key(summary['key'], convoID, loadout)
                        for key, val in summary_object.items():
                            val.update({'type': 'summary'})
                            val.update({'key': summary['key']})
                            if 'sourceIDs' in val:
                                source_pointers = []
                                print('sourceIDs')
                                print(val['sourceIDs'])
                                for source in val['sourceIDs']:
                                    print(source)
                                    if 'epoch' in val and val['epoch'] > 1:
                                        source_val = await get_source_by_key(source, convoID, loadout)
                                        for key, val in source_val.items():
                                            print(val)
                                            source_pointers.append({key: val['title']})
                                    elif 'meta' in val and 'docID' in val['meta']:
                                        message_object = await get_message_by_key(source)
                                        print(message_object)
                                        name = ''
                                        if 'name' in message_object:
                                            name = message_object['name']
                                        body = ''
                                        if 'body' in message_object:
                                            body = message_object['body']
                                            source_pointers.append({key: {name + ' : '+ body}})
                                    val['sourceIDs'] = source_pointers
                                    summaries_to_return.append(val)
                        print('adding summary to summaries available')
                        print(summaries_to_return)

        if user_requested:
            print('sending preview content')
            payload = { 'content': summaries_to_return, 'source': 'keyword'}    
            await  websocket.send(json.dumps({'event':'send_preview_content', 'payload':payload}))  
        return summaries_available[userID+convoID+str(loadout)]


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

async def get_source_by_key(key, convoID, loadout = None):

    if loadout == current_loadout[convoID]:
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