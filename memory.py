import json
import math
import asyncio
from prismaHandler import prisma
from prisma import Json
import secrets
from datetime import datetime
from query import sendChat
from debug import eZprint, get_fake_messages, get_fake_summaries, debug
from sessionHandler import novaConvo, availableCartridges, chatlog
from appHandler import websocket

summaries = {}
windows = {}

##attempt at abstracting parts of flow, general idea is that there is 'corpus' which is broken into 'chunks' which are then batched together on token size, to be summarised
## after this, the next 'corpus' is the summaries, that are then 'chunked' based on their source (each convo)
## content chunks ->normalised into candidates -> gropued into batches ->summarised, repeat

async def update_cartridge_summary(userID, cartKey, cartVal, convoID):

    window_counter = 0
    if 'blocks' not in cartVal:
        cartVal['blocks'] = []
    cartVal['state'] = 'loading'
    cartVal['status'] = ''
    payload = { 'key': cartKey,'fields': {
                'state': cartVal['state']
                    }}

    await  websocket.send(json.dumps({'event':'updateCartridgeFields', 'payload':payload}))    
    
    if userID+convoID not in windows:
        windows[userID+convoID] = []

    for window in windows[userID+convoID]:
        window_counter += 1
        # eZprint('window no ' + str(window_counter))
        for summary in window:   

            # if 'keywords' not in summary:
            #     summary['keywords'] = []
            # print(summary['title'] +' ' + str(summary['epoch']))
            cartVal['blocks'].append({'key':summary['key'], 'title':summary['title'], 'body':summary['body'], 'timestamp':summary['timestamp']})

    availableCartridges[convoID][cartKey] = cartVal
    cartVal['state'] = ''

    payload = { 'key': cartKey,'fields': {
                                'status': cartVal['status'],
                                'blocks':cartVal['blocks'],
                                'state': cartVal['state']
                                    }}
            
    await  websocket.send(json.dumps({'event':'updateCartridgeFields', 'payload':payload}))    


async def summarise_convos(convoID, cartKey, cartVal, ):
    userID = novaConvo[convoID]['userID']
    debug[userID+convoID] = False


    # return
    if novaConvo[convoID]['owner']:

        
        await summarise_messages(userID, convoID)
        eZprint('messages summarised')

        # await get_summaries(userID, convoID)
        # await update_cartridge_summary(userID, cartKey, cartVal, convoID)

        # await summarise_groups(userID, convoID)    
        # await update_cartridge_summary(userID, cartKey, cartVal, convoID)

        eZprint('groups summarised')

        # await get_summaries(userID, convoID)
        # await update_cartridge_summary(userID, cartKey, cartVal, convoID)

        
        windows[userID+convoID] = []
        epochs_summarised = await summarise_epochs(userID, convoID)
        while not epochs_summarised:
            await asyncio.sleep(1)
            # print('epoch overloaded')
            # await get_summaries(userID, convoID)
            # await update_cartridge_summary(userID, cartKey, cartVal, convoID)
            epochs_summarised = await summarise_epochs(userID, convoID)

        
        # await get_summaries(userID, convoID)
        # await update_cartridge_summary(userID, cartKey, cartVal, convoID)

    

    cartVal['state'] = ''
    cartVal['status'] = ''
    payload = { 'key': cartKey,'fields': {
                'state': cartVal['state'],
                'status': cartVal['status']
                    }}

    await  websocket.send(json.dumps({'event':'updateCartridgeFields', 'payload':payload}))   
        # await update_cartridge_summary(userID, cartKey, cartVal, convoID)
        
  
