import os
import openai
import json
import asyncio
from pathlib import Path
import os
import sys
import gptindex
import secrets
import random
import uuid


from human_id import generate_id
from prisma import Json

path_root = Path(__file__).parents[1]
sys.path.append((str(path_root)))

# from prisma import Prisma
os.system('prisma generate')
from datetime import datetime
openai.api_key = os.getenv('OPENAI_API_KEY', default=None)
# from socketHandler import socketio
from appHandler import app, websocket

from prisma import Prisma
prisma = Prisma()
import logging
# logging.basicConfig()

runningPrompts = dict()
availableCartridges = dict()
allLogs = dict()
responses = dict()
logs = dict()
userName = "guest"
agentName = "nova"
functionsRunning = 0
logCreated = 0
cartdigeLookup = dict()

async def prismaConnect():
    await prisma.connect()
    # logging.getLogger('prisma').setLevel(logging.DEBUG)
async def prismaDisconnect():
    await prisma.disconnect()

async def initialiseCartridges(data):
    eZprint('intialising cartridges')
    await loadCartridges(data)
    await runCartridges(data)

async def loadCartridges(data):
    eZprint('load cartridges called')
    # eZprint('prisma connected')
    cartridges = await prisma.cartridge.find_many(
        where = {  
        "UserID": data['userID'],
        }
    )
    eZprint('cartridge length is ' + str(len(cartridges)))
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
        await  websocket.send(json.dumps({'event':'sendCartridges', 'cartridges':availableCartridges[data['sessionID']]}))
    eZprint('load cartridges complete')

async def runCartridges(input):
    # socketio.emit('sendCartridgeStatus', 'Running Cartridge Functions')
    eZprint('running cartridges')
    if(input['sessionID'] in availableCartridges): 
        for cartridge in availableCartridges[input['sessionID']]:
            # print(availableCartridges[input['sessionID']][cartridge])
            if availableCartridges[input['sessionID']][cartridge]['type'] == 'summary':
                # eZprint('running cartridge: ' + cartridge)
                cartVal = availableCartridges[input['sessionID']][cartridge]
                await runMemory(input, cartridge, cartVal)

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
        await  websocket.send(json.dumps({'event':'sendCartridges', 'cartridges':availableCartridges[input['sessionID']]}))

        # asyncio.run(runMemory(input))
        await runCartridges(input)


async def handleChatInput(input):
    eZprint('handling message')
    
    await  websocket.send(json.dumps({'event':'agentState', 'payload':{'agent': agentName, 'state': 'typing'}}))

    promptObject=[]
    # eZprint(input)
    # asyncio.run(updateCartridges(input))
    asyncio.create_task(logMessage(input['sessionID'],input['userID'], input['userName'], input['body']))
    time = str(datetime.now())
    logs.setdefault(input['sessionID'], []).append(
        {"ID": input['ID'],
        "userName": input['userName'],
        "body": input['body'],
        "role": "user",
        "timestamp": time,

            })
    asyncio.create_task(constructChatPrompt(promptObject, input['sessionID'])),
    eZprint('constructChat prompt called')
    # asyncio.create_task(checkCartridges(input))



