import json
import math
import asyncio
from prismaHandler import prisma
from prisma import Json
import secrets
from datetime import datetime
from cartridges import update_cartridge_field
from query import sendChat, get_summary_with_prompt, parse_json_string
from debug import eZprint, get_fake_messages, get_fake_summaries, debug
from sessionHandler import novaConvo, available_cartridges, chatlog, current_loadout
from appHandler import websocket
from keywords import get_keywords_from_summaries

summaries = {}
windows = {}

async def run_summary_cartridges(convoID, cartKey, cartVal,  loadout = None):
    userID = novaConvo[convoID]['userID']
    if loadout == current_loadout[convoID]:                
        if 'blocks' not in cartVal:
            cartVal['blocks'] = {}
        await get_summaries(userID, convoID, loadout)
        await update_cartridge_summary(userID, cartKey, cartVal, convoID, loadout)
        if 'values' not in cartVal:
            cartVal['values'] = [{'initial_overview': True}, {'max_tokens': 500}]
            
        # for value in cartVal['values']:
        #     if 'initial_overview' in value:
        #         if value['initial_overview'] == True:
        #             if cartVal['blocks']:
        #                 await get_overview(convoID, cartKey, cartVal, loadout)

        await summarise_convos(convoID, cartKey, cartVal, loadout)
        await get_summaries(userID, convoID, loadout)
        await update_cartridge_summary(userID, cartKey, cartVal, convoID, loadout)
        # await get_keywords_from_summaries(convoID, cartKey, cartVal, loadout)

async def summarise_convos(convoID, cartKey, cartVal, loadout= None):

    eZprint('summarising convos')
    userID = novaConvo[convoID]['userID']

    if novaConvo[convoID]['owner']:
        if loadout == current_loadout[convoID]:
            cartVal['state'] = 'loading'
            payload = { 'key': 
                       cartKey,'fields': {
                        'state': cartVal['state'],
                            },
                        'loadout': loadout
                        }
            await  websocket.send(json.dumps({'event':'updateCartridgeFields', 'payload':payload}))        
        await summarise_messages(userID, convoID, loadout)
        print('summarise messages finished')
        await summarise_epochs(userID, convoID, loadout)

        # for value in cartVal['values']:
        #     if 'initial_overview' in value:
        #         if value['initial_overview'] == True:
        #             if cartVal['blocks']:
        #                 await get_overview(convoID, cartKey, cartVal, loadout)
    

        
async def get_summary_children_by_key(childKey, convoID, cartKey, loadout = None):
    print('get summary children by key triggered')
    userID = novaConvo[convoID]['userID']   
    if loadout == current_loadout[convoID]:
        summary = await get_summary_by_key(childKey, convoID, loadout)
        content_to_return = None
        if summary:
            summary = json.loads(summary.json())['blob']
            summary_elements = []
            for key, val in summary.items():
                if 'epoch' in val:
                    print (val)
                    if val['epoch'] > 1:
                        print('epoch greater than')
                        if 'sourceIDs' in val:
                            for sourceID in val['sourceIDs']:
                                print('sourceID found')
                                print(sourceID)
                                child_summary = await get_summary_by_key(sourceID, convoID, loadout)

                                if child_summary:
                                    print('child summary found')
                                    # print(child_summary)
                                    child_summary = json.loads(child_summary.json())['blob']
                                    # print(child_summary)

                                    for childKey, childVal in child_summary.items():
                                        childVal.update({'type': 'summary'})
                                        # if val not in summary_elements:
                                        summary_elements.append(childVal)
                                        print('content to return' + str(summary_elements)) 
                        content_to_return = {'parent':summary,'children': summary_elements, 'source' : 'summaries'}

                    elif 'meta' in val:
                        print('meta found')
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

                                print('message match ' + str(message))
                                message_json = json.loads(message.json())
                                message_json.update({'type': 'message'})
                                return_messages.append(message_json)
                            content_to_return = {'parent': summary, 'children': return_messages, 'source' : 'messages' }
                                    
            if convoID in available_cartridges:
                cartVal = available_cartridges[convoID][cartKey]

            if 'blocks' not in cartVal:
                cartVal['blocks'] = {}
            if 'summaries' not in cartVal['blocks']:
                cartVal['blocks']['summaries'] = []
            cartVal['blocks']['summaries'].append({childKey:content_to_return})


            await  websocket.send(json.dumps({'event':'send_preview_content', 'payload':content_to_return}))  

