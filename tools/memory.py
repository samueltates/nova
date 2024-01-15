import json
import math
import asyncio
from prisma import Json
import secrets
from datetime import datetime

from session.prismaHandler import prisma
from session.sessionHandler import novaConvo,novaSession, active_cartridges, chatlog, current_loadout
from session.appHandler import websocket
from core.cartridges import update_cartridge_field
from chat.query import sendChat, get_summary_with_prompt, parse_json_string
from tools.debug import eZprint, get_fake_messages, get_fake_summaries, debug, eZprint_anything
from tools.keywords import get_keywords_from_summaries

summaries = {}
windows = {}
DEBUG_KEYS = ['SUMMARY']

async def run_summary_cartridges(convoID, sessionID, cartKey, cartVal, client_loadout = None):
    userID = novaSession[sessionID]['userID']
    eZprint('run summary cartridges triggered', DEBUG_KEYS)
    if novaSession[sessionID]['owner']:
        if 'blocks' not in cartVal:
            cartVal['blocks'] = {}

        if 'summary-target' in cartVal:
            # print('summary target found')
            target_loadout = cartVal['summary-target']
        else:
            # print('no summary target')
            target_loadout = client_loadout
        # if convoID in novaConvo and 'owner' in novaConvo[convoID] and novaConvo[convoID]['owner']:
        await summarise_convos(convoID, sessionID, cartKey, cartVal, client_loadout, target_loadout)
        await get_summaries(userID, sessionID, target_loadout)
        await update_cartridge_summary(convoID, userID, cartKey, cartVal, sessionID, client_loadout)
        await get_overview(convoID, sessionID, cartKey, cartVal, client_loadout)
        await update_cartridge_summary(convoID, userID, cartKey, cartVal, sessionID, client_loadout)
        await get_keywords_from_summaries(convoID, sessionID, cartKey, cartVal, client_loadout,
            target_loadout)
        

        input = {
            'cartKey': cartKey,
            'sessionID': sessionID,
            'fields': {
                'running': False,
            }
        }
        await update_cartridge_field(input,convoID, client_loadout, system=True)


async def summarise_convos(convoID, sessionID, cartKey, cartVal, client_loadout= None, target_loadout = None):

    eZprint('summarising convos')
    userID = novaSession[sessionID]['userID']

    if novaSession[sessionID]['owner']:
        # if client_loadout == current_loadout[sessionID]:
        cartVal['state'] = 'loading'
        cartVal['status'] = 'summarising convos'
        input = {
        'cartKey': cartKey,
        'sessionID': sessionID,
        'fields': {
            'state': cartVal['state'],
            'status': cartVal['status'],
            },
        }
        await update_cartridge_field(input, convoID, client_loadout, system=True)
        await summarise_messages(userID, sessionID, client_loadout, target_loadout)
        # print('summarise messages finished')
        await summarise_epochs(userID, sessionID, client_loadout, target_loadout)
        
async def summarise_messages_by_convo(userID, sessionID, convoID ):
    POPULATE_KEYS = ['POPULATE_SUMMARY']
    eZprint_anything(convoID, POPULATE_KEYS, message = 'summarising convo')
    messages = []

    log = await prisma.log.find_first(
            where={
            'SessionID': convoID,
            }
    )
    if log:
        if log.summary == 'loading':
            return
        #set log summary value to loading
        updated_log = await prisma.log.update(
            where={
                'id': log.id,
            },
            data={
                'summary': 'loading',
            }
        )
        session ={
            'id': log.id,
            'sessionID' : log.SessionID,
            'convoID' : convoID,
            'date' : log.date,
            'summary': 'loading',
        }
        await websocket.send(json.dumps({'event': 'update_convo_tab', 'payload': session}))

    remote_messages = await prisma.message.find_many(
            where={
            'SessionID': convoID,
            'summarised': False
            }
    )
    eZprint_anything(remote_messages, POPULATE_KEYS, message = 'remote messages')
    normalised_convos = []
    meta = ' '

    # print(messages)
    ids = []

    conversation_string = ''
    for message in remote_messages:
        eZprint('message getting scanned' + str(message), DEBUG_KEYS)
        if meta == ' ':
            format = '%Y-%m-%dT%H:%M:%S.%f%z'
            # date = datetime.strptime(message.timestamp, format)
            meta = {        
                'docID': convoID,
                'timestamp': message.timestamp,
                'type' : 'message',
                'corpus' : 'loadout-conversations',
                'trigger': 'cartridge'
            }

        
        if message.name:
            conversation_string += str(message.name) 
        if message.body:
            conversation_string += ': '+ str(message.body)
        if message.content:
            conversation_string += ': ' + str(message.content)
        if message.timestamp:
            conversation_string += '\n' + str(message.timestamp) + '\n\n'
        ids.append(message.id)

        if len(conversation_string) > 7000:
            eZprint_anything(message, DEBUG_KEYS, message = '7000 char to summarise')

            # convoSplitID = conversation.SessionID.split('-')
            # docID = convoSplitID
            # if len(convoSplitID) >1:
            #     docID = convoSplitID[1]

            i = 0
            range = 7000
            last_text = ''
            while i < len(conversation_string):
                ## get the 7000 char range
                target = conversation_string[i:i+range]
                # print(str(len(conversation_string)) +"  target range and remainder -> "+ str(i + range))
                if (len(conversation_string) - (i + range) < 3000):
                    # print('remainder is less than 3000')
                    target += conversation_string[i+range:len(conversation_string)]
                    # print(str(len(target)))
                    i += range

                normalised_convos.append({
                    'ids': ids,
                    'toSummarise': target,
                    'epoch' : 0,
                    'meta' : meta,
                    'docID' : convoID
                })

                i += range
                
            conversation_string = ''
            ids = []
            meta = ' '
    #resetting after each conversation so that each is blob is only one convo
    eZprint(str(len(conversation_string)), ['SUMMARY'], message = 'length of string at end of convo')

    # removing as not summarising last chunk if not big enough
    if conversation_string != '':
        # eZprint('logging conversation with unsumarised messages\n' + f'{conversation_string}')
            # print('adding on last bit of convo')
            # print(str(len(conversation_string)))
            # convoSplitID = conversation.SessionID.split('-')
            # docID = convoSplitID
            # if len(convoSplitID) >1:
            #     docID = convoSplitID[1]
            normalised_convos.append({
                'ids': ids,
                'toSummarise': conversation_string,
                'epoch' : 0,
                'meta' : meta,
                'docID' : convoID

            })
    conversation_string = ''
    ids = []
    meta = ' '

    await summarise_batches(normalised_convos, userID, sessionID,  conversation_summary_prompt)
    await handle_convo_summary(convoID, userID, sessionID)


