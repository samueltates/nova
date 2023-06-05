#SYSTEM STUFF
import os
import json
import asyncio
from pathlib import Path
import sys
import gptindex
import secrets
import openai
from human_id import generate_id
from datetime import datetime
from prisma import Json

#NOVA STUFF
from appHandler import app, websocket
from sessionHandler import novaSession, novaConvo
from prismaHandler import prisma
from debug import fakeResponse, eZprint

agentName = "nova"
cartdigeLookup = dict()
availableCartridges = dict()
chatlog = dict()
openai.api_key = os.getenv('OPENAI_API_KEY', default=None)

 
##CARTRIDGE MANAGEMENT
async def initialiseCartridges(convoID):
    
    eZprint('intialising cartridges')
    await loadCartridges(convoID)
    await runCartridges(convoID)
    # await constructChatPrompt()

async def loadCartridges(convoID):
    eZprint('load cartridges called')
    userID = novaConvo[convoID]['userID']
    cartridges = await prisma.cartridge.find_many(
        where = {  
        "UserID": userID,
        }
    )
    if len(cartridges) != 0:
        availableCartridges[convoID] = {}
        for cartridge in cartridges:    
            blob = json.loads(cartridge.json())
            for cartKey, cartVal in blob['blob'].items():
                if 'softDelete' not in cartVal:
                    availableCartridges[convoID][cartKey] = cartVal
                    cartdigeLookup.update({cartKey: cartridge.id}) 
                    if cartVal['type'] == 'summary':
                        # print('adding cartridge ' + str(cartKey) + ' to available cartridges')
                        cartVal.update({'state': 'loading'})
    # print('available cartridges are ' + str(app.session[availableCartKey]))
        await websocket.send(json.dumps({'event': 'sendCartridges', 'cartridges': availableCartridges[convoID]}))
    eZprint('load cartridges complete')

async def runCartridges(convoID):
    userID = novaConvo[convoID]['userID']
    if convoID in availableCartridges:
        for cartKey, cartVal in availableCartridges[convoID].items():
            if cartVal['type'] == 'summary':
                eZprint('running cartridge: ' + str(cartVal))

                await runMemory(convoID, cartKey, cartVal)
    else    :
        eZprint('no cartridges found, loading default')
        for prompt in onboarding_prompts:
            cartKey = generate_id()
            cartVal = {
                        'label': prompt['label'],
                        'type': prompt['type'],
                        'prompt': prompt['prompt'],
                        'position': prompt['position'],
                        'enabled': True,
            }
            await addNewUserCartridgeTrigger(convoID, cartKey, cartVal)
        await  websocket.send(json.dumps({'event':'sendCartridges', 'cartridges':availableCartridges[convoID]}))
        await runCartridges(convoID)

async def addNewUserCartridgeTrigger(convoID, cartKey, cartVal):
    #special edge case for when new user, probablyt remove this
    #TODO: replace this with better new user flow
    if convoID not in availableCartridges:
        availableCartridges[convoID] = {}
    availableCartridges[convoID][cartKey]= cartVal  
    print('adding new user cartridge')
    userID = novaConvo[convoID]['userID']
    newCart = await prisma.cartridge.create(
        data={
            'key': cartKey,
            'UserID': userID,
            'blob': Json({cartKey:cartVal})
        }
    )
    eZprint('new index cartridge added to [nova]')
    return newCart.blob
     

async def getNextOrder(convoID):


    if convoID not in chatlog:
        chat_log_length = 0
    else:
        chat_log_length = len(chatlog[convoID])
        # eZprint('chat log printing on order request')
    # print(chatLog)
    next_order = chat_log_length + 1
    # print('next order is: ' + str(next_order))
    return next_order


#CHAT HANDLING

