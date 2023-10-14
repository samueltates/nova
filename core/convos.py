from datetime import datetime
import secrets
import json
import asyncio

from session.appHandler import websocket
from session.sessionHandler import novaConvo, novaSession, chatlog, available_convos, current_config, current_loadout
from session.prismaHandler import prisma
from core.loadout import update_loadout_field
from tools.debug import eZprint, eZprint_anything



async def get_loadout_logs(loadout, sessionID ):

    ## finds logs connected to loadout
    if sessionID not in novaSession:
        novaSession[sessionID] = {}
    
    if 'userID' not in novaSession[sessionID]:
        novaSession[sessionID]['userID'] = None
    
    userID = novaSession[sessionID]['userID']


    available_convos[sessionID] = []

    logs = None

    if sessionID in current_config and 'shared' in current_config[sessionID] and current_config[sessionID]['shared'] or 'owner' in novaSession[sessionID] and novaSession[sessionID]['owner'] and loadout != None:
        eZprint('shared or owner', ['CONVO', 'INITIALISE'])
        logs = await prisma.log.find_many(
                where={ "SessionID": {'contains':str(loadout)} },
            )
        # print(logs)
    else:
        eZprint('not shared or owner or no loadout', ['CONVO', 'INITIALISE'])
        logs = await prisma.log.find_many(
                where={ "UserID": userID, 
                    "SessionID": {'contains':str(loadout)} },
                )
        # print (logs)
            
    # print(logs)
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



async def populate_summaries(sessionID):
     
    userID = novaSession[sessionID]['userID']

    for log in available_convos[sessionID]:
        if log['summary'] == '':
            splitID = log['sessionID'].split('-')
            if len(splitID) >1:
                splitID = splitID[1]
            try:
                remote_summaries_from_convo = await prisma.summary.find_many(
                    where = {
                        'UserID' : userID,
                        'SessionID' : splitID
                        }
                )
                if not remote_summaries_from_convo:
                    remote_summaries_from_convo = await prisma.summary.find_many(
                    where = {
                        'UserID' : userID,
                        'SessionID' : log['sessionID']
                        }
                )
            except:
                remote_summaries_from_convo = None
                
            summary = ''

            if remote_summaries_from_convo:
                for summary in remote_summaries_from_convo:
                    # print(summary)
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
                    await websocket.send(json.dumps({'event': 'update_convo_tab', 'payload': log}))

async def set_convo(requested_convoID, sessionID):
    
    userID = novaSession[sessionID]['userID']
    eZprint(requested_convoID+ ' requested convoID', ['CONVO', 'INITIALISE'])
    splitConvoID = requested_convoID.split('-')
    if len(splitConvoID) > 1:
        splitConvoID = splitConvoID[1]

    if sessionID in current_config and 'shared' in current_config[sessionID] and current_config[sessionID]['shared'] or novaSession[sessionID]['owner']:

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
        # print('remote summaries found')
        # print(remote_summaries_from_convo)
        for summary in remote_summaries_from_convo:
            json_summary = json.loads(summary.json())['blob']
            for key, val in json_summary.items():
                # if val['epoch']<1:
                    summaries_found = True
                    val['role'] = 'assistant'
                    val['user_name']= 'summary'
                    # val['muted'] = False
                    # val['minimised'] = False
                    val['contentType'] = 'summary'
                    val['sources'] = val['sourceIDs']
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
            for source in log['sourceIDs']:
                for log in chatlog[requested_convoID]:
                    if log['id'] == source:
                        log['summarised'] = True
                        log['minimised'] = True
                        log['muted'] = True

  

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
        # print(chatlog[requested_convoID])
    
    novaSession[sessionID]['convoID'] = requested_convoID
    novaConvo[requested_convoID] = {}
    novaConvo[requested_convoID]['sessionID'] = sessionID

    #this is only for return to convo
    # loadout = current_loadout[sessionID]
    # if loadout:
    #     print('updating loadout field' + str(loadout))
    #     novaConvo[requested_convoID]['loadout'] = loadout
    #     print(novaConvo[requested_convoID]['loadout'])
    #     await update_loadout_field(loadout, 'convoID', requested_convoID)

async def handle_convo_switch(sessionID):
    eZprint('handle_convo_switch called', ['CONVO', 'INITIALISE'])
    requested_convoID = None
    if sessionID in current_config and 'convoID' in current_config[sessionID]:
        eZprint('adding on currentConfig', ['CONVO', 'INITIALISE'])
        requested_convoID = current_config[sessionID]['convoID']

    elif sessionID in available_convos:
        eZprint('adding on available convos', ['CONVO', 'INITIALISE'])
        eZprint_anything(available_convos[sessionID], ['CONVO', 'INITIALISE'])
        if len(available_convos[sessionID]) > 0:
            requested_convoID = available_convos[sessionID][-1]['sessionID']

    if requested_convoID:
        await set_convo(requested_convoID, sessionID)
    
    return requested_convoID
        


async def start_new_convo(sessionID):
    eZprint('start_new_convo called', ['CONVO', 'INITIALISE'])
    #TODO: make 'add convo'wrapper (and set convo
    convoID = secrets.token_bytes(4).hex()
    loadout = current_loadout[sessionID]
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
    await websocket.send(json.dumps({'event':'add_convo', 'payload': session}))

            
    return convoID_full