##LOG SUMMARY FLOWS
## gets messages normalised into 'candidates' with all data needed for summary
async def summarise_messages(userID, sessionID, client_loadout = None, target_loadout = None):  
    eZprint('getting messages to summarise')
    ##takes any group of candidates and turns them into summaries
    messages = []
    remote_messages = await prisma.message.find_many(
            where={
            'SessionID': { 'contains': str(target_loadout) },
            'summarised': False
            }
    )

    conversations = await prisma.log.find_many(
            where={
            'SessionID': { 'contains': str(target_loadout) },
            }
    )


    # print(remote_messages)
    messages = []
    for message in remote_messages:
        splitID = message.SessionID.split('-')
        # print(splitID)
        if len(splitID) >=3:
            # print(splitID[2])
            if splitID[2] == str(target_loadout):
                messages.append(message)
                # print('adding on loadout')
        elif target_loadout == None:
            # print(splitID)
            messages.append(message)
            # print('adding on no loadout')

    normalised_convos = []
    meta = ' '

    # print(messages)
    ids = []
    conversation_string = ''
    for conversation in conversations:
        # await handle_convo_summary(conversation.SessionID, userID)
        eZprint('conversation getting scanned' + str(conversation.SessionID), DEBUG_KEYS)
        for message in messages:
            if sessionID in current_loadout and client_loadout != current_loadout[sessionID]:
                return
            if message.SessionID == conversation.SessionID:
                # print(message)
                if meta == ' ':
                    format = '%Y-%m-%dT%H:%M:%S.%f%z'
                    date = datetime.strptime(message.timestamp, format)
                    meta = {        
                        'docID': conversation.SessionID,
                        'timestamp': message.timestamp,
                        'type' : 'message',
                        'corpus' : 'loadout-conversations',
                        'trigger': 'cartridge'
                    }

                
                if message.name:
                    conversation_string += str(message.name) 
                if message.body:
                    conversation_string += ': '+ str(message.body)
                if message.content:
                    conversation_string += ': ' + str(message.content)
                if message.timestamp:
                    conversation_string += '\n' + str(message.timestamp) + '\n\n'
                ids.append(message.id)

                if len(conversation_string) > 7000:
                    eZprint_anything(message, DEBUG_KEYS, message = '7000 char to summarise')

                    i = 0
                    range = 7000
                    last_text = ''
                    while i < len(conversation_string):
                        ## get the 7000 char range
                        target = conversation_string[i:i+range]
                        # print(str(len(conversation_string)) +"  target range and remainder -> "+ str(i + range))
                        if (len(conversation_string) - (i + range) < 3000):
                            # print('remainder is less than 3000')
                            target += conversation_string[i+range:len(conversation_string)]
                            # print(str(len(target)))
                            i += range

                        normalised_convos.append({
                            'ids': ids,
                            'toSummarise': target,
                            'epoch' : 0,
                            'meta' : meta,
                            'docID' : conversation.SessionID
                        })

                        i += range
                        
                    conversation_string = ''
                    ids = []
                    meta = ' '
        #resetting after each conversation so that each is blob is only one convo
        eZprint(str(len(conversation_string)), ['SUMMARY'], message = 'length of string at end of convo')

        # removing as not summarising last chunk if not big enough
        if conversation_string != '':
            # eZprint('logging conversation with unsumarised messages\n' + f'{conversation_string}')
                # print('adding on last bit of convo')
                # print(str(len(conversation_string)))
                # convoSplitID = conversation.SessionID.split('-')
                # docID = convoSplitID
                # if len(convoSplitID) >1:
                #     docID = convoSplitID[1]
                normalised_convos.append({
                    'ids': ids,
                    'toSummarise': conversation_string,
                    'epoch' : 0,
                    'meta' : meta,
                    'docID' : conversation.SessionID

                })
        conversation_string = ''
        ids = []
        meta = ' '

    await summarise_batches(normalised_convos, userID, sessionID, conversation_summary_prompt)
    for conversation in conversations:
        await handle_convo_summary(conversation.SessionID, userID, sessionID)