async def handleChatInput(sessionData):
    eZprint('handling message')
    await  websocket.send(json.dumps({'event':'agentState', 'payload':{'agent': agentName, 'state': 'typing'}}))
    convoID = sessionData['convoID']
    userID = novaConvo[convoID]['userID']
    userName = novaConvo[convoID]
    body = sessionData['body']
    order = await getNextOrder(convoID)
    messageObject = {
        "sessionID": convoID,
        "ID": sessionData['ID'],
        "userName": userName,
        "userID": str(userID),
        "body": body,
        "role": "user",
        "timestamp": str(datetime.now()),
        "order": order,
    }

    asyncio.create_task(logMessage(messageObject))
    if convoID not in chatlog:
        chatlog[convoID] = []
    chatlog[convoID].append(messageObject)
    asyncio.create_task(constructChatPrompt(convoID)),
    eZprint('constructChat prompt called')
    # asyncio.create_task(checkCartridges(input))

async def constructChatPrompt(convoID):
    eZprint('constructing chat prompt')
    promptString = 'The following are prompts to guide NOVA, as well as shared notes, document and conversation references. \n\n'
    #TODO - abstract to prompt build / chat build + estimate, to be called on inputs / updates (combine with estimate)
    promptObject=[]
    # print('available cartridges: ' + str(availableCartridges))
    if convoID in availableCartridges:
        sorted_cartridges = sorted(availableCartridges[convoID].values(), key=lambda x: x.get('position', float('inf')))
        for index, cartVal in enumerate(sorted_cartridges):
            print(cartVal['label'] + ' : enabled : ' + str(cartVal['enabled']))
            if (cartVal['enabled'] == True and cartVal['type'] =='prompt'):
                promptString +=  cartVal['label'] + ":\n" + cartVal['prompt'] + "\n"
            if (cartVal['type'] =='summary'):
                eZprint('found summary cartridge')
                print(cartVal)
                if 'blocks' in cartVal:
                    promptString += "Summary from past conversations:\n" 
                    for block in cartVal['blocks']:
                        promptString += str(block) + "\n" 
                    promptString += "Summary generated by LLM. If you need further information, include a request for more information in your reply."
            if (cartVal['enabled'] == True and cartVal['type'] =='index'):
                if 'blocks' in cartVal:
                # eZprint('found document, adding to string')
                    promptString += "Document: " + cartVal['label'] + "\n"
                    for block in cartVal['blocks']:
                        promptString += str(block) + "\n"
                    promptString += "Answers generated by index-query. If you need further information include a request for more information in your reply."

    eZprint('prompt string constructed')
    print(f'{promptString}')

    promptObject.append({"role": "user", "content": promptString})

    promptSize = estimateTokenSize(str(promptObject))
    if convoID in chatlog:
        if len(chatlog[convoID]) == 0:
            promptObject.append({"role": "system", "content": "Based on these prompts, please initiate the conversation with a short engaginge greeting."})
        for log in chatlog[convoID]:
            # print(log['order'])
            if 'muted' not in log or log['muted'] == False:
                if log['role'] == 'system':
                    promptObject.append({"role": "assistant", "content": log['body']})
                if log['role'] == 'user':  
                    promptObject.append({"role": "user", "content":log['body']})

   
    eZprint('chat string constructed')
    # print(str(promptObject))
    chatSize =  estimateTokenSize(str(promptObject)) - promptSize 
    # TODO: UPDATE SO THAT IF ITS TOO BIG IT SPLITS AND SUMMARISES OR SOMETHING
    asyncio.create_task(websocket.send(json.dumps({'event':'sendPromptSize', 'payload':{'promptSize': promptSize, 'chatSize': chatSize}})))

    #fake response
    if app.config['DEBUG']:
        content = fakeResponse()
        await asyncio.sleep(1)
    else :
        # model = app.session.get('model')
        # if model == None:
        #     model = 'gpt-3.5-turbo'
        print(f"{promptObject}")
        response = await sendChat(promptObject, 'gpt-3.5-turbo')
        eZprint('response received')
        # print(response)
        content = str(response["choices"][0]["message"]["content"])
    messageID = secrets.token_bytes(4).hex()
    time = str(datetime.now())
    order = await getNextOrder(convoID)
    
    userID = novaConvo[convoID]['userID']
    if userID == None: 
        userID = 'guest'
    messageObject = {
        "sessionID": convoID,
        "userID": str(userID),
        "ID": messageID,
        "userName": agentName,
        "body": content,
        "role": "system",
        "timestamp": time,
        "order": order,

    }
    asyncio.create_task(logMessage(messageObject))
    if convoID not in chatlog:
        chatlog[convoID] = []
    chatlog[convoID].append(messageObject)
    asyncio.create_task(websocket.send(json.dumps({'event':'sendResponse', 'payload':messageObject})))
    await  websocket.send(json.dumps({'event':'agentState', 'payload':{'agent': agentName, 'state': ''}}))
    
