import os
import openai
import json
import asyncio
from pathlib import Path
import os
import sys
import gptindex
import secrets

from human_id import generate_id

path_root = Path(__file__).parents[1]
sys.path.append((str(path_root)))

from prisma import Prisma
from prisma import Json
# from prisma import Prisma
os.system('prisma generate')
from datetime import datetime
openai.api_key = os.getenv('OPENAIKEY', default=None)
from socketHandler import socketio

runningPrompts = dict()
availableCartridges = dict()
allLogs = dict()
responses = dict()
logs = dict()
userName = "guest"
agentName = "nova"
functionsRunning = 0
prisma = Prisma()
logCreated = 0
cartdigeLookup = dict()

def initialiseCartridges(data):
    eZprint('intialising cartridges')
    asyncio.run(loadCartridges(data))
    runCartridges(data)

def handleChatInput(input):
    eZprint('handling message')
    promptObject=[]
    eZprint(input)
    # asyncio.run(updateCartridges(input))
    asyncio.run(logMessage(
        input['sessionID'], input['userID'], input['userName'], input['message']))
    logs.setdefault(input['sessionID'], []).append(
        {"ID": input['ID'],
        "userName": input['userName'],
        "message": input['message'],
        "role": "user"
            })
    # constructChatPrompt(promptObject,input['sessionID'])
    checkCartridges(input)


async def loadCartridges(data):

    await prisma.disconnect()
    await prisma.connect()
    cartridges = await prisma.cartridge.find_many(
        where = {  
        "UserID": data['userID'],
        }
    )
    # eZprint(cartridges)
    if len(cartridges) != 0:
        for cartridge in cartridges:    
            blob = json.loads(cartridge.json())
            for cartKey, cartVal in blob['blob'].items():
                if 'softDelete' not in cartVal:
                    availableCartridges.setdefault(
                        data['sessionID'], dict()).update({cartKey: cartVal})
                    cartdigeLookup.update({cartKey: cartridge.id}) 
                    if cartVal['type'] == 'summary':
                        cartVal.update({'state': 'loading'})
        socketio.emit('sendCartridges', availableCartridges[data['sessionID']])
        # socketio.emit('sendCartridgeStatus', 'cartridgesLoaded')
    eZprint('load cartridges complete')
    # eZprint(availableCartridges)
    await prisma.disconnect()


def runCartridges(input):
    socketio.emit('sendCartridgeStatus', 'Running Cartridge Functions')
    
    if(input['sessionID'] in availableCartridges): 
        for cartridge in availableCartridges[input['sessionID']]:
            # print(availableCartridges[input['sessionID']][cartridge])
            if availableCartridges[input['sessionID']][cartridge]['type'] == 'summary':
                eZprint('running cartridge: ' + cartridge)
                cartVal = availableCartridges[input['sessionID']][cartridge]
                asyncio.run(runMemory(input, cartridge, cartVal))

    else    :
        eZprint('no cartridges found, loading default')
        cartKey = generate_id()
        cartVal = {
                        'label': 'overview',
                        'type': 'prompt',
                        'prompt': 'This is a new conversation started with Nova - a conversational AI assistant. These are the things Nova will try to communicate : The Nova interface consists of a chat window and a set of cartridges that define different functions, currently prompt injection, persistent conversation and document summary. The prompts are used to guide the conversation and can be used to add new topics to the conversation. Nova is a project designed to explore self determination for an AI assistant, and paired curation of AI abilities. Novas objectives are to help you be creative, organised. However you can change this by adding and muting prompts like this one. For example you can add a producer prompt that tells nova to ask about timelines and follow up, or a designer prompt that prompts nova to be more creative and blue sky. We are hoping to create the ability to have nova set, read and change their own prompts, as well as create follow up actions. Nova also has the ability to summarise their ongoing conversations and maintain summaries in the conversation, as well as upload large texts which can be indexed and queried. Most recently the system has been updated to distinguish between users so each set of cartridges and conversation summaries is unique to the user.',
                        'enabled': True,
                        }
        addNewUserCartridgeTrigger(input['userID'],cartKey, cartVal)
        availableCartridges.setdefault(
            input['sessionID'], dict()).update({cartKey: cartVal})
        
        cartKey = "summary"
        cartVal = {
                            'label': 'summary',
                            'type': 'summary',
                            'description':' a summary function that will summarise the conversation and store it in the database',
                            'enabled': True,
                            }
        addNewUserCartridgeTrigger(input['userID'],cartKey, cartVal)
        availableCartridges.setdefault(
            input['sessionID'], dict()).update({cartKey: cartVal})
        # asyncio.run(runMemory(input))
        runCartridges(input)