async def handle_convo_summary(convoID, userID, sessionID):
    ## TODO : make it use only one summary record per convo, and let it pile up to one, write / rewrite that record
    convo_summarised =  False
    eZprint('checking summaries for first time', DEBUG_KEYS)
    while convo_summarised == False:
        eZprint('finding convo summaries', DEBUG_KEYS)
        convo_summaries = await prisma.summary.find_many(
                where = {
                    'UserID': userID,
                    'SessionID' : convoID,
                }
            )
        # if not convo_summaries or len(convo_summaries) <= 1:
        #     convo_summarised = True
        #     break
        eZprint('multiple convo summaries found', DEBUG_KEYS)
        summary_candidates = []
        log_summary = ''
        for candidate in convo_summaries:
            eZprint_anything(candidate, DEBUG_KEYS, message = 'candidate')
            summary = json.loads(candidate.json()).get('blob', None)
            for key, val in summary.items():
                # print('key and val' + str(key) + str(val))
                if val.get('epoch-summarised') == True:
                    continue
                if 'title' in val:
                    log_summary = val['title']
                if val.get('summarised') == True:
                    continue
                if val.get('convo-summarised') == True:
                    continue
                eZprint('found summary candidate' + str(val), DEBUG_KEYS)
                val.update({'id': candidate.id})
                summary_candidates.append(val)
        eZprint_anything(summary_candidates, DEBUG_KEYS, message = 'summary candidates')
        if len(summary_candidates) <= 1:
            convo_summarised = True
            if len(summary_candidates) == 1:
                summary_record = summary_candidates[0]
                eZprint('found single summary candidate' + str(summary), DEBUG_KEYS)
                if 'title' in summary_record:
                    log_summary = summary_record['title']
            if log_summary != '':
                eZprint('updating log with summary', DEBUG_KEYS)
                log = await prisma.log.find_first(
                    where = { 'SessionID' : convoID }
                )

                updated_log = await prisma.log.update(
                    where = {
                        'id' : log.id
                        },
                    data = {
                        'summary' : log_summary
                    }
                )
                session ={
                    'id': log.id,
                    'sessionID' : log.SessionID,
                    'convoID' : convoID,
                    'date' : log.date,
                    'summary': log_summary,
                }
                await websocket.send(json.dumps({'event': 'update_convo_tab', 'payload': session}))
            break
        # print(convos_to_summarise)
        batches = []
        toSummarise = ''
        ids = []
        meta = ''
        for summary in summary_candidates:
            # summary_blob = json.loads(target_summary.json())['blob']
            eZprint_anything(summary, DEBUG_KEYS, message = 'summaries in convo')
            
            summaryObj = await summary_into_candidate(summary)
            timestamp = ''
            if 'timestamp' in summaryObj:
                timestamp = summaryObj['timestamp']
            if meta == '':
                meta = {
                    'first-doc' : timestamp,
                    'type' : 'summary',
                    'corpus' : 'loadout-conversations',
                    'docID' : str(convoID),
                    'trigger' : 'convo-summarised'
                }
            toSummarise += str(summaryObj['content']) + '\n'
            ids.append(summary['id'])
            # print(summary)

            if len(toSummarise) > 7000:
                # print('adding to batch')
                meta['last-doc'] = timestamp
                batches.append({
                    'toSummarise' : toSummarise,
                    'ids' : ids,
                    'meta' : meta,
                    'epoch' : summaryObj['epoch'],
                    'docID' : convoID,


                })
                timestamp = ''
                toSummarise = ''
                ids = []
                meta = ''
        eZprint('summaries batched', DEBUG_KEYS)
        if len(toSummarise) > 0:
            # print('adding to batch')
            meta['last-doc'] = timestamp
            batches.append({
                'toSummarise' : toSummarise,
                'ids' : ids,
                'meta' : meta,
                'epoch' : summaryObj['epoch'],
                'docID' : convoID,

            })
            timestamp = ''
            toSummarise = ''
            ids = []
            meta = ''

        await summarise_batches(batches, userID, sessionID, summary_batch_prompt)



async def update_record(record_ID, record_type,  trigger = 'live'):
    eZprint('updating record with ID ' + str(record_ID) + ' and type ' + str(record_type), DEBUG_KEYS)

    summarised = True
    minimised = True
    muted = True
    trigger_value = False
    if trigger == 'convo-summarised':
        eZprint('convo summarised', DEBUG_KEYS)
        summarised = False
        minimised = False
        muted = False
        trigger_value = True

    if trigger == 'cartridge':
        eZprint('cartridge summarised', DEBUG_KEYS)
        # summarised = False
        minimised = False
        muted = False
        trigger_value = True

    if trigger == 'epoch-summarised':
        eZprint('epoch summarised', DEBUG_KEYS)
        summarised = False
        minimised = False
        muted = False
        trigger_value = True

    if record_type == 'message':
        # print('record type is message')
        remote_message = await prisma.message.find_first(
            where={
            'id': record_ID,
            }
        )

        if remote_message:

            updated_message = await prisma.message.update(
                where={
                    'id': remote_message.id,
                },
                data={
                    'summarised': summarised,
                    'minimised': minimised,
                    'muted': muted,            
                }
            )

    if record_type == 'summary':
        # print('record type is summary')
        target_summary = await prisma.summary.find_first(
            where={
            'id': record_ID,
            }
        )
        if target_summary:
            summary_blob = json.loads(target_summary.json())['blob']
            for key, val in summary_blob.items():
                val['summarised'] = summarised
                val['minimised'] = minimised
                val['muted'] = muted
                val[trigger] = trigger_value

            updated_summary = await prisma.summary.update(
                where={ 'id': target_summary.id },
                data={
                    'blob': Json({key:val}),
                }
            )
            eZprint('summary updated with ID ' + str(updated_summary) , DEBUG_KEYS)
            # print(updated_summary)
 
##GROUP SUMMARY FLOWS
async def summarise_batches(batches, userID, sessionID, prompt = "Summarise this text."):
    eZprint('summarising batches, number of batches ' + str(len(batches)), DEBUG_KEYS)
    ##takes normalised text from different sources, runs through assuming can be summarised, and creates summary records (this allows for summaries of summaries for the time being)
    
    counter = 0
    for batch in batches:
        # print('batch number ' + str(counter))

        counter += 1
        epoch = batch['epoch'] +1
        userID = novaSession[sessionID]['userID']
        summary = await get_summary_with_prompt(prompt, str(batch['toSummarise']), 'gpt-3.5-turbo', userID)
        summaryKey = secrets.token_bytes(4).hex()
        # eZprint('summary complete')
        # print(summary)
        await create_summary_record(userID, batch['ids'], summaryKey, summary, epoch, batch['meta'])


        # except:
        # print('error creating summary record')