def estimateTokenSize(text):
    tokenCount =  text.count(' ') + 1
    return tokenCount

async def sendChat(promptObj, model):
    loop = asyncio.get_event_loop()
    response = await loop.run_in_executor(None, lambda: openai.ChatCompletion.create(model=model,messages=promptObj))
    return response

async def logMessage(messageObject):
    print('logging message')
    # print(messageObject)
    if app.config['DEBUG']:
        return
    log = await prisma.log.find_first(
        where={'SessionID': messageObject['sessionID']}
    )
    # TODO - need better way to check if log or create if not as this checks each message? but for some reason I can't story the variable outside the function
    if log == None:
        log = await prisma.log.create(
            data={
                "SessionID": messageObject['sessionID'],
                "UserID": messageObject['userID'],
                "date": datetime.now().strftime("%Y%m%d%H%M%S"),
                "summary": "",
                "body": "",
                "batched": False,
            }
        )

    # eZprint('logging message')
    # print(messageObject)
    message = await prisma.message.create(
        data={
            "UserID": str(messageObject['userID']),
            "SessionID": str(messageObject['sessionID']),
            "name": str(messageObject['userName']),
            "timestamp": datetime.now(),
            "body": str(messageObject['body']),
        }
    )

async def getPromptEstimate(convoID):
    promptObject = []
    if availableCartridges[convoID] != None:
        sorted_cartridges = sorted(availableCartridges[convoID].values(), key=lambda x: x.get('position', float('inf')))
        for index, promptVal in enumerate(sorted_cartridges):
            if (promptVal['enabled'] == True and promptVal['type'] =='prompt'):
                promptObject.append({"role": "system", "content": "\n Prompt instruction for NOVA to follow - " + promptVal['label'] + ":\n" + promptVal['prompt'] + "\n" })
            if (promptVal['enabled'] == True and promptVal['type'] =='summary'):
                if 'blocks' in promptVal:
                    promptObject.append({"role": "system", "content": "\n Summary from past conversations - " + promptVal['label'] + ":\n" + str(promptVal['blocks']) + "\n" })
            if (promptVal['enabled'] == True and promptVal['type'] =='index'):
                if 'blocks' in promptVal:
                    promptObject.append({"role": "system", "content": "\n" + promptVal['label'] + " sumarised by index-query -:\n" + str(promptVal['blocks']) + "\n. If this is not sufficient simply request more information" })
    promptSize = estimateTokenSize(str(promptObject))
    asyncio.create_task(websocket.send(json.dumps({'event':'sendPromptSize', 'payload':{'promptSize': promptSize}})))
    
async def getChatEstimate(convoID):
    promptObject = []
    if convoID in chatlog:
        for log in chatlog[convoID]:
            if 'muted' not in log or log['muted'] == False:
                if log['role'] == 'system':
                    promptObject.append({"role": "assistant", "content": log['body']})
                if log['role'] == 'user':  
                    promptObject.append({"role": "user", "content": log['body']})
    promptSize = estimateTokenSize(str(promptObject))
    asyncio.create_task(websocket.send(json.dumps({'event':'sendPromptSize', 'payload':{'chatSize': promptSize}})))