async def constructChatPrompt(promptObject, sessionID):
    eZprint('constructing chat prompt')
    for promptKey in availableCartridges[sessionID]:
        promptVal = availableCartridges[sessionID][promptKey]
        if (promptVal['enabled'] == True and promptVal['type'] =='prompt'):
            # eZprint('found prompt, adding to string')
            promptObject.append({"role": "system", "content": "\n Prompt instruction for NOVA to follow - " + promptVal['label'] + ":\n" + promptVal['prompt'] + "\n" })
        if (promptVal['enabled'] == True and promptVal['type'] =='summary'):
            if 'blocks' in promptVal:
                promptObject.append({"role": "system", "content": "\n Summary from past conversations - " + promptVal['label'] + ":\n" + str(promptVal['blocks']) + "\n" })
        if (promptVal['enabled'] == True and promptVal['type'] =='index'):
            if 'blocks' in promptVal:
            # eZprint('found document, adding to string')
                promptObject.append({"role": "system", "content": "\n" + promptVal['label'] + " sumarised by index-query -:\n" + str(promptVal['blocks']) + "\n. If this is not sufficient simply request more information" })

    promptSize = estimateTokenSize(str(promptObject))
    
    for chat in logs[sessionID]:
        # eZprint('found chat, adding to string')
        # eZprint(chat)
        if 'muted' not in chat or chat['muted'] == False:
            if chat['role'] == 'system':
                promptObject.append({"role": "assistant", "content": chat['body']})
            if chat['role'] == 'user':  
                promptObject.append({"role": "user", "content": chat['body']})
            
    eZprint('prompt constructed')

    chatSize =  estimateTokenSize(str(promptObject)) - promptSize
    
    # if(promptSize + chatSize > 6000):
    asyncio.create_task(websocket.send(json.dumps({'event':'sendPromptSize', 'payload':{'promptSize': promptSize, 'chatSize': chatSize}})))

    #fake response
    if app.config['DEBUG']:
        content = fakeResponse()
        await asyncio.sleep(1)
    else :
        response = await sendChat(promptObject)
        eZprint('response received')
        print(response)
        content = str(response["choices"][0]["message"]["content"])
    asyncio.create_task(logMessage(sessionID, agentName, agentName,
                content))
    ID = secrets.token_bytes(4).hex()
    time = str(datetime.now())
    log = {
        "ID":ID,
        "key":ID,
        "userName": agentName,
        "body": content,
        "role": "system",
        "timestamp": time,
         }
    asyncio.create_task(websocket.send(json.dumps({'event':'sendResponse', 'payload':log})))
    # socketio.emit('sendResponse', log)
    logs.setdefault(sessionID, []).append(log)
    await  websocket.send(json.dumps({'event':'agentState', 'payload':{'agent': agentName, 'state': ''}}))
    
def estimateTokenSize(text):
    tokenCount =  text.count(' ') + 1
    return tokenCount

# def handleTokenFull():

def fakeResponse():
    return random.choice(["To be, or not to be, that is the question", "Love looks not with the eyes, but with the mind; and therefore is winged Cupid painted blind.", "Get thee to a nunnery. ",  "To be, or not to be: that is the question.",
    "All the world's a stage, And all the men and women merely players.",
    "The course of true love never did run smooth.",
    "We know what we are, but know not what we may be.",
    "A man can die but once.",
    "Nothing will come of nothing.",
    "Love all, trust a few, do wrong to none.",
    "Cowards die many times before their deaths; the valiant never taste of death but once.",
    "Better three hours too soon than a minute too late.",
    "The fault, dear Brutus, is not in our stars, but in ourselves, that we are underlings.",
    "All's well that ends well.",
    "Good night, good night! Parting is such sweet sorrow, That I shall say good night till it be morrow.",
    "Uneasy lies the head that wears a crown.",
    "Our doubts are traitors and make us lose the good we oft might win by fearing to attempt.",
    "What's in a name? A rose by any other name would smell as sweet.",
    "The eyes are the window to your soul.",
    "We are such stuff as dreams are made on, and our little life is rounded with a sleep.",
    "If music be the food of love, play on.",
    "There is nothing either good or bad, but thinking makes it so.",
    "Brevity is the soul of wit."])

# async def checkCartridges(input):
#     eZprint('checking cartridges')
#     # for cartKey in availableCartridges[input['sessionID']]:
#     #     cartVal = availableCartridges[input['sessionID']][cartKey]
#     #     if 'softDelete' in cartVal:
#     #         if cartVal['softDelete'] == True:
#     #             eZprint('soft delete detected')
#     #             cartVal['enabled'] = False
#     #     if cartVal['type'] == 'index' and cartVal['enabled'] == True :
#     #         eZprint('index query detected')
#     #         index = await getCartridgeDetail(cartKey)
#     #         await triggerQueryIndex(cartKey, cartVal, input, index)
#         # if cartVal['type'] == 'prompt':
#         #     eZprint('found prompt, adding to string')
#         #     promptObject.append({"role": "system", "content": "\n Prompt - " + cartVal['label'] + ":\n" + cartVal['prompt'] + "\n" })
           
