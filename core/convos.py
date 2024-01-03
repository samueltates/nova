from datetime import datetime
import secrets
import json
import asyncio

from session.appHandler import websocket
from session.sessionHandler import novaConvo, novaSession, chatlog, available_convos, current_config, current_loadout
from session.prismaHandler import prisma
from core.loadout import update_loadout_field
from tools.debug import eZprint, eZprint_anything

DEBUG_KEYS = ['CONVOS'] 



async def get_loadout_logs(loadout, sessionID ):
    eZprint_anything(loadout, ['CONVO', 'INITIALISE'], message = 'loadout logs requested')
    ## finds logs connected to loadout
    await asyncio.sleep(.1)
    if sessionID not in novaSession:
        novaSession[sessionID] = {}
    
    if 'userID' not in novaSession[sessionID]:
        novaSession[sessionID]['userID'] = None
    
    userID = novaSession[sessionID]['userID']
    

    available_convos[sessionID] = []

    logs = None

    if (sessionID in current_config and 'shared' in current_config[sessionID] and current_config[sessionID]['shared'] or 'owner' in novaSession[sessionID] and novaSession[sessionID]['owner'] ) and loadout != None:
        eZprint('shared or owner', ['CONVO', 'INITIALISE'])
        eZprint_anything(loadout, ['CONVO', 'INITIALISE'], message = 'loadout in shared')
        logs = await prisma.log.find_many(
                where={ "SessionID": {'contains':str(loadout)} },
            )
        # print(logs)
    else:
        eZprint('not shared or owner or no loadout', ['CONVO', 'INITIALISE'])
        if userID:
            logs = await prisma.log.find_many(
                    where={ 
                        "UserID": userID, 
                        "SessionID": {'contains':str(loadout)} },
                    )
        # print (logs)
            
    # print(logs)
    if logs:
        for log in logs:
            splitID = log.SessionID.split('-')
        
            if len(splitID) >=2:
            #    
                session ={
                    'id': log.id,
                    'sessionID' : log.SessionID,
                    'convoID' : splitID[1],
                    'date' : log.date,
                    'summary':log.summary,
                }
                available_convos[sessionID].append(session)
            else:
                session ={
                    'id': log.id,
                    'sessionID' : log.SessionID,
                    'convoID' : splitID,
                    'date' : log.date,
                    'summary': log.summary,
                }
                available_convos[sessionID].append(session)
                # convos.append(splitID)

    await websocket.send(json.dumps({'event': 'populate_convos', 'payload': available_convos[sessionID]}))
    asyncio.create_task( populate_summaries(sessionID))

# async def check_convos(sessionID):
#     ## pass through the convos, check if messages are unsumarised, or if there are unsumarised messages in the convo
#     # if messages then if unsumarised -  

async def populate_summaries(sessionID):
    userID = novaSession[sessionID]['userID']
    DEBUG_KEYS.append('POPULATE_SUMMARY')
    eZprint('populating summaries', DEBUG_KEYS )
    eZprint_anything(available_convos[sessionID], DEBUG_KEYS, message='convos log')
    for log in available_convos[sessionID]:
        eZprint_anything(log, DEBUG_KEYS, message='each log')
        if log['summary'] == '':
            eZprint('summary is empty', DEBUG_KEYS)
            splitID = log['sessionID'].split('-')
            if len(splitID) > 1:
                splitID = splitID[1]
            try:
                remote_summaries_from_convo = await prisma.summary.find_many(
                    where = {
                        'UserID' : userID,
                        'SessionID' : splitID
                        }
                )
                if remote_summaries_from_convo:
                    eZprint_anything(remote_summaries_from_convo, DEBUG_KEYS, message  = 'summaries from convo with split ID')

                if not remote_summaries_from_convo:

                    remote_summaries_from_convo = await prisma.summary.find_many(
                    where = {
                        'UserID' : userID,
                        'SessionID' : log['sessionID']
                        }
                    )
                    eZprint_anything(remote_summaries_from_convo, DEBUG_KEYS, message  = 'summaries from convo without split id')
                    
                    # eZprint_anything(remote_summaries_from_convo, DEBUG_KEYS, message='found remote summary')
            except:
                eZprint('summary search failed')
                remote_summaries_from_convo = None
                
            summary = ''

            if remote_summaries_from_convo:
                eZprint_anything(remote_summaries_from_convo, DEBUG_KEYS, message='found remote summary')
                for summary in remote_summaries_from_convo:
                    eZprint(summary, DEBUG_KEYS, message= 'summary found')

                    summary = json.loads(summary.json())['blob']
                    for key, val in summary.items():
                        summary = val['title']
                    log['summary'] = summary

                    updated_log = await prisma.log.update(
                        where = {
                            'id' : log['id']
                            },
                        data = {
                            'summary' : summary
                        }
                    )
                    eZprint_anything(updated_log, DEBUG_KEYS, message = 'updated log')
                    await websocket.send(json.dumps({'event': 'update_convo_tab', 'payload': log}))