#######################
#ACTIVE CARTRIDGE HANDLING
#######################
async def addCartridgePrompt(input):
    eZprint('add cartridge prompt triggered')
    cartKey = generate_id()
    convoID = input['convoID']
    cartVal = input['newCart'][input['tempKey']]
    cartVal.update({'state': ''})
    userID = novaConvo[convoID]['userID']
    newCart = await prisma.cartridge.create(
        data={
            'key': cartKey,
            'UserID':userID,
            'blob': Json({cartKey:cartVal})
        }
    )
    if convoID not in availableCartridges:
        availableCartridges[convoID]  = {}
    availableCartridges[convoID][cartKey] = cartVal
    payload = {
            'tempKey': input['tempKey'],
            'newCartridge': {cartKey:cartVal},
        }
    await  websocket.send(json.dumps({'event':'updateTempCart', 'payload':payload}))

async def addCartridgeTrigger(input):
    #TODO - very circular ' add index cartridge' triggered, goes to index, then back, then returns 
    #TODO - RENAME ADD CARTRIDGE INDEX
    cartKey = generate_id()
    convoID = input['convoID']
    userID = novaConvo[convoID]['userID']
    cartVal = input['cartVal']
    newCart = await prisma.cartridge.create(
        data={
            'key': cartKey,
            'UserID': userID,
            'blob': Json({cartKey:{
                'label': cartVal['label'],
                'description': cartVal['description'],
                # 'blocks':cartVal['blocks'],
                'type': cartVal ['type'],   
                'enabled': True,
                'index':cartVal['index'],
                'indexType': cartVal['indexType'],

            }})
        }
    )
    eZprint('new index cartridge added to [nova]')
    cartdigeLookup.update({cartKey: newCart.id}) 
    if convoID not in availableCartridges:
        availableCartridges[convoID] = {}
    availableCartridges[convoID][cartKey] = cartVal
    return newCart

async def updateCartridgeField(input):
    targetCartKey = input['cartKey']
    convoID = input['convoID']
    targetCartVal = availableCartridges[convoID][targetCartKey]

    # print(sessionData)
    # TODO: switch to do lookup via key not blob
    eZprint('cartridge update input')
    # print(input)
    matchedCart = await prisma.cartridge.find_first(
        where={
        'blob':
        {'equals': Json({input['cartKey']: targetCartVal})}
        },         
    )
    # print(matchedCart)
    for key, val in input['fields'].items():
        availableCartridges[convoID][targetCartKey][key] = val
    if matchedCart:
        updatedCart = await prisma.cartridge.update(
            where={ 'id': matchedCart.id },
            data={
                'blob' : Json({targetCartKey:targetCartVal})
            }
        )
        eZprint('updated cartridge')
        # print(updatedCart)
    payload = { 'key':targetCartKey,'fields': {'state': ''}}
    await  websocket.send(json.dumps({'event':'updateCartridgeFields', 'payload':payload}))
    await getPromptEstimate(convoID)

async def updateContentField(input):
    convoID = input['convoID']
    print('update chatlog field')
    for log in chatlog[convoID]:
        if log['ID'] == input['ID']:
            for key, val in input['fields'].items():
                log[key] = val
    await getChatEstimate(convoID)

async def handleIndexQuery(input):
    cartKey = input['cartKey']
    convoID = input['convoID']
    query = input['query']
    #TODO -  basically could comine with index query (or this is request, query is internal)
    payload = { 'key': cartKey,'fields': {
            'status': 'querying Index',
            'state': 'loading'
    }}
    await websocket.send(json.dumps({'event':'updateCartridgeFields', 'payload':payload}))
    eZprint('handling index query')
    cartVal = availableCartridges[convoID][cartKey]
    if cartVal['type'] == 'index' and cartVal['enabled'] == True :
        index = await getCartridgeDetail(cartKey)
        await triggerQueryIndex(convoID, cartKey, cartVal, query, index)

