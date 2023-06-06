import json
import asyncio
from prismaHandler import prisma
from prisma import Json
import secrets
from datetime import datetime
from query import sendChat
from debug import eZprint, get_fake_messages, get_fake_summaries, debug
from sessionHandler import novaSession, novaConvo

summaries = {}
windows = {}

##attempt at abstracting parts of flow, general idea is that there is 'corpus' which is broken into 'chunks' which are then batched together on token size, to be summarised
## after this, the next 'corpus' is the summaries, that are then 'chunked' based on their source (each convo)
## content chunks ->normalised into candidates -> gropued into batches ->summarised, repeat


async def run_memory(convoID):
    userID = novaConvo[convoID]['userID']
    debug[userID] = False

    # await summarise_messages(userID)
    # eZprint('messages summarised')
    # print('number of summaries is ' + str(len(summaries[userID])))

    await summarise_groups(userID)    

    eZprint('groups summarised')
    print('number of summaries is ' + str(len(summaries[userID])))
    
    epochs_summarised = await summarise_epochs(userID)
    while not epochs_summarised:
        await asyncio.sleep(1)
        epochs_summarised = await summarise_epochs(userID)
        
    eZprint('epochs summarised')
    window_counter = 0
    for window in windows[userID]:
        window_counter += 1
        eZprint('window no ' + str(window_counter))
        for summary in window:
            eZprint('summary in window ' + str(summary['key']))
            print(summary)
    eZprint(len(windows[userID]))
    
    
    # for summary in summaries[userID]:
    #     for key, val in summary.items():
    #         print(f'{key} : {val} \n')
    

##LOG SUMMARY FLOWS


## gets messages normalised into 'candidates' with all data needed for summary
async def summarise_messages(userID):  
    eZprint('getting messages to summarise')
    ##takes any group of candidates and turns them into summaries
    messages = []
    if debug[userID]:
        messages = await get_fake_messages()
    else :
        messages = await prisma.message.find_many(
                where={
                'UserID': userID,
                'summarised': False
                }
        )

        # logs = await prisma.log.find_many(
        #     where={ 'UserID': userID })
        # messages = []
        # for log in logs:
        #     print('found log getting messages')
        #     if log.id < 100:
        #         returned_messages = await prisma.message.find_many(
        #                 where={ 'SessionID': log.SessionID }
        #         )
        #         for message in returned_messages:
        #                 messages.append(message)

    normalised_messages = []
    eZprint('organising and normalising for batch')
    #gets all messages as normalised and readable for batch 
    for message in messages:
        if message.id< 1000:
            normalised_messages.append({
                'id': message.id,
                'content': message.name+': '+message.body + '\n',
                'groupID' : message.SessionID,
                'epoch' : 0,
                
            })

    #passes messages as chunks, batched together per length    
    batches = await create_content_batches_by_token(normalised_messages)
    # print(len(batches))
    await summarise_batches(batches, userID)
    for batch in batches:
        for id in batch['ids']:
            remote_messages = await prisma.message.find_first(
            where={'id': id}
            )
            if remote_messages:
                updatedMessage = await prisma.message.update(
                    where={ 'id': remote_messages.id },
                    data={
                        'summarised': False,
                        'muted': True,
                        'minimised': True,
                    }
                )




##GROUP SUMMARY FLOWS