async def get_summary_by_key(key, convoID, loadout = None):
    
    if loadout == current_loadout[convoID]:
        print('getting summary by key')
        summary = None

        print('trying string key')

        summary = await prisma.summary.find_first(
            where={
                'key': str(key)
            }   
        )

        if summary == None:

            print('trying int key')
            summary = await prisma.summary.find_first(
                where={
                    'id': int(key)
                }   
            )
        if summary == None:
            print('summary not found')
        else:
            print(summary)
            print('summary found')
    return summary

async def get_overview (convoID, cartKey, cartVal, loadout = None):
    response = ''
    if loadout == current_loadout[convoID]:
        cartVal['state'] = 'loading'
        cartVal['status'] = 'Getting overview'
        payload = { 'key': cartKey,'fields': {
                    'state': cartVal['state'],
                    'status': cartVal['status'],
                        },
        'loadout': loadout}
        ##TODO: make it so only happens once per session?
        await  websocket.send(json.dumps({'event':'updateCartridgeFields', 'payload':payload}))  
        response = await get_summary_with_prompt(past_convo_prompts, str(cartVal['blocks']['summaries']))
        # print('response is ' + str(response))
        cartVal['text'] = ''
    if response != '':
        if 'blocks' not in cartVal:
            cartVal['blocks'] = {}
        cartVal['blocks']['overview'] = response
        # print('getting overview of summary')
        if loadout == current_loadout[convoID]:
            cartVal['state'] = ''
            cartVal['status'] = ''
            payload = { 
                'key': cartKey,
                'fields': {
                    'state': cartVal['state'],
                    'status': cartVal['status'],
                    'text': cartVal['text']
                },
                'loadout': loadout
            }
            await update_remote_cartridge(cartKey, cartVal)
            ##TODO: make it so only happens once per session?
            await  websocket.send(json.dumps({'event':'updateCartridgeFields', 'payload':payload}))  

async def update_remote_cartridge(cartKey, cartVal):
    matchedCart = await prisma.cartridge.find_first(
        where={
        'key':
        {'equals': cartKey}
        },         
    )
    if matchedCart:
        updatedCart = await prisma.cartridge.update(
            where={ 'id': matchedCart.id },
            data={
                'blob' : Json({cartKey:cartVal})
            }
        )

##attempt at abstracting parts of flow, general idea is that there is 'corpus' which is broken into 'chunks' which are then batched together on token size, to be summarised
## after this, the next 'corpus' is the summaries, that are then 'chunked' based on their source (each convo)
## content chunks ->normalised into candidates -> gropued into batches ->summarised, repeat

async def update_cartridge_summary(userID, cartKey, cartVal, convoID, loadout= None):
    # print('update_cartridge_summary')
    window_counter = 0
    if 'blocks' not in cartVal:
        cartVal['blocks'] = {}
    if 'blocks' in cartVal:
        if isinstance(cartVal['blocks'], list):
            cartVal['blocks'] = {}
    if loadout == current_loadout[convoID]:
        # if 'blocks' not in cartVal:
        cartVal['state'] = 'loading'
        cartVal['status'] = 'Getting summaries'
        payload = { 'key': cartKey,
                'fields': {
                    'state': cartVal['state'],
                        },
                    'loadout': loadout
                    }

        await  websocket.send(json.dumps({'event':'updateCartridgeFields', 'payload':payload}))    
    
    if userID+convoID not in windows:
        windows[userID+convoID] = []

    cartVal['blocks']['summaries'] = []
    for window in windows[userID+convoID]:
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
            cartVal['blocks']['summaries'].append({key:{ 'title':title, 'body':body[0:280], 'timestamp':timestamp, 'epoch': "epoche: " + str(epoch), 'keywords':keywords}})

    if loadout == current_loadout[convoID]:
        available_cartridges[convoID][cartKey] = cartVal
        cartVal['state'] = ''
        cartVal['status'] = ''
        payload = { 
                    'key': cartKey,
                    'fields': {
                            'status': cartVal['status'],
                            'blocks':cartVal['blocks'],
                            'state': cartVal['state'],
                            },
                        'loadout': loadout

                    }

        await update_remote_cartridge(cartKey, cartVal)

        await  websocket.send(json.dumps({'event':'updateCartridgeFields', 'payload':payload}))    

  