async def handleIndexQuery(userID, cartKey, sessionID, query):
    eZprint('handling index query')
    cartVal = availableCartridges[sessionID][cartKey]
    if cartVal['type'] == 'index' and cartVal['enabled'] == True :
        index = await getCartridgeDetail(cartKey)
        await triggerQueryIndex(userID, cartKey, cartVal, query, index, sessionID)

async def sendChat(promptObj):
    loop = asyncio.get_event_loop()
    response = await loop.run_in_executor(None, lambda: openai.ChatCompletion.create(model="gpt-4",messages=promptObj))
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

async def addAuth(userID, userName, credentials):
    credentials = await prisma.user.create(
        data= {
            'UserID': userID,
            'name': 'sam',
            'blob': Json({'credentials': credentials})
        }
    )
    return credentials

async def getAuth(userID):
    credentials = await prisma.user.find_unique(
        where={
            'UserID': userID
        }
    )
    return credentials


async def addCartridgePrompt(input):
    # await prisma.disconnect()
    # await prisma.connect()
    eZprint('add cartridge prompt triggered')
    # eZprint(input)
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
    
    await  websocket.send(json.dumps({'event':'updateTempCart', 'payload':payload}))
    # socketio.emit('updateTempCart', payload)

async def updateCartridgeField(input):
    # await prisma.disconnect()
    # await prisma.connect()
    # eZprint('soft deleting cartridge')
    cartridge = availableCartridges[input['sessionID']]
    targetCartKey = input['cartKey']
    targetCartVal = cartridge[targetCartKey]
    # eZprint('val before update')
    # print(targetCartVal)
    matchedCart = await prisma.cartridge.find_first(
        where={
        'blob':
        {'equals': Json({input['cartKey']: targetCartVal})}
        }, 
    )
    for key, val in input['fields'].items():
        targetCartVal[key] = val

    input['fields']['state'] = ''

    # print(targetCartVal)
    if matchedCart:
        updatedCart = await prisma.cartridge.update(
            where={ 'id': matchedCart.id },
            data={
                'UserID': input['userID'],
                'blob' : Json({targetCartKey:targetCartVal})
            }
        )
        # eZprint(updatedCart)
    payload = { 'key':targetCartKey,'fields': {'state': ''}}
    await  websocket.send(json.dumps({'event':'updateCartridgeFields', 'payload':payload}))
    await getPromptEstimate(input['sessionID'])

    # socketio.emit('updateCartridgeFields', payload)
    # await prisma.disconnect()

async def getPromptEstimate(sessionID):
    promptObject = []
    for promptKey in availableCartridges[sessionID]:
        promptVal = availableCartridges[sessionID][promptKey]
        if (promptVal['enabled'] == True and promptVal['type'] =='prompt'):
            # eZprint('found prompt, adding to string')
            promptObject.append({"role": "system", "content": "\n Prompt instruction for NOVA to follow - " + promptVal['label'] + ":\n" + promptVal['prompt'] + "\n" })
        if (promptVal['enabled'] == True and promptVal['type'] =='summary'):
            if 'blocks' in promptVal:
                promptObject.append({"role": "system", "content": "\n Summary from past conversations - " + promptVal['label'] + ":\n" + str(promptVal['blocks']) + "\n" })
        if (promptVal['enabled'] == True and promptVal['type'] =='index'):
            if 'blocks' in promptVal:
            # eZprint('found document, adding to string')
                promptObject.append({"role": "system", "content": "\n" + promptVal['label'] + " sumarised by index-query -:\n" + str(promptVal['blocks']) + "\n. If this is not sufficient simply request more information" })
    promptSize = estimateTokenSize(str(promptObject))
    asyncio.create_task(websocket.send(json.dumps({'event':'sendPromptSize', 'payload':{'promptSize': promptSize}})))


async def updateContentField(input):
    logsToUpdate = logs[input['sessionID']]
    for log in logsToUpdate:
        if log['ID'] == input['ID']:
            for key, val in input['fields'].items():
                log[key] = val
                # print(log)
    await getChatEstimate(input['sessionID'])