async def create_summary_record( userID, sourceIDs, summaryKey, summary, epoch, meta = {}):
    eZprint_anything(summary, DEBUG_KEYS, message= 'creating summary record')
    # print()
    # print(summary)
    summarDict = await parse_json_string(summary)
    success = True
    trigger = meta.get('trigger', None)
    if summarDict == None:
        summarDict = {}
        summarDict.update({'title' : '...'})
        summarDict.update({'body' : str(summary)})
        success = False

    if summarDict:
        summarDict.update({'sourceIDs' : sourceIDs})
        summarDict.update({'meta': meta})
        summarDict.update({'epoch': epoch})
        summarDict.update({'summarised': False})
        summarDict.update({'key': summaryKey})
        

        # SessionID = sessionID
        docID = ''
        if 'docID' in meta:
            docID = meta['docID']

        # if docID != '':
        #     SessionID += '-' + docID

        # if loadout:
        #     SessionID += '-' + loadout

        summary = await prisma.summary.create(
            data={
                "key": summaryKey,
                'SessionID' : docID,
                "UserID": userID,
                "timestamp": datetime.now(),
                "blob": Json({summaryKey:summarDict})

            }
        )

    summaryID = summary.id
    # if success:
    for id in sourceIDs:
        await update_record(id, meta['type'], trigger)    
    return summaryID

##MOST GENERIC SUMMARY FUNCTIONS

async def summary_into_candidate(summarDict ):
    ##turns summary objects themselves into candidates for summary
    # print('summary into candidate' + str(summarDict))
    title = ''
    if 'title' in summarDict:
        title = summarDict['title']
    timestamp = ''
    if 'timestamp' in summarDict:
        timestamp = str(summarDict['timestamp'])
    body = ''
    if 'body' in summarDict:
        body = summarDict['body']
    keywords = ''

    summaryString = title + ' - ' + timestamp + '\n' + body + '\n'

    # if 'keywords' in summarDict:
    #     summaryString += '\nKeywords: '
    #     for keyword in summarDict['keywords']:
    #         summaryString += keyword + ', '
    #     summaryString += '\n'
        
    # notes = ''
    # if 'notes' in summarDict:
    #     for key, val in summarDict['notes'].items():
    #         notes += '-'+str(key) + ': ' + str(val) + '\n'

    # if notes != '':
    #     # print('notes found adding title')
    #     summaryString += '\nNotes:\n' + notes

    # insights = ''
    # if 'insights' in summarDict:
    #     for key, val in summarDict['insights'].items():
    #         if isinstance(val, dict):
    #             for key2, val2 in val.items():
    #                 summaryString += '-'+str(key2) + ': ' + str(val2) + '\n'


    # if insights != '':
    #     # print('insights found adding title')
    #     summaryString += '\nInsights:\n' + insights 


    if 'epoch' not in summarDict:
        epoch = 0
    else:
        epoch = summarDict['epoch']
    if 'meta' not in summarDict:
        meta = ''
    else:
        meta = summarDict['meta']

    candidate = {
        'content' : summaryString,
        'meta' : meta,
        'epoch' : epoch,
        'id' : summarDict['id'],
        'type' : 'summary',
        'timestamp' : timestamp,
    }
    
    return candidate



async def summarise_epochs(userID, sessionID, client_loadout = None, target_loadout = None):
    ##number of groups holding pieces of content at different echelons, goes through echelons, summarises in batches if too full (bubbles up) and restarts
    EPOCH_KEYS = DEBUG_KEYS + ['EPOCH']
    eZprint('starting epoch summary', EPOCH_KEYS)

    epoch_in_window = False

    while epoch_in_window == False:
        epochs = {}
        eZprint('getting epochs', DEBUG_KEYS)


        candidates = await prisma.summary.find_many(
            where={
            'UserID': userID,
            'SessionID': { 'contains': str(target_loadout) }
            }
        ) 
        eZprint('got candidates for epochs', EPOCH_KEYS)

        # loadout_candidates = []
        # for candidate in candidates:
        #     # print(candidate.SessionID)
        #     splitID = candidate.SessionID.split('-')
        #     # print(splitID)
        #     if len(splitID) >= 3:
        #         if splitID[2] == target_loadout:
        #             # print('found loadout candidate')
        #             loadout_candidates.append(candidate)
        #     elif target_loadout  == None:
        #         # print('adding on a none loadout')
        #         loadout_candidates.append(candidate)

        eZprint('setting epoch_in_window to true', EPOCH_KEYS)
        epoch_in_window = True
        for candidate in candidates:
            summary = json.loads(candidate.json())['blob']

            for key, val in summary.items():
                # print('key and val' + str(key) + str(val))
                if 'summarised' in val:
                    if val['summarised'] == True:
                        continue
                if 'cono-summarised' in val:
                    if val['convo-summarised'] == True:
                        continue
                if 'epoch-summarised' in val:
                    if val['epoch-summarised'] == True:
                        continue
                eZprint('found summary candidate' + str(val), EPOCH_KEYS)
                epoch_no = 'epoch_' + str(val['epoch'])
                val.update({'id': candidate.id})
                # eZprint('found summary candidate')
                if epoch_no not in epochs:
                    eZprint('creating epoch ' + str(epoch_no), EPOCH_KEYS)
                    epochs[epoch_no] = []
                epochs[epoch_no].append(val)
        ## number of pieces of content per window 

        resolution = 2
        # print(f'{epochs}')
        
        epoch_summaries = 0

        batches = []

        for key, val in epochs.items():
            epoch = val
            # eZprint('epoch is ' + key) 
            # print(epoch)
            #checks if epoch is 70% over resolution
            if client_loadout != current_loadout[sessionID]:
                return
            
            #switching to 'windows' being based on token size, so resolution is 3 blocks of 10k
            # eZprint('epoch too large, starting epoch batch and summarise')
            ## if any epoch has too many summaries it'll go through and summarise to resolution specified, and then restart whole thing... will see if we can make more elegant, but can't think of how else apart from removing from that 
            toSummarise = ''
            ids = []
            x = 0
            meta = ''
            # print('epoch len ' + str(len(epoch)))
            if len(epoch) > 1:
                for summary in epoch:
                    x += 1
                    ##goes through and creates batches in reverse
                    # eZprint('creating candidate  ' + str(x) + ' of epoch ' + str(key))
                    summaryObj = await summary_into_candidate(summary)
                    timestamp = ''
                    if 'timestamp' in summaryObj:
                        timestamp = summaryObj['timestamp']
                    if meta == '':
                        meta = {
                            'first-doc' : timestamp,
                            'type' : 'summary',
                            'corpus' : 'loadout-conversations',
                            'docID' : str(target_loadout),
                            'trigger': 'epoch-summarised'
                        }
                    toSummarise += str(summaryObj['content']) + '\n'
                    ids.append(summary['id'])
                    # print(summary)

                    if len(toSummarise) > 7000:
                        # print('adding to batch')
                        meta['last-doc'] = timestamp
                        batches.append({
                            'toSummarise' : toSummarise,
                            'ids' : ids,
                            'meta' : meta,
                            'epoch' : summaryObj['epoch'],
                            'docID' : target_loadout

                        })
                        timestamp = ''
                        toSummarise = ''
                        ids = []
                        meta = ''
                # print('epoch summarised looped')
                if toSummarise != '':
                    # print('adding to batch')
                    meta['last-doc'] = timestamp
                    batches.append({
                        'toSummarise' : toSummarise,
                        'ids' : ids,
                        'meta' : meta,
                        'epoch' : summaryObj['epoch'],
                        'docID' : target_loadout

                    })
                    timestamp = ''
                    toSummarise = ''
                    ids = []
                    meta = ''
            if len(batches) > 0:
                await summarise_batches(batches, userID, sessionID, summary_batch_prompt)
                batches = []
                eZprint('summarising batches so setting to false to trigger reloop', EPOCH_KEYS)
                epoch_in_window = False
                break
                


    # for key, val in epochs.items():
    #     epoch = val
    #     for summary in epoch:


    # print('epoch summarised outside while should be past while loop')
    