##LOG SUMMARY FLOWS
## gets messages normalised into 'candidates' with all data needed for summary
async def summarise_messages(userID, convoID, loadout = None):  
    eZprint('getting messages to summarise')
    ##takes any group of candidates and turns them into summaries
    messages = []
    remote_messages = await prisma.message.find_many(
            where={
            'UserID': userID,
            'summarised': False
            }
    )

    conversations = await prisma.log.find_many(
            where={
            'UserID': userID,
            }
    )
    
    messages = []
    for message in remote_messages:
        splitID = message.SessionID.split('-')
        if len(splitID) >=3:
            if splitID[2] == loadout:
                messages.append(message)
        elif loadout == None:
            messages.append(message)

    normalised_convos = []
    meta = ' '


    ids = []
    conversation_string = ''
    for conversation in conversations:
        if conversation.id > 1600:
            break
        for message in messages:
            if message.SessionID == conversation.SessionID:
                # print('found message match')
                # print(message)
                if meta == ' ':
                    format = '%Y-%m-%dT%H:%M:%S.%f%z'
                    date = datetime.strptime(message.timestamp, format)
                    meta = {
                        'docID': conversation.SessionID,
                        'timestamp': message.timestamp,
                        'type' : 'message',
                        'corpus' : 'loadout-conversations'
                    }
                name = message.name.strip()
                if name.lower() != 'sam':
                    name = 'Nova'
                conversation_string += name +': '+ message.body + '\n' + message.timestamp + '\n\n'
                ids.append(message.id)

                if len(conversation_string) > 7000:
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
                            'meta' : meta
                        })
                        i += range
                        
                    conversation_string = ''
                    ids = []
    if conversation_string != '':
        # eZprint('logging conversation with unsumarised messages\n' + f'{conversation_string}')
            print('adding on last bit of convo')
            print(str(len(conversation_string)))
            normalised_convos.append({
                'ids': ids,
                'toSummarise': conversation_string,
                'epoch' : 0,
                'meta' : meta

            })


    await summarise_batches(normalised_convos, userID, convoID, loadout, conversation_summary_prompt)


async def update_record(record_ID, record_type, convoID, loadout = None):
    # eZprint('updating record')

    if record_type == 'message':
        # print('record type is message')
        updated_message = await prisma.message.update(
            where={
                'id': record_ID,
            },
            data={
                'summarised': True,
                'minimised': True,
                'muted': True,            
            }
        )

    if record_type == 'summary':
        # print('record type is summary')
        target_summary = await prisma.summary.find_first(
            where={
            'id': record_ID,
            }
        )
        summary_blob = json.loads(target_summary.json())['blob']
        for key, val in summary_blob.items():
            val['summarised'] = True
            val['minimised'] = True
            val['muted'] = True

        updated_summary = await prisma.summary.update(
            where={ 'id': record_ID },
            data={
                'blob': Json({key:val}),
            }
        )
 
##GROUP SUMMARY FLOWS
async def summarise_batches(batches, userID, convoID, loadout = None, prompt = "Summarise this text."):
    eZprint('summarising batches, number of batches ' + str(len(batches)))
    ##takes normalised text from different sources, runs through assuming can be summarised, and creates summary records (this allows for summaries of summaries for the time being)
    
    counter = 0
    for batch in batches:
        print('batch number ' + str(counter))
        counter += 1
        epoch = batch['epoch'] +1
        summary = await get_summary_with_prompt(prompt, str(batch['toSummarise']))
        summaryID = secrets.token_bytes(4).hex()
        eZprint('summary complete')
        # print(summary)
        await create_summary_record(userID, batch['ids'], summaryID, summary, epoch, batch['meta'], convoID, loadout)


        # except:
        # print('error creating summary record')