async def set_convo(requested_convoID, sessionID, loadout):
    
    userID = novaSession[sessionID]['userID']
    eZprint(requested_convoID+ ' requested convoID', ['CONVO', 'INITIALISE'])
    splitConvoID = requested_convoID.split('-')
    if len(splitConvoID) > 1:
        splitConvoID = splitConvoID[1]

    if sessionID in current_config and 'shared' in current_config[sessionID] and current_config[sessionID]['shared'] or novaSession[sessionID]['owner'] :

        try:
            remote_summaries_from_convo = await prisma.summary.find_many(
                where = {
                    'SessionID' : {'contains':splitConvoID}
                    }
            )

        except:
            remote_summaries_from_convo = None

        remote_messages_from_convo = await prisma.message.find_many(
            where = {
                'SessionID' : requested_convoID
                }
        )

    else:
        try:
            remote_summaries_from_convo = await prisma.summary.find_many(
                where = {
                    'UserID' : userID,
                    'SessionID' : {'contains':splitConvoID}
                    }
            )

        except:
            remote_summaries_from_convo = None

        remote_messages_from_convo = await prisma.message.find_many(
            where = {
                'UserID' : userID,
                'SessionID' : requested_convoID
                }
        )


    chatlog[requested_convoID] = []
    # summaries_found = False
    summaries = []
    messages = []

    if remote_summaries_from_convo:
        eZprint_anything(remote_summaries_from_convo, DEBUG_KEYS + ['SUMMARY'], message = 'remote summaries found')
        # print(remote_summaries_from_convo)
        for summary in remote_summaries_from_convo:
            json_summary = json.loads(summary.json())['blob']
            for key, val in json_summary.items():
                # if val['epoch']<1:
                    summaries_found = True
                    val['role'] = 'system'
                    # val['function_name']= 'conversation_summary'
                    # val['muted'] = False
                    # val['minimised'] = False
                    val['contentType'] = 'summary'
                    val['content'] = 'Conversation Summary : '
                    if val.get('timestamp',None):
                        val['content'] += val['timestamp'] + '\n'
                    # val['content'] += val['title'] + ' : ' + val['body']
                    val['sources'] = val['sourceIDs']
                    meta = val.get('meta', None)
                    if meta:
                        trigger = meta.get('trigger', None)
                        if trigger:
                            if trigger == 'convo-summarised' or trigger == 'epoch-summarised':
                                break    
                            val['trigger'] = trigger
                        
                    val['id'] = summary.id
                    summaries.append(val)

    if remote_messages_from_convo:
        # print('remote messages found')
        for message in remote_messages_from_convo:
            json_message = json.loads(message.json())
            messages.append(json_message)

    # for summary in summaries:
    #     chatlog[requested_convoID].append(summary)
    #     messages_added = False
    #     for source in summary['sources']:
    #         for message in messages:
    #             if message['id'] == source:
    #                 # print('adding on source match' + str(message) + 'to summary' + str(summary))
    #                 messages_added = True
    #                 chatlog[requested_convoID].append(message)
    #                 messages.remove(message)
    #     if not messages_added:
    #         # print('removing sum ary as no sources' + str(summary))
    #         chatlog[requested_convoID].remove(summary)
    for message in messages:
        # message['muted'] = False
        # message['minimised'] = False
        # message['summarised'] = False
        chatlog[requested_convoID].append(message)


    for summary in summaries:
        for log in chatlog[requested_convoID]:
            if summary['sourceIDs']:
                if log['id'] == summary['sourceIDs'][0]:
                    index = chatlog[requested_convoID].index(log)
                    chatlog[requested_convoID].insert(index, summary)
                    # summaries.remove(summary)
                    break

    for log in chatlog[requested_convoID]:
        if 'sourceIDs' in log:
            eZprint_anything(log, ['CONVO', 'INITIALISE', 'SUMMARY'], message = 'summary-log')
            if log.get('trigger', None) != 'cartridge':
                # eZprint('trigger source : ' + str(log['trigger']), ['CONVO', 'INITIALISE', 'SUMMARY'])
                for source in log['sourceIDs']:
                    for log in chatlog[requested_convoID]:
                        if log['id'] == source:
                            log['summarised'] = True
                            log['minimised'] = True
                            log['muted'] = True
            elif log['trigger'] == 'cartridge':
                eZprint('trigger source : ' + str(log['trigger']), ['CONVO', 'INITIALISE', 'SUMMARY'])
                # log['summarised'] = True
                log['minimised'] = True
                # log['muted'] = True
                log['childrenShow'] = True

            # else:
                            #thinking here how to control basically the body of the summary is minimised, only title BECAUSE the summary is expanded (showing children
            #     # eZprint('trigger source : ' + str(log['trigger']), ['CONVO', 'INITIALISE', 'SUMMARY'])
            #     log['minimised']=True

  

    unsumarrised = False
    for log in chatlog[requested_convoID]:
        if 'summarised' not in log or not log['summarised']:
            unsumarrised = True
            break

    if not unsumarrised:
        summaries_present = False
        for log in chatlog[requested_convoID]:
            if 'contentType' in log and log['contentType'] == 'summary':
                summaries_present = True
                local_summary = False
                for otherLog in chatlog[requested_convoID]:
                    if 'contentType' in otherLog and otherLog['contentType'] == 'summary':
                        if log['id']  in otherLog['sourceIDs']:
                            local_summary = True
                            break   
                if not local_summary:
                    log['summarised'] = False
                    log['minimised'] = False
                    log['muted'] = False
                    if log['content'] == 'None':
                        log['content'] = ''
                    if log['function_call']:
                        if log['arguments']:
                            log['arguments'] == json.loads(log['arguments'], strict=False)

        if not summaries_present:
            for log in chatlog[requested_convoID]:
                    log['summarised'] = False
                    log['minimised'] = False
                    log['muted'] = False
        
    await websocket.send(json.dumps({'event':'set_convo', 'payload':{'messages': chatlog[requested_convoID], 'convoID' : requested_convoID}}))
    await websocket.send(json.dumps({'event':'set_convoID', 'payload':{'convoID' : requested_convoID}}))

        # print(chatlog[requested_convoID])
    
    novaSession[sessionID]['convoID'] = requested_convoID
    novaConvo[requested_convoID] = {}
    novaConvo[requested_convoID]['sessionID'] = sessionID

    #this is only for return to convo
    if loadout:
        await update_loadout_field(loadout, 'latest_convo', requested_convoID)