async def get_summaries( userID, sessionID, target_loadout):

    # eZprint('getting summaries')
    summaries = await prisma.summary.find_many(
        where={
        'UserID': userID,
        }
    ) 

    summary_candidates = []
    if len(summaries) == 0:
        return 
    # print('loadoutID is ' + str(loadoutID))
    for summary in summaries:
        # print(summary)
        splitID = str(summary.SessionID).split('-')
        # print(splitID)
        if target_loadout in summary.SessionID:
            summary_candidates.append(summary)

        elif target_loadout == None:
            # print('adding on a none loadout')
            summary_candidates.append(summary)

    summaries = summary_candidates

    windows[userID+sessionID] = []
    epochs = {}
    for summary in summaries:
        summaryObj = dict(summary.blob)

        for key, val in summaryObj.items():
            eZprint_anything(val, DEBUG_KEYS, message = 'summary found')
            if val.get('summarised') == True:
                    continue
            if val.get('trigger') == 'cartridge':
                #skips if trigger for summary was cartridge  (only convo chunks)
                continue
            if val.get('convo-summarised') == True:
                #skips if summarised by convo summariser
                continue
            if val.get('epoch-summarised') == True:
            #     #skips if summarised by epoch summariser
                continue

                #leaving only unsumarised top of convo and epoch summaries
            # eZprint('found summary candidate')
            eZprint_anything(val, DEBUG_KEYS, message = 'summary to show')

            val.update({'key': summary.key})
            epoch_no = 'epoch_' + str(val['epoch'])
            if val['epoch'] not in epochs:
                # eZprint('creating epoch ' + str(epoch_no))
                epochs[val['epoch']] = []
            epochs[val['epoch']].append(val)
        
    if userID not in windows:
        windows[userID+sessionID] = []

    resolution = 3
    window = []
    sorted_epochs = sorted(epochs.items(), key=lambda x: x[0])
    # print(sorted_epochs)
    for epochs in sorted_epochs:
        (epoch_no, summaries) = epochs
        counter = 0
        reversed_summaries = summaries[::-1]
        for summary in reversed_summaries:
            # print(summary)
            window.append(summary)
            counter += 1
            if counter >= resolution - 1:
                windows[userID+sessionID].append(window)
                window = []
                counter = 0
    if window != []:
        windows[userID+sessionID].append(window)

            #TODO - set summary 




conversation_summary_prompt = """
Generate a concise summary of this conversation in JSON format, including a title, time range, in-depth paragraph, top 3 keywords, and relevant notes. The summary should be organized as follows:

{
    "title": "[Short unique description of topics discussed]",
    "timestamp" : "[Time, Date, or Date Range]",
    "body": "[Longer summary with key topics, decisions, and discoveries]",
    "keywords": ["Keyword1", "Keyword2", "Keyword3"],
    "notes": {
        "[Note Title1]": "[Note Body1]",
        "[Note Title2]": "[Note Body2]"
    },
    "insights": {
        "people": {
            "[Insight Title1]": "[Insight Body1]"
        },
        "places": {
            "[Insight Title2]": "[Insight Body2]"
        },
        "projects" : {
            "[Insight Title3]": "[Insight Body3]"
        },
        "positive memories": {
            "[Insight Title4]": "[Insight Body4]"
        },
        "negative memories": {
            "[Insight Title5]": "[Insight Body5]"
        } 
    }
}

Ensure that the summary captures essential decisions, discoveries, or resolutions, and keep the information dense and easy to parse.
"""

summary_batch_prompt = """
Combine the below conversation summaries into one single summary in JSON format, including a title, time range, in-depth paragraph, top 3 keywords, and relevant notes. The summary should be organized as follows:

{
    "title": "[Short unique overview of topics in this period]",
    "timestamp" : "[first timestamp] - [last timestamp]",
    "body": "[Synthesis of topics, decisions, and discoveries across conversations]", 
    "keywords": ["Keyword1", "Keyword2", "Keyword3"],
    "notes": {
        "[Note Title1]": "[Note Body1]",
        "[Note Title2]": "[Note Body2]"
    }
}

Ensure that the summary captures the broad strokes of all conversations in one synthesis. Make sure that the above format is followed exactly, and can be read by json.dumps, ensuring all response is inside of the brackets with only one root JSON object. Ensure all conversation summaries are combined into one single summary:
"""