async def create_summary_record(userID, sourceIDs, summaryID, summary, epoch, meta = {}, convoID = '', loadout =None):
    # print(summary)
    eZprint('creating summary record')
    print(summary)
    summarDict = await parse_json_string(summary)
    success = True
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
        summarDict.update({'key': summaryID})
        
        SessionID = convoID
        if loadout:
            SessionID += "-"+convoID+"-"+str(loadout)

        summary = await prisma.summary.create(
            data={
                "key": summaryID,
                'SessionID' : SessionID,
                "UserID": userID,
                "timestamp": datetime.now(),
                "blob": Json({summaryID:summarDict})

            }
        )

    # if success:
    for id in sourceIDs:
        await update_record(id, meta['type'], convoID, loadout)    

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

    if 'keywords' in summarDict:
        summaryString += '\nKeywords: '
        for keyword in summarDict['keywords']:
            summaryString += keyword + ', '
        summaryString += '\n'
        
    notes = ''
    if 'notes' in summarDict:
        for key, val in summarDict['notes'].items():
            notes += '-'+str(key) + ': ' + str(val) + '\n'

    if notes != '':
        # print('notes found adding title')
        summaryString += '\nNotes:\n' + notes

    insights = ''
    if 'insights' in summarDict:
        for key, val in summarDict['insights'].items():
            if isinstance(val, dict):
                for key2, val2 in val.items():
                    summaryString += '-'+str(key2) + ': ' + str(val2) + '\n'


    if insights != '':
        # print('insights found adding title')
        summaryString += '\nInsights:\n' + insights 


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

async def summarise_epochs(userID, convoID, loadoutID = None):
    ##number of groups holding pieces of content at different echelons, goes through echelons, summarises in batches if too full (bubbles up) and restarts
    eZprint('starting epoch summary')



    epoch_in_window = False

    while epoch_in_window == False:

        epochs = {}

        candidates = await prisma.summary.find_many(
            where={
            'UserID': userID,
            }
        ) 

        loadout_candidates = []
        for candidate in candidates:
            # print(candidate.SessionID)
            splitID = candidate.SessionID.split('-')
            # print(splitID)
            if len(splitID) >= 2:
                if splitID[2] == loadoutID:
                    # print('found loadout candidate')
                    loadout_candidates.append(candidate)
            elif loadoutID  == None:
                # print('adding on a none loadout')
                loadout_candidates.append(candidate)

        print('setting epoch_in_window to true')
        epoch_in_window = True
        for candidate in loadout_candidates:
            summary = json.loads(candidate.json())['blob']

            for key, val in summary.items():
                # print('key and val' + str(key) + str(val))
                if 'summarised' in val:
                    if val['summarised'] == True:
                        continue
                    # print('found summary candidate' + str(val))
                    epoch_no = 'epoch_' + str(val['epoch'])
                    val.update({'id': candidate.id})
                    # eZprint('found summary candidate')
                    if epoch_no not in epochs:
                        # eZprint('creating epoch ' + str(epoch_no))
                        epochs[epoch_no] = []
                    epochs[epoch_no].append(val)
        ## number of pieces of content per window 

        resolution = 2
        # print(f'{epochs}')
        
        epoch_summaries = 0

        batches = []

        for key, val in epochs.items():
            epoch = val
            eZprint('epoch is ' + key) 
            # print(epoch)
            #checks if epoch is 70% over resolution
            
            #switching to 'windows' being based on token size, so resolution is 3 blocks of 10k
            # eZprint('epoch too large, starting epoch batch and summarise')
            ## if any epoch has too many summaries it'll go through and summarise to resolution specified, and then restart whole thing... will see if we can make more elegant, but can't think of how else apart from removing from that 
            toSummarise = ''
            ids = []
            x = 0
            meta = ''
            print('epoch len ' + str(len(epoch)))
            for summary in epoch:
                x += 1
                ##goes through and creates batches in reverse
                eZprint('creating candidate  ' + str(x) + ' of epoch ' + str(key))
                summaryObj = await summary_into_candidate(summary)
                timestamp = ''
                if 'timestamp' in summaryObj:
                    timestamp = summaryObj['timestamp']
                if meta == '':
                    meta = {
                        'first-doc' : timestamp,
                        'type' : 'summary',
                        'corpus' : 'loadout-conversations',
                        'docID' : loadoutID
                    }
                toSummarise += str(summaryObj['content']) + '\n'
                ids.append(summary['id'])

                if len(toSummarise) > 7000:
                    print('adding to batch')
                    meta['last-doc'] = timestamp
                    batches.append({
                        'toSummarise' : toSummarise,
                        'ids' : ids,
                        'meta' : meta,
                        'epoch' : summaryObj['epoch']

                    })
                    timestamp = ''
                    toSummarise = ''
                    ids = []
                    meta = ''
            print('epoch summarised looped')
            if len(batches) > 0:
                await summarise_batches(batches, userID, convoID, loadoutID, summary_batch_prompt)
                batches = []
                print('summarising batches so setting to false to trigger reloop')
                epoch_in_window = False

    print('epoch summarised outside while should be past while loop')
    
       