async def addCartridgePrompt(input):
    await prisma.disconnect()
    await prisma.connect()
    eZprint('add cartridge prompt triggered')
    eZprint(input)
    cartKey = generate_id()
    cartVal = input['newCart'][input['tempKey']]
    cartVal.update({'state': ''})
    newCart = await prisma.cartridge.create(
        data={
            'UserID':input['userID'],
            'blob': Json({cartKey:cartVal})
        }
    )
    availableCartridges[input['sessionID']].update({cartKey:cartVal})
    payload = {
            'tempKey': input['tempKey'],
            'newCartridge': {cartKey:cartVal},
        }
    socketio.emit('updateTempCart', payload)
    

async def updateCartridgeField(input):
    await prisma.disconnect()
    await prisma.connect()
    # eZprint('soft deleting cartridge')
    cartridges = availableCartridges[input['sessionID']]
    targetCartKey = input['cartKey']
    targetCartVal = cartridges[targetCartKey]
    matchedCart = await prisma.cartridge.find_first(
        where={
        'blob':
        {'equals': Json({input['cartKey']: targetCartVal})}
        }, 
    )
    for key, val in input['fields'].items():
        targetCartVal[key] = val

    input['fields']['state'] = ''

    print(targetCartVal)
    if matchedCart:
        updatedCart = await prisma.cartridge.update(
            where={ 'id': matchedCart.id },
            data={
                'UserID': input['userID'],
                'blob' : Json({targetCartKey:targetCartVal})
            }
        )
        eZprint(updatedCart)
    payload = { 'key':targetCartKey,'fields': input['fields']}
    socketio.emit('updateCartridgeFields', payload)
    await prisma.disconnect()

async def updateCartridges(input):
    await prisma.disconnect()
    await prisma.connect()
    eZprint('updating cartridges')
    # print(input['prompts'])
    # checks prompts, if values don't match in DB then updates DB
    for promptKey in input['prompts']:
        promptVal = input['prompts'][promptKey]
        matchFound = 0
        for oldPromptKey in availableCartridges[input['sessionID']]:
            oldPromptVal = availableCartridges[input['sessionID']][oldPromptKey]
            if promptKey == oldPromptKey:
                matchFound = 1
                if "softDelete" in input['prompts'][promptKey]:
                        eZprint('deleting prompt')
                        matchedCart = await prisma.cartridge.find_first(
                            where={
                            'blob':
                            {'equals': Json({oldPromptKey: {oldPromptVal}})}
                            }, 
                        )
                        updatedCart = await prisma.cartridge.delete(
                            where={ 'id': matchedCart.id }
                        )
                        eZprint(matchedCart)
                
                elif oldPromptVal != promptVal:
                    eZprint('found prompt, updating')
                    # print(promptVal)

                    matchedCart = await prisma.cartridge.find_first(
                        where={
                        'blob':
                        {'equals': Json({oldPromptKey: oldPromptVal})}
                            # 'blob': {
                            #     'path':'$.'+promptKey,
                            #     'array_contains': 
                            # }
                        }, 
                    )
                    # print(matchedCart)
                    if matchedCart is not None:
                        updatedCart = await prisma.cartridge.update(    
                            where={ 'id': matchedCart.id },     
                            data = {  
                                'UserID': input['userID'],
                                'blob':  Json({promptKey:promptVal})
                            }
                        )
                        # print(matchedCart)
        if(matchFound == 0 and promptVal['type'] == 'prompt'):
            eZprint('no match found, creating new prompt')
            newCart = await prisma.cartridge.create(
                data={
                    'UserID':input['userID'],
                    'blob': Json({generate_id():promptVal})
                }
            )
            availableCartridges[input['sessionID']].append(newCart['blob'])
            # print(newCart)
    availableCartridges[input['sessionID']] = input['prompts']

    await prisma.disconnect()