async def summarise_percent(convoID, percent):
    eZprint('summarising percent', DEBUG_KEYS)
    await  websocket.send(json.dumps({'event':'recieve_agent_state', 'payload':{'agent': 'system', 'state': 'summarising'}}))

    summaryKey = secrets.token_bytes(4).hex()
    message_IDs = []
    counter = 0
    # print(chatlog[convoID])
    unsummarised = []
    if convoID in chatlog:
        for log in chatlog[convoID]:
            # print(log)
            if 'summarised' not in log or log['summarised'] == False:
                # if counter <= max:
                    if 'id' in log:
                        unsummarised.append(log['id'])
    
    max = len(unsummarised) * percent
    for log in unsummarised:
        if counter <= max:
            message_IDs.append(log)
            counter += 1

    summary_block = {
        'convoID': convoID,
        'messageIDs': message_IDs,
        'summaryKey': summaryKey,
    }

    # payload = {'summaryKey':summaryKey, 'messages': message_IDs}
    await  websocket.send(json.dumps({'event':'create_summary', 'payload':summary_block}))

    summary_result = await summariseChatBlocks(summary_block)
    return summary_result

async def summarise_from_range(convoID, start, end):

    start = int(start)
    end = int(end)
    eZprint('summarising from range')
    summaryKey = secrets.token_bytes(4).hex()
    message_IDs = []

    # print(chatlog[convoID])

    counter = 0
    for log in chatlog[convoID]:
        if 'summarised' not in log or log['summarised'] == False:
        # print(log)
                if counter >= start and counter <= end:
                    # eZprint('adding to summarise' + str(log['ID'] + ' ' + log['body']))
                    if 'id' in log:
                        message_IDs.append(log['id'])
                counter += 1

    summary_block = {
        'convoID': convoID,
        'messageIDs': message_IDs,
        'summaryKey': summaryKey,
    }

    # payload = {'summaryKey':summaryKey, 'messageIDs': message_IDs}
    await  websocket.send(json.dumps({'event':'create_summary', 'payload':summary_block}))
    summary_result = await summariseChatBlocks(summary_block)
    return summary_result



async def summariseChatBlocks(input,  loadout = None):
    eZprint('summarising chat blocks', DEBUG_KEYS)
    convoID = input['convoID']
    # print(input)
    messageIDs = []

    if 'messageIDs' in input:
        for id in input['messageIDs']:
            for log in chatlog[convoID]:
                if 'id' in log and id == log['id']:
                        if 'summarised' not in log or log['summarised'] == False:
                            messageIDs.append(log['id'])

    sessionID = novaConvo[convoID]['sessionID']
    summaryKey = input['summaryKey']
    userID = novaSession[sessionID]['userID']
    messages_string = ''
    messagesToSummarise = []
    start_message = None
    sessionID = ''

    eZprint('checking message ID list for messages to summarise' + str(messageIDs), DEBUG_KEYS)
    for log in chatlog[convoID]:

        if 'id' in log and log['id'] in messageIDs:
            if sessionID == '':
                if 'sessionID' in log:
                    sessionID = log['sessionID']
            messagesToSummarise.append(log)
            if start_message == None:
                start_message = log
            if 'timestamp' in log:
                messages_string +=  str(log['timestamp']) + '\n'
            if 'userName' in log:
                messages_string += str(log['userName']) + ': '
            if 'content' in log:
                messages_string += str(log['content']) 
            if 'function_call' in log:
                messages_string += str(log['function_call']) + '\n'
            messages_string += '\n'
            if 'role' in log:
                messages_string += 'role : '+  str(log['role']) + ': '
            if 'function_name' in log:
                messages_string += 'function name :' + str(log['function_name']) + '\n'

    payload = []   
    summary= ""
    prompt = """
    Generate a concise summary of this conversation in JSON format, including a title, time range, in-depth paragraph, top 3 keywords, and relevant notes. The summary should be organized as follows:

    {
    "title": "[Short description]",
    "timeRange": {"start": "[Start time]", "end": "[End time]"},
    "body": "[Longer description]",
    "keywords": ["Keyword1", "Keyword2", "Keyword3"],
    "notes": {
        "[Note Title1]": "[Note Body1]",
        "[Note Title2]": "[Note Body2]"
    }
    }

    Ensure that the summary captures essential decisions, discoveries, or resolutions, and keep the information dense and easy to parse.
    """
    model = 'gpt-3.5-turbo'

    if novaConvo.get(convoID):
        if novaConvo[convoID].get('model'):
            model = novaConvo[convoID]['model']


    summary = await get_summary_with_prompt(conversation_summary_prompt, str(messages_string), model, userID)
    #wait for 2 seconds
    eZprint_anything(summary, DEBUG_KEYS, message = 'summary returned')
    if summary:
        summarDict = await parse_json_string(summary)
        # summarDict = json.loads(summarDict, strict=False)
    print(summarDict)

    date = datetime.now()
    # summarDict.update({'sources':messageIDs})
    # convoSplitID = convoID.split('-')
    # docID = convoSplitID
    # if len(convoSplitID) >1:
    #     docID = convoSplitID[1]
    meta = {
        'overview': 'Conversation section from conversation ' + str(date),
        # 'docID': sessionID,
        'timestamp': date,
        'type' : 'message',
        'corpus' : 'loadout-conversations',
        'docID' : convoID
    }    
    # print(summarDict)
    summaryID = None
    summaryID = await create_summary_record(userID, messageIDs, summaryKey, summary, 0, meta)
    eZprint(summary, DEBUG_KEYS, 'summary')
    fields = {}
    for key, value in summarDict.items():
      fields[key] = value
    fields['state'] = ''
    fields['id'] = summaryID
    payload = {'key':summaryKey, 'fields':fields}
    await  websocket.send(json.dumps({'event':'updateMessageFields', 'payload':payload}))

    injectPosition = chatlog[convoID].index(start_message) 
    chatlog[convoID].insert(injectPosition, {'id':summaryID,'role':'function',  'function_name': 'conversation_summary', 'content':summarDict['title'] +" : "+ summarDict['body'], 'timestamp':datetime.now(),'key':summaryKey})
    # print(chatlog[convoID])
    for log in messagesToSummarise:
        remoteMessage = await prisma.message.find_first(
            where={'id': log['id']}
        )
        if remoteMessage:
            updatedMessage = await prisma.message.update(
                where={ 'id': remoteMessage.id },
                data={
                    'summarised': True,
                    'muted': True,
                    'minimised': True,
                 }      
            )
        elif log['contentType'] == 'summary': 
            remoteMessage = await prisma.summary.find_first(
                where={'id': log['id']}
            )
            if remoteMessage:
                updatedSummary = await prisma.summary.update(
                    where={ 'id': remoteMessage.id },
                    data={
                        'summarised': True,
                        'muted': True,
                        'minimised': True,
                    }
                )
            #basically getting messages that are summarised (by cartridge trigger so not minimised, then minimisining now they're officially summarised)
            #TODO: make a more sensical system v user summary tracking
            blob = json.loads(remoteMessage.json())['blob']
            for key, val in blob.items():
                if 'sourceIDs' in val:
                    for id in val['sourceIDs']:
                        for log in chatlog[convoID]:
                            if 'id' in log and log['id'] == id:
                                log['summarised'] = True
                                log['muted'] = True
                                log['minimised'] = True
                                remoteMessage = await prisma.message.find_first(
                                    where={'id': log['id']}
                                )
                            if remoteMessage:
                                updatedMessage = await prisma.message.update(
                                    where={ 'id': remoteMessage.id },
                                    data={
                                        'summarised': True,
                                        'muted': True,
                                        'minimised': True,
                                    }      
                                )

        payload = {'id':log['id'], 'fields' :{ 'summarised': True, 'muted': True, 'minimised': True,}}
        await  websocket.send(json.dumps({'event':'updateMessageFields', 'payload':payload}))
        # print('updated message' + str(log))
        log['summarised'] = True
        log['muted'] = True
        log['minimised'] = True
    eZprint('summary update complete', DEBUG_KEYS, 'summary')
    # print(chatlog[convoID])
    await  websocket.send(json.dumps({'event':'recieve_agent_state', 'payload':{'agent': 'system', 'state': ''}}))

    return True