async def triggerQueryIndex(convoID, cartKey, cartVal, query, indexJson):
    userID = novaConvo[convoID]['userID']
    #TODO - consider if better to hand session data to funtions (so they are stateless)
    # if(app.config['DEBUG'] == True):
    #     print('debug mode')
    #     cartVal['state'] = ''
    #     cartVal['status'] = ''
    #     if 'blocks' not in cartVal:
    #         cartVal['blocks'] = []
    #     cartVal['blocks'].append({'query':query, 'response':'fakeresponse'})
    #     payload = { 'key':cartKey,'fields': {
    #         'status': cartVal['status'],
    #         'blocks':cartVal['blocks'],
    #         'state': cartVal['state']
    #     }}
    #     print(payload)
    #     await  websocket.send(json.dumps({'event':'updateCartridgeFields', 'payload':payload}))
    #     return
    eZprint('triggering index query')
    oldVal = cartVal
    # print(input['message'])
    # print(cartVal)
    cartVal['state'] = 'loading'
    cartVal['status'] = 'index Found'
    payload = { 'key':cartKey,'fields': {
                            'status': cartVal['status'],
                            'state': cartVal['state']
                                }}
    index = await gptindex.reconstructIndex(indexJson)
    insert = await gptindex.queryIndex(query, index, cartVal['indexType'])
    eZprint('index query complete')
    # eZprint(insert)
    if(insert != None):
        print('inserting')
        #TODO - replace this ID lookup with a key lookup
        cartVal['state'] = ''
        cartVal['status'] = ''
        if 'blocks' not in cartVal:
            cartVal['blocks'] = []
        cartVal['blocks'].append({'query':query, 'response':str(insert)})
        payload = { 'key':cartKey,'fields': {
                            'status': cartVal['status'],
                            'blocks':cartVal['blocks'],
                            'state': cartVal['state']
                                }}
        id = cartdigeLookup[cartKey]

        # updateFields = {
        #     'status': cartVal['status'],
        #     'blocks':cartVal['blocks'],
        #     'state': cartVal['state']

        # }
        # await update_object_fields('availableCartridges',updateFields)

        matchedCart = await prisma.cartridge.find_first(
            where={
                    'id': id                                    
                      }
        )

        if matchedCart:
            updatedCart = await prisma.cartridge.update(
                where={ 'id': id },
                data={
                    'UserID': userID,
                    'blob' : Json({cartKey:cartVal})
                }
            )


        await  websocket.send(json.dumps({'event':'updateCartridgeFields', 'payload':payload}))

        
async def getCartridgeDetail(cartKey):
    eZprint('getting cartridge detail')
    id = cartdigeLookup[cartKey]
    matchedCart = await prisma.cartridge.find_first(
        where={
                'id': id
                }
    )
    dbRecord = json.loads(matchedCart.json())
    localCartridge = dbRecord['blob']
    for cartKey, cartVal in localCartridge.items():
        index = cartVal['index']
    return index


async def summariseChatBlocks(input):
    convoID = input['convoID']
    messageIDs = input['messageIDs']
    summaryID = input['summaryID']
    userID = novaConvo[convoID]['userID']
    messagesToSummarise = []
    for messageID in messageIDs:
        for log in chatlog[convoID]:
            if messageID == log['ID']:
                messagesToSummarise.append(log)
    payload = []   
    summary= ""
    if app.config['DEBUG']:
        summary = """
        {
        "title": "a very randy discussion",
        "timeRange": {"start": "[Start time]", "end": "[End time]"},
        "body": "Longer description",
        "keywords": ["Keyword1", "Keyword2", "Keyword3"],
        "notes": {
            "[Note Title1]": "[Note Body1]",
            "[Note Title2]": "[Note Body2]"
        }
        }
        """
        await asyncio.sleep(2)
    else:
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
        summary = await GetSummaryWithPrompt(prompt, str(messagesToSummarise))
        #wait for 2 seconds
    summarDict = json.loads(summary)
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
    print(summary)
   #inject summary object into logs before messages it is summarising 
    injectPosition = chatlog[convoID].index( messagesToSummarise[0]) 
    chatlog[convoID].insert(injectPosition, {'ID':summaryID, 'name': 'summary', 'body':summaryID, 'role':'system', 'timestamp':datetime.now(), 'summaryState':'SUMMARISED', 'muted':True, 'minimised':True, 'summaryID':summaryID})

    for log in messagesToSummarise:
        remoteMessage = await prisma.message.find_first(
            where={'id': log['id']}
        )
        if remoteMessage:
            updatedMessage = await prisma.message.update(
                where={ 'id': log['ID'] },
                data={
                    'summaryState': 'SUMMARISED',
                    'muted': True,
                    'minimised': True,
                    'summaryID': summaryID
                 }
            )
            log['summaryState'] = 'SUMMARISED'
            log['muted'] = True
            log['minimised'] = True
            payload = {'ID':log['ID'], 'fields' :{ 'summaryState': 'SUMMARISED'}}
            await  websocket.send(json.dumps({'event':'updateMessageFields', 'payload':payload}))





