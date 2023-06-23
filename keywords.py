import asyncio
import json
from appHandler import websocket
from prismaHandler import prisma
from sessionHandler import novaConvo, available_cartridges
from debug import eZprint

SKIP_KEYS = {'key', 'overview', 'timestamp', 'first-doc', 'last-doc', 'body', 'title', 'meta', 'epoch', 'sourceIDs', 'summarised', 'keywords', 'end', 'start', 'Participants', 'Session ID', 'sources', 'timeRange', 'end line', 'start line'}

summaries_available = {}
keywords_available = {}
notes_available = {}

async def get_keywords_from_summary(convoID, cartKey, cartVal, loadout = None):

    eZprint('getting keywords for ' + convoID + ' ' + cartKey)
    userID = novaConvo[convoID]['userID']
    if 'blocks' not in cartVal:
        cartVal['blocks'] = {}
    cartVal['state'] = 'loading'
    payload = { 'key': cartKey,
               'fields': {
                'state': cartVal['state']
                    },
            'loadout' : loadout 
                    }
    await  websocket.send(json.dumps({'event':'updateCartridgeFields', 'payload':payload})) 

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
        for key, val in blob.items():
            if 'summarised ' not in val or val['summarised'] == False:
                # print(summary)
                if userID+convoID not in summaries_available:
                    summaries_available[userID+convoID+str(loadout)] = []
                summaries_available[userID+convoID+str(loadout)].append({key:val})
                keywords = val['keywords']
                ## creates list for keyword
                for keyword in keywords:
                    if keyword not in keywords_available:
                        keywords_available[userID+convoID+str(loadout)][keyword] = []
                    keywords_available[userID+convoID+str(loadout)][keyword].append({'title':val['title'], 'body':val['body'],'key':summary.key,'type': 'summary', 'active': False})
                
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
                        notes_available[userID+convoID+str(loadout)][key].append({'line':val[key], 'timestamp': val['timestamp'], 'key':summary.key, 'active': False, 'type': 'summary'} )
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
                                        notes_available[userID+convoID+str(loadout)][subSubKey].append({'line':subSubVal, 'timestamp':val['timestamp'], 'key':summary.key,'type': 'summary', 'active': False})

    cartVal['blocks']['keywords'] = []
    for keyword in keywords_available[userID+convoID+str(loadout)]:
        cartVal['blocks']['keywords'].append({'keyword': keyword, 'active': False, 'summaries': keywords_available[userID+convoID+str(loadout)][keyword]})

    cartVal['state'] = ''
    payload = { 'key': cartKey,
               'fields': {
                'state': cartVal['state'],
                'blocks': cartVal['blocks']
                        }}
    # print('notes')
        
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
    payload = { 'key': cartKey,
               'fields': {
                'state': cartVal['state'],
                'blocks': cartVal['blocks']
                        },
                    'loadout' : loadout
                        }
    
    await  websocket.send(json.dumps({'event':'updateCartridgeFields', 'payload':payload})) 


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
            print(key)
            if key == keyword:
                for summary in val:
                    print(summary['title'])
                    summary['active'] = True
                    if summary not in summaries_to_return:
                        print('adding summary to return')
                        summaries_to_return.append(summary)
                        print('adding summary to summaries available')
                        print(summary['key'])
                        # if 'blocks' not in cartVal:
                        #     cartVal['blocks'] = {}
                        # cartVal['blocks'].append({'title':summary['title'], 'body':summary['body']})
                        # if userID+convoID in summaries_available:
                        #     summaries_available[userID+convoID+str(loadout)] = {}
                        # summaries_available[userID+convoID+str(loadout)][summary['summaryKey']] = summary

        if user_requested:
            payload = { 'content': summaries_to_return, 'source': 'keyword'}    
            await  websocket.send(json.dumps({'event':'send_preview_content', 'payload':payload}))  
        return summaries_available[userID+convoID+str(loadout)]






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