async def get_summaries(userID, convoID, loadoutID):

    eZprint('getting summaries')
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
        if(len(splitID) >= 2):
            if splitID[2] == loadoutID:
                # print('loadout ID found')
                summary_candidates.append(summary)
        elif loadoutID == None:
            # print('adding on a none loadout')
            summary_candidates.append(summary)

    summaries = summary_candidates

    windows[userID+convoID] = []
    epochs = {}
    for summary in summaries:
        summaryObj = dict(summary.blob)

        for key, val in summaryObj.items():
            if 'summarised' in val:
                if val['summarised'] == True:
                    continue
                # eZprint('found summary candidate')

                val.update({'key': summary.key})
                epoch_no = 'epoch_' + str(val['epoch'])
                if val['epoch'] not in epochs:
                    # eZprint('creating epoch ' + str(epoch_no))
                    epochs[val['epoch']] = []
                epochs[val['epoch']].append(val)
        
    if userID not in windows:
        windows[userID+convoID] = []

    resolution = 3
    window = []
    sorted_epochs = sorted(epochs.items(), key=lambda x: x[0])
    # print(sorted_epochs)
    for epochs in sorted_epochs:
        (epoch_no, summaries) = epochs
        counter = 0
        for summary in reversed(summaries):
            # print(summary)
            window.append(summary)
            counter += 1
            if counter >= resolution - 1:
                windows[userID+convoID].append(window)
                window = []
                counter = 0
    if window != []:
        windows[userID+convoID].append(window)

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
"timestamp" : "[Time, Date, or Date Range]",
"body": "[Synthesis of topics, decisions, and discoveries across conversations]", 
"keywords": ["Keyword1", "Keyword2", "Keyword3"],
"notes": {
    "[Note Title1]": "[Note Body1]",
    "[Note Title2]": "[Note Body2]"
}
}