# async def handle_convo_switch(sessionID):
#     eZprint('handle_convo_switch called', ['CONVO', 'INITIALISE'])
#     requested_convoID = None

#     if sessionID in current_config and 'convoID' in current_config[sessionID]:
#         eZprint('adding on currentConfig', ['CONVO', 'INITIALISE'])
#         requested_convoID = current_config[sessionID]['convoID']

#     elif sessionID in available_convos:
#         eZprint('adding on available convos', ['CONVO', 'INITIALISE'])
#         eZprint_anything(available_convos[sessionID], ['CONVO', 'INITIALISE'])
#         if len(available_convos[sessionID]) > 0:
#             requested_convoID = available_convos[sessionID][-1]['sessionID']

#     if requested_convoID:
#         await set_convo(requested_convoID, sessionID)
    
#     return requested_convoID


async def start_new_convo(sessionID, loadout):
    eZprint('start_new_convo called', ['CONVO', 'INITIALISE'])
    #TODO: make 'add convo'wrapper (and set convo
    convoID = secrets.token_bytes(4).hex()
    # loadout = current_loadout[sessionID]
    # await initialise_conversation(sessionID, convoID, params)
    convoID_full = sessionID +'-'+convoID +'-'+ str(loadout)
    eZprint('new convo convoID full ' + convoID_full, ['CONVO', 'INITIALISE'])
    novaSession[sessionID]['convoID'] = convoID_full

    novaConvo[convoID_full] = {}
    novaConvo[convoID_full]['sessionID'] = sessionID
    novaConvo[convoID_full]['loadout'] = loadout
    session ={
        'sessionID' : convoID_full,
        'convoID' : convoID_full,
        'date' : datetime.now().strftime("%Y%m%d%H%M%S"),
        'summary': "new conversation",
    }
    await websocket.send(json.dumps({'event':'set_convoID', 'payload':{'convoID' : convoID_full}}))
    await websocket.send(json.dumps({'event':'add_convo', 'payload': session}))
            
    return convoID_full

async def turn_guest_logs_to_user(newUserID, guestID, sessionID):
    eZprint('turn_guest_logs_to_user called', ['CONVO', 'INITIALISE'])
    logs = await prisma.log.find_many(
        where = {
            'UserID' : guestID
        }
    )
    for log in logs:
        log = json.loads(log.json())
        log['UserID'] = newUserID
        log = json.dumps(log)
        await prisma.log.update(
            where = {
                'id' : log['id']
            },
            data = {
                'UserID' : newUserID
            }
        )

    summaries = await prisma.summary.find_many(
        where = {
            'UserID' : guestID
        }
    )
    for summary in summaries:
        summary = json.loads(summary.json())
        summary['UserID'] = newUserID
        summary = json.dumps(summary)
        await prisma.summary.update(
            where = {
                'id' : summary['id']
            },
            data = {
                'UserID' : newUserID
            }
        )

    messages = await prisma.message.find_many(
        where = {
            'UserID' : guestID
        }
    )
    for message in messages:
        message = json.loads(message.json())
        message['UserID'] = newUserID
        message = json.dumps(message)
        await prisma.message.update(
            where = {
                'id' : message['id']
            },
            data = {
                'UserID' : newUserID
            }
        )
    await websocket.send(json.dumps({'event':'set_convoID', 'payload':{'convoID' : sessionID}}))
    return True
    #