##LOG SUMMARY FLOWS
## gets messages normalised into 'candidates' with all data needed for summary
async def summarise_messages(userID, convoID):  
    # eZprint('getting messages to summarise')
    ##takes any group of candidates and turns them into summaries
    messages = []
    if debug[userID+convoID]:
        messages = await get_fake_messages()
    else :
        messages = await prisma.message.find_many(
                where={
                'UserID': userID,
                'summarised': False
                }
        )

        logs = await prisma.log.find_many(
                where={
                'UserID': userID,
                }
        )

    normalised_messages = []
    batches = []
    # eZprint('organising and normalising for batch')
    #gets all messages as normalised and readable for batch 
    novaConvo[convoID]['pastConvos'] = len(logs)
    counter = 0
    for log in logs:
        # if log.id < 800:
        #     continue
        meta = ' '
        normalised_messages = []
        for message in messages:
            if log.SessionID == message.SessionID:
                if meta == ' ':
                    format = '%Y-%m-%dT%H:%M:%S.%f%z'
                    date = datetime.strptime(message.timestamp, format)
                    meta = {
                        'overview': 'Conversation section from conversation ID: ' + str(log.id) + ' on ' + str(date),
                        'docID': log.id,
                        'timestamp': message.timestamp,
                    }
                    counter += 1

                normalised_messages.append({
                    'id': message.id,
                    'content': message.name+': '+ message.body + '\n',
                    'epoch' : 0,
                    'type' : 'message'        
                })
        if len(normalised_messages) > 0:
            # print(meta)
            batches += await create_content_batches_by_token(normalised_messages, meta)
   
    await summarise_batches(batches, userID, convoID)

    for batch in batches:
        for id in batch['ids']:
            remote_messages = await prisma.message.find_first(
            where={'id': id}
            )
            if remote_messages:
                updatedMessage = await prisma.message.update(
                    where={ 'id': remote_messages.id },
                    data={
                        'summarised': True,
                        'muted': True,
                        'minimised': True,
                    }
                )



async def create_content_batches_by_token(content, meta):

    ## takes document, breaks into chunks of 2000 tokens, and returns a list of chunks
    ## returns with expected values, to summarise is text, id's is the source ID's
    # eZprint('creating content batches by token')
    tokens = 0
    batches = []
    toSummarise = meta['overview'] + ' \n'
    ids = []
    docID = ''
    epoch = 0

    #assumes parent level and child level? or per 'document' but document agnostic
    for chunk in content:
        epoch = chunk['epoch']
        tokens += len(str(chunk['content']))
        toSummarise += chunk['content']
        ids.append(chunk['id'])
        if tokens > 10000:
            batches.append({
                'toSummarise': toSummarise,
                'ids': ids,
                'epoch': epoch,
                'meta': meta
            })
            tokens = 0
            toSummarise = ''
            ids = []
    
    ##catches last lot that didn't tick over and get added
    batches.append({
        'toSummarise': toSummarise,
        'ids': ids, 
        'epoch': epoch,
        'meta': meta

    })
   
    return batches


##GROUP SUMMARY FLOWS

async def summarise_batches(batches, userID, convoID):
    # eZprint('summarising batches, number of batches ' + str(len(batches)))
    ##takes normalised text from different sources, runs through assuming can be summarised, and creates summary records (this allows for summaries of summaries for the time being)
    counter = 0
    if userID not in summaries:
        summaries[userID+convoID] = []
    for batch in batches:
        # print('epoch on get' + str(batch['epoch']))
        counter += 1
        eZprint('summarising batch no ' + str(counter) + 'of' + str(len(batches)))
        epoch = batch['epoch'] +1
        
        if debug[userID+convoID]:
            summary = await get_fake_summaries(batch)
            # summarDict = json.loads(summary)
            summary.update({'sourceIDs' : batch['ids']})
            summary.update({'epoch': epoch})
            summary.update({'summarised':False})
            summaryID = secrets.token_bytes(4).hex()
            summary.update({'key':summaryID})
            summaryObj = {
                'key': summaryID,
                'userID' : userID,
                'blob': summary
            }
            summaries[userID+convoID].append(summaryObj)
            for summary in summaries[userID+convoID]:
                for id in batch['ids']:
                    if summary['id'] == id:
                        summary['blob']['summarised'] = True
            
            # for summary in summaries[userID]:
            #     print(summary['blob']['summarised'])
        else:
            try:
            # print(batch)
                # summary = await get_fake_summaries(batch)
                summary = await get_summary_with_prompt(batch_summary_prompt, str(batch['toSummarise']))
                summaryID = secrets.token_bytes(4).hex()
                await create_summary_record(userID, batch['ids'], summaryID, epoch, summary, batch['meta'])
            except:
                pass
                # print('error creating summary record')
            #sending summary state back to server