async def getChatEstimate(sessionID):
    promptObject = []
    for chat in logs[sessionID]:
        # eZprint('found chat, adding to string')
        # eZprint(chat)
        if 'muted' not in chat or chat['muted'] == False:
            if chat['role'] == 'system':
                promptObject.append({"role": "assistant", "content": chat['body']})
            if chat['role'] == 'user':  
                promptObject.append({"role": "user", "content": chat['body']})
            
    promptSize = estimateTokenSize(str(promptObject))
    asyncio.create_task(websocket.send(json.dumps({'event':'sendPromptSize', 'payload':{'chatSize': promptSize}})))

async def addCartridgeTrigger(userID, sessionID, cartVal):
    eZprint('adding cartridge triggered')
    newCart =  await addCartridgeAsync(userID,sessionID, cartVal)
    return newCart
    
async def addCartridgeAsync(userID, sessionID, cartVal):
    eZprint('adding cartridge async')
    eZprint(cartVal)
    # await prisma.disconnect()
    # await prisma.connect()
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
                'index':cartVal['index'],
                'indexType': cartVal['indexType'],

            }})
        }
    )
    eZprint('new index cartridge added to [nova]')
    cartdigeLookup.update({cartKey: newCart.id}) 
    availableCartridges[sessionID].update({cartKey:cartVal})
    # await prisma.disconnect()
    return newCart.blob


async def addNewUserCartridgeTrigger(userID,cartKey, cartVal):
    eZprint('adding cartridge triggered')
    newCart = await addNewUserCartridgeAsync(userID,cartKey, cartVal)
    return newCart
    
async def  addNewUserCartridgeAsync(userID, cartKey, cartVal):
    eZprint('adding cartridge async')
    eZprint(cartVal)
    # await prisma.disconnect()
    # await prisma.connect()
    # indexJsonsed = Json(cartVal['index'])
    newCart = await prisma.cartridge.create(
        data={
            'UserID': userID,
            'blob': Json({cartKey:cartVal})
        }
    )
    eZprint('new index cartridge added to [nova]')
    # await prisma.disconnect()
    return newCart.blob
     
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


async def triggerQueryIndex(userID, cartKey, cartVal, query, indexJson, sessionID):
    if(app.config['DEBUG'] == True):
        print('debug mode')
        cartVal['state'] = ''
        cartVal['status'] = ''
        cartVal['blocks'].append({'query':query, 'response':'fakeresponse'})
        payload = { 'key':cartKey,'fields': {
            'status': cartVal['status'],
            'blocks':cartVal['blocks'],
            'state': cartVal['state']
        }}
        print(payload)
        await  websocket.send(json.dumps({'event':'updateCartridgeFields', 'payload':payload}))
        return
        
    eZprint('triggering index query')
    oldVal = cartVal
    # print(input['message'])
    cartVal['state'] = 'loading'
    cartVal['status'] = 'indexFound'
    payload = { 'key':cartKey,'fields': {
                            'status': cartVal['status'],
                            'state': cartVal['state']
                                }}
    # socketio.emit('updateCartridgeFields', payload)
    
    index = await gptindex.reconstructIndex(indexJson, sessionID)
    insert = await gptindex.queryIndex(query, index, cartVal['indexType'])
    eZprint('index query complete')
    # eZprint(insert)
    if(insert != None):
        cartVal['state'] = ''
        cartVal['status'] = ''
        cartVal['blocks'].append({'query':query, 'response':str(insert)})
        # cartVal['blocks'].append(str(insert))
        payload = { 'key':cartKey,'fields': {
                            'status': cartVal['status'],
                            'blocks':cartVal['blocks'],
                            'state': cartVal['state']
                                }}

        id = cartdigeLookup[cartKey]
        print(id)
        matchedCart = await prisma.cartridge.find_first(
            where={
                    'id': id
                    
                    }
        )
        print(matchedCart)
        print(cartVal)
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
    # await prisma.disconnect()
    # await prisma.connect()
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
    # await prisma.disconnect()
    return index