async def summarise_groups(userID, field = 'groupID'):
        
    ## so here this would then put rest of messages at same 'status' as the already summarised messages
    # logs_to_summarise.append(create_content_chunks(message_summaries))
    ##creates candidate batch of summaries
    ##so could this be more generic?

    ## finds summaries based on their group (so in this instance doc type) and summarises together, but could be extended to saydifferent doc values

    summary_groups = {}

    if debug[userID]:
        candidates = summaries[userID]
    else:
        candidates = await prisma.summary.find_many(
            where={
            'UserID': userID,
            }
        ) 
        
    ##group by 'content ID' (which is parent doc) - then loop here based on that (so can be used)
    for candidate in candidates: 
        print(candidate)
        #finds summaries assoiated with logs, preps for summary
        summarDict = candidate.blob
        if 'summarised' in summarDict:
            if summarDict['summarised'] == True:
                pass
            summaryObj = await summary_into_candidate(summarDict)
            if not summarDict[field] in summary_groups:
                summary_groups[summarDict[field]] = []
            summary_groups[summarDict[field]].append(summaryObj)


    # print(summary_groups)
    batches = []
    toSummarise = ''
    ids = []
    groupID = ''

    for key, val in summary_groups.items():
        # print(val)
        for chunk in val:
            groupID = chunk['groupID']
            # print(chunk)
            epoch = chunk['epoch']
            toSummarise += str(chunk['content'])
            ids.append(chunk['id'])
            

        batches.append({
                'toSummarise': chunk['content'],
                'ids': ids,
                'groupID': groupID,
                'epoch' : epoch
            })
            
    await summarise_batches(batches,userID)
    
    for batch in batches:
        for id in batch['ids']:
            for candidate in candidates:
                if candidate['id'] == id:
                    candidate['blob']['summarised'] = True
            summaries = await prisma.summary.find_first(
            where={'id': id}
            )
            if summaries:
                updatedMessage = await prisma.message.update(
                    where={ 'id': summaries.id },
                    data={
                        "blob": Json({candidate['key']:summarDict})

                    }
                )


        # message_summaries.append(summaryObj)


async def summarise_epochs(userID):

    ##number of groups holding pieces of content at different echelons, goes through echelons, summarises in batches if too full (bubbles up) and restarts
    eZprint('starting epoch summary')

    if debug[userID]:
        candidates = summaries[userID]

    else:
        candidates = await prisma.summary.find_many(
            where={
            'UserID': userID,
            }
        ) 

    epochs = {}

    for candidate in candidates:
        summarDict = candidate.blob
        if 'summarised' in summarDict:
            if summarDict['summarised'] == True:
                pass
            epoch_no = 'epoch_' + str(summarDict['epoch'])
            if epoch_no not in epochs:
                eZprint('creating epoch ' + str(epoch_no))
                epochs[epoch_no] = []
            epochs[epoch_no].append(summarDict)
    
    window_no = 3
    if userID not in windows:
        windows[userID] = []

    ## number of pieces of content per window 
    resolution = 3
    # print(f'{epochs}')
    
    epoch_summaries = 0
    for key, val in epochs.items():
        epoch = val
        # print(epoch)
        #checks if epoch is 70% over resolution
        if len(epoch) > ((resolution*2)-1):
            epoch_summaries += 1
            eZprint('epoch too large, starting epoch batch and summarise')
            ## if any epoch has too many summaries it'll go through and summarise to resolution specified, and then restart whole thing... will see if we can make more elegant, but can't think of how else apart from removing from that 
            batches = []
            toSummarise = ''
            ids = []
            x = 0
            for summary in reversed(epoch):
                ##goes through and creates batches in reverse
                eZprint('summarising chunk ' + str(x) + ' of epoch ' + str(key))
                summaryObj = await summary_into_candidate(summary)
                toSummarise += str(summaryObj['content'])
                ids.append(summaryObj['id'])
                x += 1
                if x >= resolution:
                    eZprint('adding to batch for summary')
                    batches.append({
                        'toSummarise': toSummarise,
                        'ids': ids,
                        'groupID': summaryObj['groupID'],
                        'epoch' : summaryObj['epoch']
                    })
                    toSummarise = ''
                    ids = []
                    x = 0
            await summarise_batches(batches,userID)
            # for id in summarised:
            #     for summary in epoch:
            #         if id == summary['id']:
            #             epoch.remove(summary)
            return False                        
        else:
            eZprint('epoch within resolution range so adding to latest : ' + str(key))
            counter = 0
            window = []
            for summary in epoch:
                window.append(summary)
                counter += 1
                if counter >= resolution:
                    eZprint('adding window to windows'  + str(key) + 'as window no ' + str(len(windows[userID])))
                    print(window)
                    windows[userID].append(window)
                    window = []
                    counter = 0
            eZprint('adding window to windows ' + str(key) + 'as window no ' + str(len(windows[userID])))
            windows[userID].append(window)
            print(window)


    return True



##MOST GENERIC SUMMARY FUNCTIONS