async def get_summary_with_prompt(prompt, textToSummarise):

    promptObject = []
    promptObject.append({'role' : 'system', 'content' : prompt})
    promptObject.append({'role' : 'user', 'content' : textToSummarise})
    # print(textToSummarise)
    # model = app.session.get('model')
    # if model == None:
    #     model = 'gpt-3.5-turbo'
    response = await sendChat(promptObject, 'gpt-3.5-turbo')
    # print(response)
    try:
        return response["choices"][0]["message"]["content"]
    except:
        return response


async def create_summary_record(userID, sourceIDs, summaryID, epoch, summary, meta, convoID = ''):
    # eZprint('creating summary record')
    summarDict = json.loads(summary)
    summarDict.update({'sourceIDs' : sourceIDs})
    summarDict.update({'meta': meta})
    summarDict.update({'epoch': epoch})
    summarDict.update({'summarised': False})
    summarDict.update({'key': summaryID})
    
    summary = await prisma.summary.create(
        data={
            "key": summaryID,
            "UserID": userID,
            "timestamp": datetime.now(),
            'SessionID' : convoID,
            "blob": Json({summaryID:summarDict})

        }
    )


async def summarise_groups(userID, convoID, field = 'docID'):
    ## finds summaries based on their group (so in this instance doc type) and summarises together, but could be extended to saydifferent doc values

    summary_groups = {}
    
    if debug[userID+convoID]:
        candidates = summaries[userID+convoID]
    else:
        candidates = await prisma.summary.find_many(
            where={
            'UserID': userID,
            }
        ) 
        
    ##group by 'content ID' (which is parent doc) - then loop here based on that (so can be used)
    for candidate in candidates: 
        # print(candidate)
        #finds summaries assoiated with logs, preps for summary
        summary = dict(candidate.blob)

        for key, val in summary.items():
            if 'epoch' in val:
                val.update({'key':key})
                val.update({'id':candidate.id})
                if 'summarised' in val:
                    if val['summarised'] == True or val['epoch'] != 1:
                        continue
                # print('found messages summary to summarise')
                summaryObj = await summary_into_candidate(val)
                # print(val['meta'])
                if not val['meta'][field] in summary_groups:
                    summary_groups[val['meta'][field]] = []
                    print ('creating new group for ' + str(val['meta'][field]) + '')
                summary_groups[val['meta'][field]].append(summaryObj)

    batches = []

    for key, val in summary_groups.items():

        meta = ' '
        toSummarise = ''
        ids = []
        
        for chunk in val:
            if meta == ' ':
                format = '%Y-%m-%dT%H:%M:%S.%f%z'
                date = datetime.strptime(chunk['meta']['timestamp'], format)                
                meta = {
                    'overview' : 'summaries from conversation held ' + str(date),
                    'timestamp' : chunk['meta']['timestamp'],
                }

            epoch = chunk['epoch']
            if toSummarise == '':
                toSummarise += meta['overview'] + '\n'
            toSummarise += str(chunk['content'])
            ids.append(chunk['id'])
            
        batches.append({
                'toSummarise': toSummarise,
                'ids': ids,
                'epoch' : epoch,
                'meta' : meta,
                'type':'partial_doc'   
            })
            
    await summarise_batches(batches,userID, convoID)
    
    # eZprint('number of batches is ' + str(len(batches)))
    for batch in batches:
        for id in batch['ids']:
            summary = dict(candidate.blob)
            for key, val in summary.items():
                val['summarised'] = True
            updated_summary = await prisma.summary.update(
                where={ 'id': id },
                data={
                    "blob": Json({key:val})
                }
            )
          