def addCartridgeTrigger(userID, sessionID, cartVal):
    eZprint('adding cartridge triggered')
    newCart = asyncio.run(addCartridgeAsync(userID,sessionID, cartVal))
    return newCart
    
async def addCartridgeAsync(userID, sessionID, cartVal):
    eZprint('adding cartridge async')
    # eZprint(cartVal)
    await prisma.disconnect()
    await prisma.connect()
    cartKey = generate_id()
    # indexJsonsed = Json(cartVal['index'])
    newCart = await prisma.cartridge.create(
        data={
            'UserID': userID,
            'blob': Json({cartKey:{
                'label': cartVal['label'],
                'description': cartVal['description'],
                'blocks':cartVal['blocks'],
                'type': cartVal ['type'],   
                'enabled': True,
                'index':cartVal['index']
            }})
        }
    )
    eZprint('new index cartridge added to [nova]')
    cartdigeLookup.update({cartKey: newCart.id}) 
    availableCartridges[sessionID].append(newCart)
    await prisma.disconnect()
    return newCart.blob


def addNewUserCartridgeTrigger(userID,cartKey, cartVal):
    eZprint('adding cartridge triggered')
    newCart = asyncio.run(addNewUserCartridgeAsync(userID,cartKey, cartVal))
    return newCart
    
async def  addNewUserCartridgeAsync(userID, cartKey, cartVal):
    eZprint('adding cartridge async')
    eZprint(cartVal)
    await prisma.disconnect()
    await prisma.connect()
    # indexJsonsed = Json(cartVal['index'])
    newCart = await prisma.cartridge.create(
        data={
            'UserID': userID,
            'blob': Json({cartKey:cartVal})
        }
    )
    eZprint('new index cartridge added to [nova]')
    await prisma.disconnect()
    return newCart.blob

def checkCartridges(input):
    for cartKey in availableCartridges[input['sessionID']]:
        cartVal = availableCartridges[input['sessionID']][cartKey]
        if cartVal['enabled'] == False :
            return
        if cartVal['type'] == 'index':
            eZprint('index query detected')
            # print(cartVal)
            # print(message)
            index = asyncio.run(getCartridgeDetail(cartKey))
            triggerQueryIndex(cartKey, cartVal, input, index)
        # if cartVal['type'] == 'prompt':
        #     eZprint('found prompt, adding to string')
        #     promptObject.append({"role": "system", "content": "\n Prompt - " + cartVal['label'] + ":\n" + cartVal['prompt'] + "\n" })
                
    # for promptKey in input['prompts']:
    #     promptVal = input['prompts'][promptKey]
    #     # for promptKey, promptVal in prompt.items():
    #     if promptVal['type'] == 'index' and promptVal['enabled'] == True:
    #         eZprint('index query detected')
    #         # print(promptVal)
    #         for runningPromptKey in availableCartridges[input['sessionID']]:
    #             runningPromptVal = availableCartridges[input['sessionID']][runningPromptKey]
    #             if runningPromptKey == promptKey:
    #                 matchedCart = promptVal
    #                 eZprint ('matched cart found')
    #             index = asyncio.run(getCartridgeDetail(promptKey))
    #             triggerQueryIndex(input, index)