Ensure that the summary captures the broad strokes of all conversations in one synthesis. Make sure that the above format is followed exactly, and can be read by json.dumps, ensuring all response is inside of the brackets. Ensure all conversation summaries are combined into one single summary.
"""

async def summarise_percent(convoID, percent):
    eZprint('summarising percent')
    summaryID = secrets.token_bytes(4).hex()
    to_summarise = []
    counter = 0
    max = len(chatlog[convoID]) * percent
    for log in chatlog[convoID]:
        if 'summarised' not in log:
            if counter <= max:
                # eZprint('adding to summarise' + str(log['ID'] + ' ' + log['body']))
                to_summarise.append(log['ID'])
                counter += 1

    summary_block = {
        'convoID': convoID,
        'messageIDs': to_summarise,
        'summaryID': summaryID,
    }

    payload = {'summaryID':summaryID, 'messages': to_summarise}
    await  websocket.send(json.dumps({'event':'create_summary', 'payload':payload}))

    await summariseChatBlocks(summary_block)

async def summarise_from_range(convoID, start, end):

    start = int(start)
    end = int(end)
    eZprint('summarising from range')
    summaryID = secrets.token_bytes(4).hex()
    to_summarise = []
    print(chatlog[convoID])

    counter = 0
    for log in chatlog[convoID]:
        if 'summarised' not in log:
        # print(log)
            if log['summarised'] == False:
                if counter >= start and counter <= end:
                    # eZprint('adding to summarise' + str(log['ID'] + ' ' + log['body']))
                    to_summarise.append(log['ID'])
        counter += 1

    summary_block = {
        'convoID': convoID,
        'messageIDs': to_summarise,
        'summaryID': summaryID,
    }

    payload = {'summaryID':summaryID, 'messages': to_summarise}
    await  websocket.send(json.dumps({'event':'create_summary', 'payload':payload}))
    summary_result = await summariseChatBlocks(summary_block)
    return summary_result



async def summariseChatBlocks(input,  loadout = None):
    eZprint('summarising chat blocks')
    convoID = input['convoID']
    messageIDs = input['messageIDs']
    summaryID = input['summaryID']
    userID = novaConvo[convoID]['userID']
    messages_string = ''
    messagesToSummarise = []
    start_message = None
    for messageID in messageIDs:
        for log in chatlog[convoID]:
            if messageID == log['ID']:
                messagesToSummarise.append(log)
                if start_message == None:
                    start_message = log
                if 'name' in log:
                    messages_string += str(log['name']) + ': '
                if 'title' in log:
                    messages_string += str(log['title']) + ': '
                if 'body' in log:
                    messages_string += str(log['body'])
                if 'timestamp' in log:
                    messages_string += ' ' + str(log['timestamp'])
                messages_string += '\n'
                
                
    print(messages_string)
    print(len(messages_string))
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
    summary = await get_summary_with_prompt(prompt, str(messages_string))
    #wait for 2 seconds
    print(summary)
    summarDict = json.loads(summary)
    # print(summarDict)
    fields = {}
    for key, value in summarDict.items():
      fields[key] = value
    fields['state'] = ''
    payload = {'ID':summaryID, 'fields':fields}
    await  websocket.send(json.dumps({'event':'updateMessageFields', 'payload':payload}))
    date = datetime.now()
    # summarDict.update({'sources':messageIDs})
    meta = {
        'overview': 'Conversation section from conversation ' + str(date),

    }    
    # print(summarDict)

    await create_summary_record(userID, messageIDs,summaryID, summary, 0, meta, convoID, loadout)
    # print(summary)
   #inject summary object into logs before messages it is summarising 
    injectPosition = chatlog[convoID].index(start_message) 
    chatlog[convoID].insert(injectPosition, {'ID':summaryID, 'name': 'summary', 'title':summarDict['title'], 'role':'user', 'body': summarDict['body'],'timestamp':datetime.now(),'summaryID':summaryID})
    # print(chatlog[convoID])
    for log in messagesToSummarise:
        remoteMessage = await prisma.message.find_first(
            where={'key': log['ID']}
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
            log['summarised'] = True
            log['muted'] = True
            log['minimised'] = True
            payload = {'ID':log['ID'], 'fields' :{ 'summarised': True, 'muted': True, 'minimised': True,}}
            await  websocket.send(json.dumps({'event':'updateMessageFields', 'payload':payload}))
    # print(chatlog[convoID])
    return True


async def get_sessions(convoID):
    
    print('getting sessions')
    logs = await prisma.log.find_many(
    where = {
        "UserID": novaConvo[convoID]['userID'],
    })
    
    sessions = 0
    
    if logs:
        print('logs found')
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

    novaConvo[convoID]['sessions'] = sessions
    novaConvo[convoID]['first_date'] = first_date
    novaConvo[convoID]['last_date'] = last_date

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

past_convo_prompts = """This is an overview of previous conversations. Review for any key information, actions or points of interest for this conversation and return your notes."""