##MOST GENERIC SUMMARY FUNCTIONS

async def summary_into_candidate(summarDict ):
    ##turns summary objects themselves into candidates for summary
    summaryString = str(summarDict['title'])+ '\n' + str(summarDict['body']) + '\n' + str(summarDict['timestamp'])

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
    }
    
    return candidate




async def summarise_epochs(userID, convoID):

    ##number of groups holding pieces of content at different echelons, goes through echelons, summarises in batches if too full (bubbles up) and restarts
    eZprint('starting epoch summary')

    if debug[userID+convoID]:
        candidates = summaries[userID+convoID]

    else:
        candidates = await prisma.summary.find_many(
            where={
            'UserID': userID,
            }
        ) 

    epochs = {}

    for candidate in candidates:
        summary = dict(candidate.blob)

        for key, val in summary.items():
            if 'summarised' in val:
                if val['summarised'] == True:
                    continue
                epoch_no = 'epoch_' + str(val['epoch'])
                val.update({'id': candidate.id})
                val.update({'timestamp': candidate.timestamp})
                if epoch_no not in epochs:
                    eZprint('creating epoch ' + str(epoch_no))
                    epochs[epoch_no] = []
                epochs[epoch_no].append(val)
    
    window_no = 3
    if userID not in windows:
        windows[userID+convoID] = []

    ## number of pieces of content per window 
    resolution = 3
    # print(f'{epochs}')
    
    epoch_summaries = 0
    window = []


    for key, val in epochs.items():
        epoch = val
        # print(epoch)
        #checks if epoch is 70% over resolution
        if len(epoch) >= ((resolution*2)-1):
            epoch_summaries += 1
            # eZprint('epoch too large, starting epoch batch and summarise')
            ## if any epoch has too many summaries it'll go through and summarise to resolution specified, and then restart whole thing... will see if we can make more elegant, but can't think of how else apart from removing from that 
            batches = []
            toSummarise = ''
            ids = []
            x = 0
            counter = 0
            meta = ' '
            for summary in epoch:
                ##goes through and creates batches in reverse
                # eZprint('summarising chunk ' + str(x) + ' of epoch ' + str(key))
                summaryObj = await summary_into_candidate(summary)
                format = '%Y-%m-%dT%H:%M:%S.%f%z'
                # date = datetime.strptime(summary['timestamp'], format)  
                date =''  
                if meta == ' ':
                    meta = {
                        'overview' : 'Summaries of docoument summaries starting from ' + str(date),
                        'first-doc' : summary['timestamp'],
                    }
                toSummarise += str(summaryObj['content']) + '\n'
                ids.append(summary['id'])
                x += 1
                counter += 1
                groups = len(epoch) / resolution  
                frac, whole = math.modf(groups)
                max = len(epoch) - (1-frac)
                # print('max for batch is  ' +str(max))

                if x >= resolution:
                    if counter >= max:
                        continue
                    # eZprint('adding to batch for summary')

                    meta['last-doc'] = summary['timestamp']
                    format = '%Y-%m-%dT%H:%M:%S.%f%z'
                    date = datetime.strptime(meta['last-doc'], format)    
                    meta['overview'] = meta['overview'] + ' to ' + str(date) 

                    toSummarise = meta['overview'] + '\n' + toSummarise
                    batches.append({
                        'toSummarise': toSummarise,
                        'ids': ids,
                        'meta': meta,
                        'epoch' : summaryObj['epoch']
                    })
                    toSummarise = ''
                    ids = []
                    x = 0
                    meta = ' '

            await summarise_batches(batches,userID, convoID)
            
            for batch in batches:
                for id in batch['ids']:
                    summary = dict(candidate.blob)
                    for key, val in summary.items():
                        val['summarised'] = True
                    updated_summary = await prisma.summary.update(
                        where={ 'id': id },
                        data={
                            "blob": Json({key:val})
                        }
                    )
            return False                        
        else:
            # eZprint('epoch within resolution range so adding to latest : ' + str(key))
            counter = 0
            for summary in epoch:
                window.append(summary)
                counter += 1
                if counter >= resolution - 1:
                    windows[userID+convoID].append(window)
                    window = []
                    counter = 0
    if window != []:
        windows[userID+convoID].append(window)

    
    return True