def triggerQueryIndex(cartKey, cartVal, input, index):
    eZprint('triggering index query')
    print(input['message'])
    cartVal['state'] = 'loading'
    cartVal['status'] = 'indexFound'
    payload = { 'key':cartKey,'fields': {
                            'status': cartVal['status'],
                            'blocks':cartVal['blocks'],
                            'state': cartVal['state']
                                }}
    socketio.emit('updateCartridgeFields', payload)
    insert = gptindex.queryIndex(input['message'], index)
    eZprint('index query complete')
    # eZprint(insert)
    if(insert != None):
        cartVal['state'] = 'loading'
        cartVal['status'] = ''
        cartVal['blocks'].append(str(insert))
        payload = { 'key':cartKey,'fields': {
                            'status': cartVal['status'],
                            'blocks':cartVal['blocks'],
                            'state': cartVal['state']
                                }}
        socketio.emit('updateCartridgeFields', payload)

        asyncio.run(logMessage(input['sessionID'], 'index-query', 'index-query' , str(insert)))
        logs.setdefault(input['sessionID'], []).append(
            {"userName": 'index-query',
            "message": str(insert),
            "role": "system"
            })
        
        ID = secrets.token_bytes(4).hex()

        log = {
            "ID":ID,
            "userName": 'index-query',
            "message": str(insert),
            "role": "system"
            }

        socketio.emit('sendResponse', log)
        
async def getCartridgeDetail(cartKey):
    eZprint('getting cartridge detail')

    id = cartdigeLookup[cartKey]
    await prisma.disconnect()
    await prisma.connect()
    matchedCart = await prisma.cartridge.find_first(
        where={
                'id': id
                
                }
    )
    dbRecord = json.loads(matchedCart.json())
    # print (dbRecord)
    localCartridge = dbRecord['blob']
    for cartKey, cartVal in localCartridge.items():
        index = cartVal['index']
    await prisma.disconnect()
    return index

# def logQueryReply(input, insert):
#     asyncio.run(logMessage(input['sessionID'], 'index-query', insert))
#     logs.setdefault(input['sessionID'], []).append(
#         {"userName": 'index-query',
#         "message": insert,
#         "role": "system"
#         })



def sendChat(promptObj):
    response = openai.ChatCompletion.create(
        model="gpt-4",
        messages=promptObj,
    )
    return response


def sendPrompt(promptString):
    response = openai.Completion.create(
        model="text-davinci-003",
        prompt=promptString,
        temperature=0.9,
        max_tokens=150,
        top_p=1,
        frequency_penalty=0,
        presence_penalty=0.6,
        stop=[" Sam:", " Nova:"]
    )

    eZprint('promptSent')
    # eZprint(response)
    return response


def constructChatPrompt(promptObject, sessionID):

    eZprint("sending prompt")

    for chat in logs[sessionID]:
        eZprint('found chat, adding to string')
        eZprint(chat)
        if chat['role'] == 'system':
            promptObject.append({"role": "assistant", "content": chat['message']})
        if chat['role'] == 'user':  
            promptObject.append({"role": "user", "content": chat['message']})
            
    eZprint('prompt constructed')

    #fake response

    try :
        response = sendChat(promptObject)
        print(response)
        content = str(response["choices"][0]["message"]["content"])
    except:
        content = 'API error'
    asyncio.run(logMessage(sessionID, agentName, agentName,
                content))
    ID = secrets.token_bytes(4).hex()

    log = {
        "ID":ID,
        "userName": agentName,
        "message": content,
        "role": "system"
         }

    socketio.emit('sendResponse', log)
    logs.setdefault(sessionID, []).append(log)
    


async def logMessage(sessionID, userID, userName, message):
    functionsRunning = 1
    # return
    await prisma.disconnect()
    await prisma.connect()
    log = await prisma.log.find_first(
        where={'SessionID': sessionID}
    )
    # need better way to check if log or create if not as this checks each message? but for some reason I can't story the variable outside the function
    if log == None:
        log = await prisma.log.create(
            data={
                "SessionID": sessionID,
                "UserID": userID,
                "date": datetime.now().strftime("%Y%m%d%H%M%S"),
                "summary": "",
                "body": "",
                "batched": False,
            }
        )

    eZprint('logging message')
    message = await prisma.message.create(
        data={
            "SessionID": sessionID,
            "name": userName,
            "UserID": userID,
            "timestamp": datetime.now(),
            "body": message,
        }
    )
    await prisma.disconnect()

    functionsRunning = 0