# def logQueryReply(input, insert):
#     asyncio.run(logMessage(input['sessionID'], 'index-query', insert))
#     logs.setdefault(input['sessionID'], []).append(
#         {"userName": 'index-query',
#         "message": insert,
#         "role": "system"
#         })




async def logMessage(sessionID, userID, userName, body):
    if app.config['DEBUG']:
        return
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
            "body": body,
        }
    )


def eZprint(string):
    # return
    # socketio.emit('sendDebug', str(string))

    print('\n _____________ \n')
    print(string)
    print('\n _____________ \n')

    # data['userID'], data['sessionID'], data['content'], data['tempKey']
async def summariseChatBlocks(userID, sessionID, messageIDs, summaryID):
    messagesToSummarise = []
    for messageID in messageIDs:
        for message in logs[sessionID]:
            if messageID == message['ID']:
                messagesToSummarise.append(message)
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
            "SessionID": sessionID,
            "UserID": userID,
            "timestamp": datetime.now(),
            "blob": Json({summaryID:summarDict})

        }
    )
    print(summary)
   #inject summary object into logs before messages it is summarising 
    injectIndex = logs[sessionID].index(messagesToSummarise[0])
    logs[sessionID].insert(injectIndex, {'ID':summaryID, 'name': 'summary', 'body':summaryID, 'role':'system', 'timestamp':datetime.now(), 'summaryState':'SUMMARISED', 'muted':True, 'minimised':True, 'summaryID':summaryID})

    for message in messagesToSummarise:
        remoteMessage = await prisma.message.find_first(
            where={'id': message['id']}
        )
        if remoteMessage:
            updatedMessage = await prisma.message.update(
                where={ 'id': message['id'] },
                data={
                    'summaryState': 'SUMMARISED',
                    'muted': True,
                    'minimised': True,
                    'summaryID': summaryID
                 }
            )
            message['summaryState'] = 'SUMMARISED'
            message['muted'] = True
            message['minimised'] = True
            
            print(message)
            payload = {'ID':message['ID'], 'fields' :{ 'summaryState': 'SUMMARISED'}}
            await  websocket.send(json.dumps({'event':'updateMessageFields', 'payload':payload}))

    



async def runMemory(input, cartKey, cartVal):

    eZprint('running memory')
    # eZprint(cartKey)
    remoteLogs = await prisma.log.find_many(
        where={'UserID': input['userID']}
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
    # eZprint('result of remote log check')
    # print(remoteLogs)

    if(len(remoteLogs) > 0):
        allLogs.setdefault(
            input['sessionID'], remoteLogs)
        for log in allLogs[input['sessionID']]:
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
            where={'UserID': input['userID']}
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
                where={'UserID': input['userID']}
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
                        'summary': batchSummary, 'batched': False, 'UserID': input['userID'] })
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
            await  websocket.send(json.dumps({'event':'updateCartridgeFields', 'payload':payload}))

            # socketio.emit('updateCartridgeFields', payload)
            # await prisma.disconnect()
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

        # socketio.emit('updateCartridgeFields', payload)
        await  websocket.send(json.dumps({'event':'updateCartridgeFields', 'payload':payload}))





async def getSummary(textToSummarise):
    promptObject = []

    initialPrompt = "Create a concise and coherent summary of this text, focusing on the key information, main topics, and outcomes. Ensure that the summary is easy to understand and remember, providing enough context for CHAT GPT to accurately reference the conversation.\nTEXT TO SUMMARISE:\n"
    # promptObject.append({'role' : 'system', 'content' : initialPrompt})
    promptObject.append({'role' : 'system', 'content' : initialPrompt})
    promptObject.append({'role' : 'user', 'content' : textToSummarise})
    response = await sendChat(promptObject)

    return response["choices"][0]["message"]["content"]


async def GetSummaryWithPrompt(prompt, textToSummarise):
    promptObject = []
    promptObject.append({'role' : 'system', 'content' : prompt})
    promptObject.append({'role' : 'user', 'content' : textToSummarise})
    response = await sendChat(promptObject)

    return response["choices"][0]["message"]["content"]