async def get_sessions(convoID):
    sessionID = novaConvo[convoID]['sessionID']
    # print('getting sessions')
    logs = await prisma.log.find_many(
    where = {
        "UserID": novaSession[sessionID]['userID'],
    })
    
    sessions = 0
    
    if logs:
        # print('logs found')
        sessions = len(logs)
    first_date = ''
    last_date = ''
    for log in logs:
        if first_date == '':
            first_date = log.date
        if last_date == '':
            last_date = log.date
        if log.date < first_date:
            first_date = log.date
        if log.date > last_date:
            last_date = log.date

    novaSession[sessionID]['sessions'] = sessions
    novaSession[sessionID]['first_date'] = first_date
    novaSession[sessionID]['last_date'] = last_date

# async def main() -> None:
#     eZprint('running main')
#     ##setup for debug, using UID as key
#     await prisma.connect()
#     novaConvo['test'] = {}
#     novaConvo['test']['userID'] = '110327569930296986874'
#     # userID = '110327569930296986874'
#     debug['userID'] = False

#     await run_memory('test')

# if __name__ == '__main__':
#     asyncio.run(main())

past_convo_prompts = """These are summaries of past conversations, return a short concise summary of topics, outcomes, and insights."""



async def get_summary_children_by_key(childKey,convoID, sessionID, cartKey, client_loadout = None):
    eZprint('get summary children by key triggered', DEBUG_KEYS +['TRAVERSE'])
    # userID = novaSession[sessionID]['userID']   
    if client_loadout == current_loadout[sessionID]:
        summary = await get_summary_by_key(childKey, sessionID, client_loadout)
        content_to_return = None
        if summary:
            summary = json.loads(summary.json())['blob']
            summary_elements = []
            for key, val in summary.items():
                if 'epoch' in val:
                    # print (val)
                    if val['epoch'] > 1:
                        # print('epoch greater than')
                        if 'sourceIDs' in val:
                            for sourceID in val['sourceIDs']:
                                # print('sourceID found')
                                # print(sourceID)
                                child_summary = await get_summary_by_key(sourceID, sessionID, client_loadout)

                                if child_summary:
                                    # print('child summary found')
                                    # print(child_summary)
                                    child_summary = json.loads(child_summary.json())['blob']
                                    # print(child_summary)

                                    for childKey, childVal in child_summary.items():
                                        childVal.update({'type': 'summary'})
                                        # if val not in summary_elements:
                                        summary_elements.append(childVal)
                                        # print('content to return' + str(summary_elements)) 
                        content_to_return = {'parent':summary,'children': summary_elements, 'source' : 'summaries'}

                    elif 'meta' in val:
                        # print('meta found')
                        # if 'docID' in val['meta']:
                        #     print('conversation found')
                        return_messages = []
                        if 'sourceIDs' in val:
                            # print('sourceIDs found')
                            for sourceID in val['sourceIDs']:
                                # print('sourceID found')
                                message = None
                                if isinstance(sourceID, int):
                                    message = await prisma.message.find_first(
                                        where={
                                        'id': sourceID,
                                        }
                                    )
                                
                                if message == None:
                                    if isinstance(sourceID, str):
                                        message = await prisma.message.find_first(
                                            where={
                                            'key': str(sourceID),
                                            }
                                        )

                                # print('message match ' + str(message))
                                message_json = json.loads(message.json())
                                message_json.update({'type': 'message'})
                                return_messages.append(message_json)
                            content_to_return = {'parent': summary, 'children': return_messages, 'source' : 'messages' }
                                    
            if convoID in active_cartridges:
                cartVal = active_cartridges[convoID][cartKey]

            if 'blocks' not in cartVal:
                cartVal['blocks'] = {}
            if 'summaries' not in cartVal['blocks']:
                cartVal['blocks']['summaries'] = []
            cartVal['blocks']['summaries'].append({childKey:content_to_return})


            await  websocket.send(json.dumps({'event':'send_preview_content', 'payload':content_to_return}))  
            return content_to_return