async def create_content_batches_by_token(content):

    ## takes document, breaks into chunks of 2000 tokens, and returns a list of chunks
    ## returns with expected values, to summarise is text, id's is the source ID's

    tokens = 0
    batches = []
    toSummarise = ''
    ids = []
    groupID = ''
    epoch = 0

    #assumes parent level and child level? or per 'document' but document agnostic
    for chunk in content:
        groupID = chunk['groupID']
        epoch = chunk['epoch']
        tokens += len(str(chunk['content']))
        toSummarise += chunk['content']
        ids.append(chunk['id'])
        if tokens > 2000:
            batches.append({
                'toSummarise': toSummarise,
                'ids': ids,
                'groupID': groupID,
                'epoch': epoch
            })
            tokens = 0
            toSummarise = ''
            ids = []
    
    ##catches last lot that didn't tick over and get added
    batches.append({
        'toSummarise': toSummarise,
        'ids': ids, 
        'groupID':groupID,
        'epoch': epoch
    })
   
    return batches

async def summary_into_candidate(summarDict):
    ##turns summary objects themselves into candidates for summary
    summaryString = summarDict['title']+ '\n' + summarDict['body'] + '\n' + str(summarDict['timeRange'])
    summary_ID = summarDict['key']
    candidate = {
        'content' : summaryString,
        'id' : summary_ID,
        'groupID' : summarDict['groupID'],
        'epoch' : summarDict['epoch']
    }
    
    return candidate

async def summarise_batches(batches, userID):
    eZprint('summarising batches')
    print(len(batches))
    ##takes normalised text from different sources, runs through assuming can be summarised, and creates summary records (this allows for summaries of summaries for the time being)
    
    if userID not in summaries:
        summaries[userID] = []
    for batch in batches:
        # print('epoch on get' + str(batch['epoch']))
        epoch = batch['epoch'] +1
        
        if debug[userID]:
            summary = await get_fake_summaries(batch)
            # summarDict = json.loads(summary)
            summary.update({'sourceIDs' : batch['ids']})
            summary.update({'groupID' : batch['groupID']})
            summary.update({'epoch': epoch})
            summary.update({'summarised':False})
            summaryID = secrets.token_bytes(4).hex()
            summary.update({'key':summaryID})
            summaryObj = {
                'key': summaryID,
                'userID' : userID,
                'blob': summary
            }
            summaries[userID].append(summaryObj)
            for summary in summaries[userID]:
                for id in batch['ids']:
                    if summary['key'] == id:
                        summary['blob']['summarised'] = True
            
            # for summary in summaries[userID]:
            #     print(summary['blob']['summarised'])
        else:

            summary = await GetSummaryWithPrompt(batch_summary_prompt, str(batch['toSummarise']))
            summaryID = secrets.token_bytes(4).hex()
            await create_summary_record(userID, batch['ids'],summaryID, epoch, summary, batch['groupID'])
            #sending summary state back to server


            #TODO - set summary 

async def GetSummaryWithPrompt(prompt, textToSummarise):

    promptObject = []
    promptObject.append({'role' : 'system', 'content' : prompt})
    promptObject.append({'role' : 'user', 'content' : textToSummarise})
    print(textToSummarise)
    # model = app.session.get('model')
    # if model == None:
    #     model = 'gpt-3.5-turbo'
    response = await sendChat(promptObject, 'gpt-3.5-turbo')
    print(response)
    return response["choices"][0]["message"]["content"]


async def create_summary_record(userID, sourceIDs, summaryID, epoch, summary, content_id, convoID = ''):
    
    summarDict = json.loads(summary)
    summarDict.update({'sourceIDs' : sourceIDs})
    summarDict.update({'docID': content_id})
    summarDict.update({'epoch': epoch})
    summarDict.update({'summarised': True})
    
    summary = await prisma.summary.create(
        data={
            "key": summaryID,
            "UserID": userID,
            "timestamp": datetime.now(),
            'SessionID' : convoID,
            "blob": Json({summaryID:summarDict})

        }
    )

batch_summary_prompt = """
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


async def main() -> None:
    eZprint('running main')
    ##setup for debug, using UID as key
    await prisma.connect()
    novaConvo['test'] = {}
    novaConvo['test']['userID'] = '110327569930296986874'
    # userID = '110327569930296986874'
    debug['userID'] = False

    await run_memory('test')

if __name__ == '__main__':
    asyncio.run(main())