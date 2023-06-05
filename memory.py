import json
import asyncio
from prismaHandler import prisma
from prisma import Json
import secrets
from datetime import datetime
from query import sendChat
from debug import eZprint, get_fake_messages, get_fake_summaries, debug

summaries = {}

##attempt at abstracting parts of flow, general idea is that there is 'corpus' which is broken into 'chunks' which are then batched together on token size, to be summarised
## after this, the next 'corpus' is the summaries, that are then 'chunked' based on their source (each convo)
## content chunks ->normalised into candidates -> gropued into batches ->summarised, repeat



async def runMemory(userID):

    await summarise_messages(userID)
    eZprint('messages summarised')
    print('number of summaries is ' + str(len(summaries[userID])))

    # for summary in summaries[userID]:
    #     for key, val in summary.items():
    #         print(f'{key} : {val} \n')
    
    # return
    await summarise_groups(userID)    

    eZprint('groups summarised')
    print('number of summaries is ' + str(len(summaries[userID])))

    
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
    
    normalised_messages = []
    eZprint('organising and normalising for batch')
    #gets all messages as normalised and readable for batch 
    for message in messages:
        normalised_messages.append({
            'id': message['messageID'],
            'content': message['name']+': '+message['body'] + '\n',
            'groupID' : message['convoID'],
        })

    #passes messages as chunks, batched together per length    
    batches = await create_content_batches(normalised_messages)
    # print(len(batches))
    await summarise_batches(batches, userID)

##MOST GENERIC SUMMARY FUNCTIONS

async def create_content_batches(content,):

    ## takes document, breaks into chunks of 2000 tokens, and returns a list of chunks
    ## returns with expected values, to summarise is text, id's is the source ID's

    tokens = 0
    batches = []
    toSummarise = ''
    ids = []
    groupID = ''

    #assumes parent level and child level? or per 'document' but document agnostic
    for chunk in content:
        groupID = chunk['groupID']
        tokens += len(str(chunk['content']))
        toSummarise += chunk['content']
        ids.append(chunk['id'])
        if tokens > 2000:
            batches.append({
                'toSummarise': toSummarise,
                'ids': ids,
                'groupID': groupID
            })
            tokens = 0
            toSummarise = ''
            ids = []
    
    ##catches last lot that didn't tick over and get added
    batches.append({
        'toSummarise': toSummarise,
        'ids': ids, 
        'groupID':groupID
    })
   
    return batches


async def summarise_batches(batches, userID):
    eZprint('summarising bactes')
    ##takes normalised text from different sources, runs through assuming can be summarised, and creates summary records (this allows for summaries of summaries for the time being)

    summaries[userID] = []
    for batch in batches:
        if debug[userID]:
            summary = await get_fake_summaries(batch)
            # summarDict = json.loads(summary)
            summary.update({'sourceIDs' : batch['ids']})
            summary.update({'groupID' : batch['groupID']})
            summaryID = secrets.token_bytes(4).hex()
            summary.update({'key':summaryID})
            summaryObj = {
                'key': summaryID,
                'userID' : userID,
                'blob': summary
            }
            summaries[userID].append(summaryObj)
        else:

            summary = GetSummaryWithPrompt(batch_summary_prompt, str(batch['toSummarise']))
            summarDict = json.loads(summary)
            create_summary_record(batch['userID'], batch['ids'], summarDict, batch['groupID'])


async def GetSummaryWithPrompt(prompt, textToSummarise):

    promptObject = []
    promptObject.append({'role' : 'system', 'content' : prompt})
    promptObject.append({'role' : 'user', 'content' : textToSummarise})
    # model = app.session.get('model')
    # if model == None:
    #     model = 'gpt-3.5-turbo'
    response = await sendChat(promptObject, 'gpt-3.5-turbo')
    return response["choices"][0]["message"]["content"]


async def create_summary_record(userID, sourceIDs, summary, content_id):
    
    summaryID = secrets.token_bytes(4).hex()
    summarDict = json.loads(summary)
    summarDict.update({'sourceIDs' : sourceIDs})
    summarDict.update({'docID': content_id})
    
    summary = await prisma.summary.create(
        data={
            "key": summaryID,
            "UserID": userID,
            "timestamp": datetime.now(),
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
            'summarised': False
            }
        ) 
        
    ##group by 'content ID' (which is parent doc) - then loop here based on that (so can be used)
    for candidate in candidates: 
        #finds summaries assoiated with logs, preps for summary
        
        summarDict = candidate['blob']
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
            toSummarise += str(chunk['content'])
            ids.append(chunk['id'])

        batches.append({
                'toSummarise': chunk['content'],
                'ids': ids,
                'groupID': groupID
            })
            
        await summarise_batches(batches,userID)
        # message_summaries.append(summaryObj)


async def summary_into_candidate(summarDict):
    ##turns summary objects themselves into candidates for summary
    summaryString = summarDict['title']+ '\n' + summarDict['body'] + '\n' + str(summarDict['timeRange'])
    summary_ID = summarDict['key']
    candidate = {
        'content' : summaryString,
        'id' : summary_ID,
        'groupID' : summarDict['groupID']
    }
    
    return candidate


async def compress_summaries(userID):
    #goes through summaries and compresses based on user prefs
    ##option one - even up - takes 'blocks' at rate 
    
    print('something')


async def main() -> None:
    eZprint('running main')
    ##setup for debug, using UID as key
    userID = 'sam'
    debug[userID] = True

    await runMemory(userID)

if __name__ == '__main__':
    asyncio.run(main())