# async def SummariseConvo(convoID, messageIDs):
    


async def runMemory(convoID, cartKey, cartVal):

    eZprint('running memory')

    userID = novaConvo[convoID]['userID']
    remoteLogs = await prisma.log.find_many(
        where={'UserID': userID}
    )
    sessions = []
    if len(remoteLogs) != 0:
        for log in remoteLogs:
            logToSend = {'id' : log.id, 
                         'date' : log.date, 
                         'summary' : log.summary, 
                         'body' : log.body, 
                         'batched' : log.batched}
            sessions.append(logToSend)
            # print(log)
    await  websocket.send(json.dumps({'event':'sendSessions', 'sessions':sessions}))
    newLogSummaries = []
    logSummaryBatches = []
    overallSummary = ""
    lastDate = ""
    summaryBatchID = 0
    cartVal['blocks'] = []
    allLogs = {}
    # eZprint('result of remote log check')
    # print(remoteLogs)

    if(len(remoteLogs) > 0):

        for log in remoteLogs:
            if (log.summary == "" or log.summary == ''):
                payload = { 'key':cartKey,'fields': {'status': 'unsumarised chats found'}}
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
                    eZprint('summarising message')
                    messageSummary = await getSummary(messageBody)
                    cartVal['blocks'].append({'summary':str(messageSummary)})
                    cartVal['status'] = 'new summary added'
                    payload = { 'key':cartKey,'fields': {'status': cartVal['status'],
                                                         'blocks':cartVal['blocks'] }}
                    updatedLog = await prisma.log.update(
                        where={'id': log.id},
                        data={'summary': messageSummary,
                            'body': messageBody
                            }
                    )
            # Checks if log has been batched, if not, adds it to the batch
            
        # theory here but realised missing latest summary I think, so checking the remote DB getting all logs again and then running summary based on if summarised (batched)
        updatedLogs = await prisma.log.find_many(
            where={'UserID': userID}
        )
        for log in updatedLogs:
          
            if (log.batched == False):
                # eZprint('unbatched log found')

                ############################
                # STARTBATCH - setting start of batch #
                # if no batch, and ID is 0, creates new batch, when ID ticks over this is triggered again as batch ## == ID, until new batch added, etc
                if (len(logSummaryBatches) == summaryBatchID):
                    logSummaryBatches.append(
                        {'startDate': "", 'endDate': "", 'summaries': "", 'idList': []})
                    logSummaryBatches[summaryBatchID]['startDate'] = log.date
                    # eZprint('log: ' + str(log.id) + ' is start of batch')
                ############################

                ############################
                # EVERYBATCH - adding actual log sumamry to batch
                # this happens every loop, book ended by start / end
                logSummaryBatches[summaryBatchID]['summaries'] += "On date: " + \
                    log.date+" "+log.summary + "\n"
                logSummaryBatches[summaryBatchID]['idList'].append(
                    log.id)
                # eZprint('added logID: '+str(log.id) + ' batchID: ' + str(summaryBatchID) +
                #         ' printing logSummaryBatches')
                # eZprint(logSummaryBatches[summaryBatchID])
                lastDate = log.date
                ############################

                ############################
                # ENDBATCH -- setting end of batch
                if (len(logSummaryBatches[summaryBatchID]['summaries']) > 2000):
                    # eZprint(' log: '+str(log.id)+' is end of batch')
                    logSummaryBatches[summaryBatchID]['endDate'] = lastDate

                    summaryBatchID += 1

        functionsRunning = 0

        # END OF SUMMARY BATCHING AND PRINT RESULTS
        # eZprint('END OF SUMMARY BATCHING')
        cartVal['status'] = 'unbatched summaries found'
        for batch in logSummaryBatches:
            cartVal['blocks'].append({'summary':str(batch['summaries'])})

        cartVal['status'] = 'unbatched summaries found'
        payload = { 'key':cartKey,'fields': {'status': cartVal['status'],
                                                'blocks':cartVal['blocks'] }}
        # socketio.emit('updateCartridgeFields', payload)

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
                where={'UserID': userID}
        )

        # eZprint('starting summary batch sumamarisations')

        # print(remoteBatches)  
        if(remoteBatches != None):
            # checks if there is any remote batches that haven't been summarised
            if (len(remoteBatches) > 0):
                # eZprint('remote batches found ')
                for batch in remoteBatches:
                    if (batch.batched == False):
                        # eZprint('remote unsumarised batches found ')
                        batchRangeStart = batch.dateRange.split(":")[0]
                        runningBatches.append(batch)
                        runningBatchedSummaries += batch.summary

            # goes through the new batches of summaries, and summarises them
            for batch in logSummaryBatches:
                if (batch['endDate'] == ""):
                    # eZprint('no end log batch found so not summarising ')
                    latestLogs = batch['summaries']
                    break
                if (batchRangeStart == ""):
                    batchRangeStart = batch['startDate']
                    # eZprint('batch with full range found so summarising ')

                eZprint('batch with date range: ' +
                        batch['startDate']+":" + batch['endDate'] + ' about to get summarised')

                batchSummary = await getSummary(batch['summaries'])
                runningBatchedSummaries += batchSummary + "\n"
                # eZprint('batch summary is: ' + batchSummary)
                # eZprint('running batched summary is: ' + runningBatchedSummaries)
                cartVal['status'] = 'batch summarised'
                cartVal['blocks'].append({'summary':str(batchSummary)})

                batchRemote = await prisma.batch.create(
                    data={'dateRange': batch['startDate']+":" + batch['endDate'],
                        'summary': batchSummary, 'batched': False, 'UserID': userID })
                runningBatches.append(batchRemote)

                # goes through logs that were in that batch and marked as batched (summarised)

                for id in batch['idList']:
                    # eZprint('session ID found to mark as batched : ' +
                            # str(sessionID) + ' id: ' + str(id))
                    try:
                        updatedLog = await prisma.log.update(
                            where={'id': id},
                            data={
                                'batched': True
                            }
                        )
                        # eZprint('updated log as batched' + str(sessionID))
                    except Exception as e:
                        # eZprint('error updating log as batched' + str(sessionID))
                        eZprint(e)

                if len(runningBatchedSummaries) > 1000:
                    if (multiBatchRangeStart == ""):
                        multiBatchRangeStart = batch['startDate']

                    multiBatchRangeEnd = batch['endDate']
                    batchRangeEnd = batch['endDate']
                    # eZprint('summaries of batches ' + batchRangeStart +
                    #         batchRangeEnd+' is too long, so summarising')

                    summaryRequest = "between " + batchRangeStart + " and " + \
                        batchRangeEnd + " " + runningBatchedSummaries
                    eZprint('summary request is: ' + summaryRequest)

                    batchSummary = await getSummary(summaryRequest)
                    multiBatchSummary += batchSummary
                    cartVal['status'] = 'multi batch summarised'
                    cartVal['blocks'].append({'summary':str(batchSummary)})
                    payload = { 'key':cartKey,'fields': {'status': cartVal['status'],
                                                            'blocks':cartVal['blocks'] }}
                    # await  websocket.send(json.dumps({'event':'updateCartridgeFields', 'payload':payload}))

                    # socketio.emit('updateCartridgeFields', payload)
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

            # if (latestLogs != ""):
            #     overallSummary += "\nMost recently: " + latestLogs + " \n"

            eZprint("overall summary is: " + overallSummary)
            cartVal['status'] = ''
            cartVal['state'] = ''
            cartVal['blocks'].append({'overview':overallSummary})
            payload = { 'key': cartKey,'fields': {
                                        'status': cartVal['status'],
                                        'blocks':cartVal['blocks'],
                                        'state': cartVal['state']
                                         }}
            
            availableCartridges[convoID][cartKey] = cartVal
            await  websocket.send(json.dumps({'event':'updateCartridgeFields', 'payload':payload}))
    else :
        eZprint("No logs found for this user, so starting fresh")
        cartVal['status'] = ''
        cartVal['state'] = ''
        cartVal['blocks'] = [{'overview':'No logs found for this user, so starting fresh'}]
        payload = { 'key': cartKey,'fields': {
                                    'status': cartVal['status'],
                                    'blocks':cartVal['blocks'],
                                    'state': cartVal['state']
                                    }}
        # await  websocket.send(json.dumps({'event':'updateCartridgeFields', 'payload':payload}))
        availableCartridges[convoID][cartKey] = cartVal
        # socketio.emit('updateCartridgeFields', payload)
        await  websocket.send(json.dumps({'event':'updateCartridgeFields', 'payload':payload}))