async def summarise_by_window(userID, convoID):
    eZprint('starting epoch summary')

    if debug[userID+convoID]:
        candidates = summaries[userID+convoID]

    else:
        candidates = await prisma.summary.find_many(
            where={
            'UserID': userID,
            }
        ) 
    for candidate in candidates:
        summary = dict(candidate.blob)

        for key, val in summary.items():
            if 'summarised' in val:
                if val['summarised'] == True:
                    continue

async def get_summaries(userID, convoID):

    eZprint('getting summaries')
    summaries = await prisma.summary.find_many(
        where={
        'UserID': userID,
        }
    ) 
    windows[userID+convoID] = []
    epochs = {}
    for summary in summaries:
        summaryObj = dict(summary.blob)

        for key, val in summaryObj.items():
            if 'summarised' in val:
                if val['summarised'] == True:
                    continue
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
        for summary in summaries:
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

batch_summary_prompt = """
    Generate a concise summary of this conversation in JSON format, including a title, time range, in-depth paragraph, top 3 keywords, and relevant notes. The summary should be organized as follows:

    {
    "title": "[Short description]",
    "timestamp" : "[Time, Date, or Date Range]"
    "body": "[Longer description]",
    "keywords": ["Keyword1", "Keyword2", "Keyword3"],
    "notes": {
        "[Note Title1]": "[Note Body1]",
        "[Note Title2]": "[Note Body2]"
    },
    "insights": {
        "people": "[Insight Body1]",
        "places": "[Insight Body2]",
        "positive memories": "[Insight Body4]",
        "negative memories": "[Insight Body5]",
    }
    }

    Ensure that the summary captures essential decisions, discoveries, or resolutions, and keep the information dense and easy to parse.
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
    counter = 0
    for log in chatlog[convoID]:
        if 'summarised' not in log:
        # print(log)
        # if log['summarised'] == False:
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



async def summariseChatBlocks(input):
    eZprint('summarising chat blocks')
    convoID = input['convoID']
    messageIDs = input['messageIDs']
    summaryID = input['summaryID']
    userID = novaConvo[convoID]['userID']
    messagesToSummarise = []
    for messageID in messageIDs:
        for log in chatlog[convoID]:
            if messageID == log['ID']:
                messagesToSummarise.append(log)
    print(messagesToSummarise)
    print(len(messagesToSummarise))
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
    summary = await get_summary_with_prompt(prompt, str(messagesToSummarise))
    #wait for 2 seconds
    summarDict = {}
    try:
        summarDict = json.loads(summary)
    except:
        print('error parsing summary')
        summarDict.update({'title':'error parsing summary', 'body':summary})
    fields = {}
    for key, value in summarDict.items():
      fields[key] = value
    fields['state'] = ''
    payload = {'ID':summaryID, 'fields':fields}
    await  websocket.send(json.dumps({'event':'updateMessageFields', 'payload':payload}))
    summarDict.update({'sources':messageIDs})
    summary = await prisma.summary.create(
        data={
            "key": summaryID,
            "SessionID": convoID,
            "UserID": userID,
            "timestamp": datetime.now(),
            "blob": Json({summaryID:summarDict})
        }
    )
    # print(summary)
   #inject summary object into logs before messages it is summarising 
    injectPosition = chatlog[convoID].index( messagesToSummarise[0]) 
    chatlog[convoID].insert(injectPosition, {'ID':summaryID, 'name': 'summary', 'body':summarDict['title'], 'role':'system', 'timestamp':datetime.now(), 'summaryState':'SUMMARISED', 'muted':True, 'minimised':True, 'summaryID':summaryID})

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