async def get_summary_by_key(key, sessionID, client_loadout = None):
    
    if client_loadout == current_loadout[sessionID]:
        # print('getting summary by key')
        summary = None

        # print('trying string key')

        summary = await prisma.summary.find_first(
            where={
                'key': str(key)
            }   
        )

        
        if summary == None:

            # print('trying int key')
            summary = await prisma.summary.find_first(
                where={
                    'id': int(key)
                }   
            )

    return summary

async def get_overview (convoID, sessionID, cartKey, cartVal, client_loadout = None):
    
    response = ''
    cartVal['state'] = 'loading'
    cartVal['status'] = 'Getting overview'

    input = {
        'cartKey': cartKey,
        'sessionID': sessionID,
        'fields': {
            'state': cartVal['state'],
            'status': cartVal['status'],
            },
        }
    await update_cartridge_field(input,convoID, client_loadout, system=True)

    texts = []
    textString = ''
    if 'blocks' in cartVal:
        if 'summaries' in cartVal['blocks']:
            for summary in cartVal['blocks']['summaries']:
                for key, val in summary.items():
                    if 'title' in val:
                        textString += val['title'] + '\n'
                    if 'body' in val:
                        textString += val['body'] + '\n'
                    if 'timestamp' in val:
                        textString += val['timestamp'] + '\n'
                    if len(textString) > 7000:
                        texts.append(textString)
                        # print(textString)
                        textString = ''
    if textString != '':
        # print(textString)
        texts.append(textString)

    # print('text string length ' + str(len(textString)))
    for text in texts:
        # print('getting summary with prompt')
        userID = novaSession[sessionID]['userID']
        response += str(await get_summary_with_prompt(past_convo_prompts, text, 'gpt-3.5-turbo', userID)) + '\n\n'

    # response = await get_summary_with_prompt(past_convo_prompts, str(cartVal['blocks']['summaries']))
    # print('response is ' + str(response))
    cartVal['text'] = ''
    if response != '':
        if 'blocks' not in cartVal:
            cartVal['blocks'] = {}
        cartVal['blocks']['overview'] = str(response)
        # print('getting overview of summary')
        if client_loadout == current_loadout[sessionID]:
            cartVal['state'] = ''
            cartVal['status'] = ''
            input = { 
                'cartKey': cartKey,
                'sessionID': sessionID,
                'fields': {
                    'state': cartVal['state'],
                    'status': cartVal['status'],
                    'blocks': cartVal['blocks']
                },
                'loadout': client_loadout
            }
        await update_cartridge_field(input,convoID, client_loadout, system=True)

##attempt at abstracting parts of flow, general idea is that there is 'corpus' which is broken into 'chunks' which are then batched together on token size, to be summarised
## after this, the next 'corpus' is the summaries, that are then 'chunked' based on their source (each convo)
## content chunks ->normalised into candidates -> gropued into batches ->summarised, repeat

async def update_cartridge_summary(convoID, userID, cartKey, cartVal, sessionID, client_loadout= None):
    # print('update_cartridge_summary')
    window_counter = 0
    if 'blocks' not in cartVal:
        cartVal['blocks'] = {}
    if 'blocks' in cartVal:
        if isinstance(cartVal['blocks'], list):
            cartVal['blocks'] = {}
    # if client_loadout == current_loadout[sessionID]:
        # if 'blocks' not in cartVal:
    cartVal['state'] = 'loading'
    cartVal['status'] = 'Getting summaries'
    input = {
        'cartKey': cartKey,
        'sessionID': sessionID,
        'fields': {
            'state': cartVal['state'],
            'status': cartVal['status'],
            },
        }
    ##TODO: make it so only happens once per session?

    await update_cartridge_field(input,convoID, client_loadout, system=True)

    if userID+sessionID not in windows:
        windows[userID+sessionID] = []

    cartVal['blocks']['summaries'] = []
    for window in windows[userID+sessionID]:
        window_counter += 1
        # eZprint('window no ' + str(window_counter))
        for summary in window:   

            key = ''
            title = ''
            body = ''
            timestamp = ''
            epoch = ''
            keywords = ''
            if 'key' in summary:
                key = summary['key']
            if 'title' in summary:
                title = summary['title']
            if 'body' in summary:
                body = summary['body']
            if 'timestamp' in summary:
                timestamp = summary['timestamp']
            if 'epoch' in summary:
                epoch = summary['epoch']
            if 'keywords' in summary:
                keywords = summary['keywords']

            
            if 'blocks' not in cartVal:
                cartVal['blocks'] = {}
                if 'summaries' not in cartVal['blocks']:
                    cartVal['blocks']['summaries'] = []
            cartVal['blocks']['summaries'].append({key:{ 'title':title, 'body':body, 'timestamp':timestamp, 'epoch': "epoche: " + str(epoch), 'keywords':keywords}})

    # if client_loadout == current_loadout[sessionID]:
    active_cartridges[convoID][cartKey] = cartVal
    cartVal['state'] = ''
    cartVal['status'] = ''
    fields = {  
        'state': cartVal['state'],
        'status': cartVal['status'],
        'blocks': cartVal['blocks']
    }
    input = {
        'cartKey': cartKey,
        'sessionID': sessionID,
        'fields': fields,
    }
    await update_cartridge_field(input, convoID, client_loadout, system=True)

        # await  websocket.send(json.dumps({'event':'updateCartridgeFields', 'payload':payload}))    