def eZprint(string):
    # return
    # socketio.emit('sendDebug', str(string))

    print('\n _____________ \n')
    print(string)
    print('\n _____________ \n')


async def runMemory(input, cartKey, cartVal):
    await prisma.disconnect()
    await prisma.connect()
    eZprint('running memory')
    eZprint(cartKey)
    remoteLogs = await prisma.log.find_many(
        where={'UserID': input['userID']}
    )

    newLogSummaries = []
    logSummaryBatches = []
    overallSummary = ""
    lastDate = ""
    summaryBatchID = 0
    cartVal['blocks'] = []
    eZprint('result of remote log check')
    # print(remoteLogs)

    if(len(remoteLogs) > 0):
        eZprint('logs found')

        allLogs.setdefault(
            input['sessionID'], remoteLogs)
        for log in allLogs[input['sessionID']]:
            # Checks if log has summary, if not, gets summary from OPENAI
            if (log.summary == "" or log.summary == ''):
                eZprint('no summary, getting summary from OPENAI')
                payload = { 'key':cartKey,'fields': {'status': 'unsumarised chats found'}}
                socketio.emit('updateCartridgeFields', payload)
 
                sessionID = log.SessionID
                messageBody = ""
                # Gets messages with corresponding ID
                messages = await prisma.message.find_many(
                    where={'SessionID': sessionID})
                
                # makes sure messages aren't zero (this should be blocked as log isn't created until first message now)
                if (len(messages) != 0):
                    messageBody += "Chat on " + str(messages[0].timestamp) + "\n"

                    for message in messages:
                        messageBody += "timestamp:\n"+str(message.timestamp) + \
                            message.name + ":" + message.body + "\n"

                    eZprint('printing messageBody')
                    # eZprint(messageBody)

                    messageSummary = getSummary(messageBody)
                    eZprint('summary is: '+messageSummary)
                    cartVal['blocks'].append(str(messageSummary))
                    cartVal['status'] = 'new summary added'
                    payload = { 'key':cartKey,'fields': {'status': cartVal['status'],
                                                         'blocks':cartVal['blocks'] }}
                    socketio.emit('updateCartridgeFields', payload)
 
                    print(cartVal['blocks'])
                    updatedLog = await prisma.log.update(
                        where={'id': log.id},
                        data={'summary': messageSummary,
                            'body': messageBody
                            }
                    )
            # Checks if log has been batched, if not, adds it to the batch
            
        eZprint('starting log batching')

        # theory here but realised missing latest summary I think, so checking the remote DB getting all logs again and then running summary based on if summarised (batched)
        updatedLogs = await prisma.log.find_many(
            where={'UserID': input['userID']}
        )
        for log in updatedLogs:
          
            if (log.batched == False):
                eZprint('unbatched log found')

                ############################
                # STARTBATCH - setting start of batch #
                # if no batch, and ID is 0, creates new batch, when ID ticks over this is triggered again as batch ## == ID, until new batch added, etc
                if (len(logSummaryBatches) == summaryBatchID):
                    logSummaryBatches.append(
                        {'startDate': "", 'endDate': "", 'summaries': "", 'idList': []})
                    logSummaryBatches[summaryBatchID]['startDate'] = log.date
                    eZprint('log: ' + str(log.id) + ' is start of batch')
                ############################

                ############################
                # EVERYBATCH - adding actual log sumamry to batch
                # this happens every loop, book ended by start / end
                logSummaryBatches[summaryBatchID]['summaries'] += "On date: " + \
                    log.date+" "+log.summary + "\n"
                logSummaryBatches[summaryBatchID]['idList'].append(
                    log.id)
                eZprint('added logID: '+str(log.id) + ' batchID: ' + str(summaryBatchID) +
                        ' printing logSummaryBatches')
                # eZprint(logSummaryBatches[summaryBatchID])
                lastDate = log.date
                ############################

                ############################
                # ENDBATCH -- setting end of batch
                if (len(logSummaryBatches[summaryBatchID]['summaries']) > 2000):
                    eZprint(' log: '+str(log.id)+' is end of batch')
                    logSummaryBatches[summaryBatchID]['endDate'] = lastDate

                    summaryBatchID += 1

        functionsRunning = 0

        # END OF SUMMARY BATCHING AND PRINT RESULTS
        eZprint('END OF SUMMARY BATCHING')
        cartVal['status'] = 'unbatched summaries found'
        for batch in logSummaryBatches:
            cartVal['blocks'].append(str(batch['summaries']))

        cartVal['status'] = 'unbatched summaries found'
        payload = { 'key':cartKey,'fields': {'status': cartVal['status'],
                                                'blocks':cartVal['blocks'] }}
        socketio.emit('updateCartridgeFields', payload)

        # return
        # summarises each batch if that isn't summarised, and adds to summary
        # how do we know if the batch has been created and summarised
        # so a batch is only being created if there's lots of logs, and then it's being summarised
        # the 'stored' batch summaries shouldn't overlap with the new batch summaries
        # so will need to add the new batch summaries to remote, access those, then add the unbatched logs -
        # will also need to check remote and any batches that get too big .. wll need to be batched... I'm confused

        runningBatchedSummaries = ""
        runningBatches = []
        latestLogs = ""
        batchRangeStart = ""
        batchRangeEnd = ""

        multiBatchRangeStart = ""
        multiBatchRangeEnd = ""

        multiBatchSummary = ""

        remoteBatches = await prisma.batch.find_many(
                where={'UserID': input['userID']}
        )

        eZprint('starting summary batch sumamarisations')

        # print(remoteBatches)
        if(remoteBatches != None):
            # checks if there is any remote batches that haven't been summarised
            if (len(remoteBatches) > 0):
                eZprint('remote batches found ')
                for batch in remoteBatches:
                    if (batch.batched == False):
                        eZprint('remote unsumarised batches found ')
                        batchRangeStart = batch.dateRange.split(":")[0]
                        runningBatches.append(batch)
                        runningBatchedSummaries += batch.summary

            # goes through the new batches of summaries, and summarises them
            for batch in logSummaryBatches:
                if (batch['endDate'] == ""):
                    eZprint('no end log batch found so not summarising ')
                    latestLogs = batch['summaries']
                    break
                if (batchRangeStart == ""):
                    batchRangeStart = batch['startDate']
                    eZprint('batch with full range found so summarising ')

                eZprint('batch with date range: ' +
                        batch['startDate']+":" + batch['endDate'] + ' about to get summarised')

                batchSummary = getSummary(batch['summaries'])
                runningBatchedSummaries += batchSummary + "\n"
                # eZprint('batch summary is: ' + batchSummary)
                # eZprint('running batched summary is: ' + runningBatchedSummaries)
                cartVal['status'] = 'batch summarised'
                cartVal['blocks'].append(str(batchSummary))

                batchRemote = await prisma.batch.create(
                    data={'dateRange': batch['startDate']+":" + batch['endDate'],
                        'summary': batchSummary, 'batched': False, 'UserID': input['userID'] })
                runningBatches.append(batchRemote)

                # goes through logs that were in that batch and marked as batched (summarised)

                for id in batch['idList']:
                    eZprint('session ID found to mark as batched : ' +
                            str(sessionID) + ' id: ' + str(id))
                    try:
                        updatedLog = await prisma.log.update(
                            where={'id': id},
                            data={
                                'batched': True
                            }
                        )
                        eZprint('updated log as batched' + str(sessionID))
                    except Exception as e:
                        eZprint('error updating log as batched' + str(sessionID))
                        eZprint(e)

                if len(runningBatchedSummaries) > 1000:
                    if (multiBatchRangeStart == ""):
                        multiBatchRangeStart = batch['startDate']

                    multiBatchRangeEnd = batch['endDate']
                    batchRangeEnd = batch['endDate']
                    eZprint('summaries of batches ' + batchRangeStart +
                            batchRangeEnd+' is too long, so summarising')

                    summaryRequest = "between " + batchRangeStart + " and " + \
                        batchRangeEnd + " " + runningBatchedSummaries
                    eZprint('summary request is: ' + summaryRequest)

                    batchSummary = getSummary(summaryRequest)
                    multiBatchSummary += batchSummary
                    cartVal['status'] = 'multi batch summarised'
                    cartVal['blocks'].append(str(batchSummary))
                    payload = { 'key':cartKey,'fields': {'status': cartVal['status'],
                                                            'blocks':cartVal['blocks'] }}
                    socketio.emit('updateCartridgeFields', payload)
                    batchBatch = await prisma.batch.create(
                        data={'dateRange': batch['startDate']+":" + batch['endDate'],
                            'summary': batchSummary, 'batched': False, })

                    for batch in runningBatches:
                        updateBatch = await prisma.batch.update(
                            where={'id': batch.id},
                            data={'batched': True, })

                    runningBatchedSummaries = ""
                    batchRangeStart = ""
                    runningBatches = []

            overallSummary = "Summary of chat log: \n"

            if (multiBatchSummary != ""):
                overallSummary += "\nOldest: Between " + multiBatchRangeStart + \
                    " & " + multiBatchRangeEnd + " - " + multiBatchSummary + " \n"

            if (runningBatchedSummaries != ""):
                overallSummary += "\nRecent: Between " + batchRangeStart + \
                    " & " + batchRangeEnd + runningBatchedSummaries + " \n"

            if (latestLogs != ""):
                overallSummary += "\nMost recently: " + latestLogs + " \n"

            eZprint("overall summary is: " + overallSummary)
            cartVal['status'] = ''
            cartVal['state'] = ''
            cartVal['blocks'] = [overallSummary]
            payload = { 'key':cartKey,'fields': {
                                        'status': cartVal['status'],
                                        'blocks':cartVal['blocks'],
                                        'state': cartVal['state']
                                         }}
            socketio.emit('updateCartridgeFields', payload)
            await prisma.disconnect()
    else :
        eZprint("No logs found for this user, so starting fresh")
        summaryCartridge = {'label': 'summary-output',
                    'type': 'summary-output',
                    'description': 'an output that has then been stored as a cartridge',
                    'blocks': ["No prior conversations to summarise. This cartridge will show the summaries of your past conversations, and add to context if unmuted."],
                    'state': '',
                    'enabled': True}

        updatePayload = {
            'key': cartKey,
            'val' : summaryCartridge
            }
        
        socketio.emit('updateCartridge', updatePayload)
        availableCartridges[input['sessionID']][cartKey].update(summaryCartridge)

        await prisma.disconnect()


def welcomeGuest(sessionID, userID, userName):

    promptString = ""
    eZprint("sending prompt")
    # eZprint(runningPrompts)
    for promptObj in runningPrompts[sessionID]:
        eZprint('found prompt, adding to string')
        # print(promptObj)
        promptString += " "+promptObj['cartridge']['prompt']+"\n"

    response = sendPrompt(promptString)

    # eZprint(response)
    asyncio.run(logMessage(sessionID, userID, userName,
                response["choices"][0]["text"]))

    logs.setdefault(sessionID, []).append(
        {"userName": agentName,
         "message": response["choices"][0]["text"]})


def getSummary(textToSummarise):
    promptObject = []

    initialPrompt = "Create a concise and coherent summary of this text, focusing on the key information, main topics, and outcomes. Ensure that the summary is easy to understand and remember, providing enough context for CHAT GPT to accurately reference the conversation.\nTEXT TO SUMMARISE:\n"
    promptObject.append({'role' : 'system', 'content' : initialPrompt})
    promptObject.append({'role' : 'system', 'content' : initialPrompt})
    promptObject.append({'role' : 'user', 'content' : textToSummarise})
    response = sendChat(promptObject)

    return response["choices"][0]["message"]["content"]