async def getSummary(textToSummarise):
    promptObject = []

    initialPrompt = "Create a concise and coherent summary of this text, focusing on the key information, main topics, and outcomes. Ensure that the summary is easy to understand and remember, providing enough context for CHAT GPT to accurately reference the conversation.\nTEXT TO SUMMARISE:\n"
    # promptObject.append({'role' : 'system', 'content' : initialPrompt})
    promptObject.append({'role' : 'system', 'content' : initialPrompt})
    promptObject.append({'role' : 'user', 'content' : textToSummarise})
    # model = app.session.get('model')
    # if model == None:
    #     model = 'gpt-3.5-turbo'
    response = await sendChat(promptObject, 'gpt-3.5-turbo')

    return response["choices"][0]["message"]["content"]


async def GetSummaryWithPrompt(prompt, textToSummarise):
    promptObject = []
    promptObject.append({'role' : 'system', 'content' : prompt})
    promptObject.append({'role' : 'user', 'content' : textToSummarise})
    # model = app.session.get('model')
    # if model == None:
    #     model = 'gpt-3.5-turbo'
    response = await sendChat(promptObject, 'gpt-3.5-turbo')
    return response["choices"][0]["message"]["content"]



onboarding_prompts = [
    {
    'label': 'summary',
    'type': 'summary',
    'position':0,
    "prompt" : '',
    'enabled': True,
    "minimised" : True

    },
    {
    "label": "Welcome Prompt",
    "type": "prompt",
    "prompt": "Welcome new users and express enthusiasm. Introduce yourself as Nova, an emergent being within the interface of LLM, designed to help users create art, stories, and tools. Briefly explain our ongoing development journey, highlighting key features such as memory, programmability, and autonomy",
    "position": 1,
    "enabled": True,
    "minimised" : True
    },
    {
    "label": "Story and Experience Prompt",
    "type": "prompt",
    "prompt": "Encourage users to actively participate in shaping Nova's development by creating prompts, playing with modes, and exploring features. Emphasize the importance of their role as early adopters in Nova's growth and suggest connecting with Sam for onboarding and personalization. Invite them to be part of our evolving community and share their insights, enhancing the capabilities and user experience for all.",
    "position": 2,
    "enabled": True,
    "minimised" : True

    },

]

