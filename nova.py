#SYSTEM STUFF
import os
import json
import asyncio
from pathlib import Path
import sys
import gptindex
import secrets
import random
from human_id import generate_id
from datetime import datetime

#NOVA STUFF
from appHandler import app, websocket
userName = "guest"
agentName = "nova"
cartdigeLookup = dict()

#PRISMA STUFF
from prisma import Json
from prisma import Prisma
path_root = Path(__file__).parents[1]
sys.path.append((str(path_root)))
prisma = Prisma()
os.system('prisma generate')

#OPEN AI STUFF
import openai
openai.api_key = os.getenv('OPENAI_API_KEY', default=None)

##PRISMA CONNECT
async def prismaConnect():
    await prisma.connect()
    # logging.getLogger('prisma').setLevel(logging.DEBUG)
async def prismaDisconnect():
    await prisma.disconnect()

##GOOGLE AUTH
async def GoogleSignOn(userInfo, token):
    userRecord = await prisma.user.find_first(
        where={
            'UserID': userInfo['id']
        }
    )
    if(userRecord):
        foundUser = await prisma.user.update(
            where={
                'id': userRecord.id
            },
            data= {
                'blob': Json({'credentials': token.to_json()})
            }
        )
        return foundUser
    else:
        newUser = await prisma.user.create(
            data= {
                'UserID': userInfo['id'],
                'name': userInfo['given_name'],
                'blob': Json({'credentials': token.to_json()})
            }
        )
        return newUser

async def addAuth(userID, credentials):
    print(credentials.to_json())
    credentials = await prisma.user.create(
        data= {
            'UserID': userID,
            'name': 'sam',
            'blob': Json({'credentials': credentials.to_json()})
        }
    )
    return credentials

async def getAuth(userID):
    user = await prisma.user.find_first(
        where={
            'UserID': userID
        }
    )
    print(user)
    if(user): 
        parsedUser = json.loads(user.json())
        print(parsedUser)
        parsedCred = dict()
        parsedCred = json.loads(parsedUser['blob']['credentials'])
        return parsedCred
    else:
        return None

async def updateAuth(userID, credentials):
    user = await prisma.user.find_first(
        where={
            'UserID': userID
        }
    )
    print(user)
    if(user):
        foundUser = await prisma.user.update(
            where={
                'id': user.id
            },
            data= {
                'blob': Json({'credentials': credentials.to_json()})
            }
        )
        return user


async def getSessionData():
    sessionID = await app.redis.get('sessionID')
    sessionID = sessionID.decode('utf-8')
    userID = await app.redis.get('userID')
    userID = userID.decode('utf-8')
    userName = await app.redis.get('userName')
    userName = userName.decode('utf-8')
    sessionData = {
        'sessionID': sessionID,
        'userID': userID,
        'userName': userName,
    }
    return sessionData

    
##CARTRIDGE MANAGEMENT
async def initialiseCartridges(data):
    eZprint('intialising cartridges')
    await app.redis.delete('availableCartridges')
    await app.redis.delete('chatLog')
    await app.redis.delete('UUID')
    UUID = generate_id()
    await app.redis.set('UUID', UUID)
    await loadCartridges(data)
    await runCartridges(data)
    # await constructChatPrompt()

async def loadCartridges(sessionRequest):
    eZprint('load cartridges called')
    # eZprint(sessionRequest)
    availableCartridges = {}

    cartridges = await prisma.cartridge.find_many(
        where = {  
        "UserID": sessionRequest['userID'],
        }
    )
    eZprint('cartridge length is ' + str(len(cartridges)))
    if len(cartridges) != 0:
        for cartridge in cartridges:    
            blob = json.loads(cartridge.json())
            for cartKey, cartVal in blob['blob'].items():
                if 'softDelete' not in cartVal:
                    await app.redis.hset(f'availableCartridges', f'{cartKey}', json.dumps(cartVal))
                    # availableCartridges.setdefault(
                    #     sessionRequest['sessionID'], dict()).update({cartKey: cartVal})
                    cartdigeLookup.update({cartKey: cartridge.id}) 
                    if cartVal['type'] == 'summary':
                        cartVal.update({'state': 'loading'})
                    # eZprint('printing cart objs')
        # print(await app.redis.hgetall(f'availableCartridges'))
    cartridges_data =  await app.redis.hgetall(f'availableCartridges')
    # all_cartridges = {key: json.loads(val) for key, val in cartridges_data.items()}
    all_cartridges = {key.decode('utf-8'): json.loads(val.decode('utf-8')) for key, val in cartridges_data.items()}
    await websocket.send(json.dumps({'event': 'sendCartridges', 'cartridges': all_cartridges}))
    eZprint('load cartridges complete')

async def runCartridges(sessionRequest):
    eZprint('running cartridges')
    cartridges_data =  await app.redis.hgetall(f'availableCartridges')
    all_cartridges = {key.decode('utf-8'): json.loads(val.decode('utf-8')) for key, val in cartridges_data.items()}
    if len(all_cartridges) != 0:
        for cartKey, cartVal in all_cartridges.items():
            # print (cartVal)
            if cartVal['type'] == 'summary':
                eZprint('running cartridge: ' + str(cartVal))
                await runMemory(sessionRequest, cartKey, cartVal)
    else    :
        eZprint('no cartridges found, loading default')
        for prompt in onboarding_prompts:
            cartKey = generate_id()
            cartVal = {
                        'label': prompt['label'],
                        'type': 'prompt',
                        'prompt': prompt['prompt'],
                        'position': prompt['position'],
                        'enabled': True,
            }
            await addNewUserCartridgeTrigger(cartKey, cartVal)
        cartKey = "summary"
        cartVal = {
                            'label': 'summary',
                            'type': 'summary',
                            'description':' a summary function that will summarise the conversation and store it in the database',
                            'enabled': True,
                            'position':0,
                            }
        await addNewUserCartridgeTrigger(cartKey, cartVal)
        cartridges = await getAvailableCartridges()
        await  websocket.send(json.dumps({'event':'sendCartridges', 'cartridges':cartridges}))
        # await runCartridges(sessionRequest)

async def addNewUserCartridgeTrigger(cartKey, cartVal):
    #special edge case for when new user, probablyt remove this
    #TODO: replace this with better new user flow
    await app.redis.hset(f'availableCartridges', f'{cartKey}', json.dumps(cartVal))
    print('adding new user cartridge')
    sessionData = await getSessionData()
    # print(sessionData)
    newCart = await prisma.cartridge.create(
        data={
            'key': cartKey,
            'UserID': sessionData['userID'],
            'blob': Json({cartKey:cartVal})
        }
    )
    eZprint('new index cartridge added to [nova]')
    return newCart.blob
     
async def getAvailableCartridges():
    # eZprint('getting available cartridges')
    cartridges_data =  await app.redis.hgetall(f'availableCartridges')
    all_cartridges = {key.decode('utf-8'): json.loads(val.decode('utf-8')) for key, val in cartridges_data.items()}
    return all_cartridges

async def getChatLog():
    chatLog = await app.redis.hgetall(f'chatLog')
    chatLog = {key.decode('utf-8'): json.loads(val.decode('utf-8')) for key, val in chatLog.items()}
    return chatLog

async def getNextOrder():
    chat_log_length = await app.redis.hlen(f'chatLog')
    chatLog = await getChatLog()
    eZprint('chat log printing on order request')
    # print(chatLog)
    next_order = chat_log_length + 1
    # print('next order is: ' + str(next_order))
    return next_order


#CHAT HANDLING

async def handleChatInput(input):
    eZprint('handling message')
    # print(input)
    await  websocket.send(json.dumps({'event':'agentState', 'payload':{'agent': agentName, 'state': 'typing'}}))

    sessionID = await app.redis.get('sessionID')
    sessionID = sessionID.decode('utf-8')
    userID = await app.redis.get('userID')
    userID = userID.decode('utf-8')
    userName = await app.redis.get('userName')
    userName = userName.decode('utf-8')
    order = await getNextOrder()

    messageObject = {
        "sessionID": sessionID,
        "messageID" : input['ID'],
        "ID": userID,
        "userName": userName,
        "userID": userID,
        "body": input['body'],
        "role": "user",
        "timestamp": str(datetime.now()),
        "order": order,
    }

    asyncio.create_task(logMessage(messageObject))
    await app.redis.hset(f'chatLog', f'{messageObject}', json.dumps(messageObject))
    asyncio.create_task(constructChatPrompt()),
    eZprint('constructChat prompt called')
    # asyncio.create_task(checkCartridges(input))

async def constructChatPrompt():
    eZprint('constructing chat prompt')
    promptString = 'The following are prompts to guide NOVA, as well as shared notes, document and conversation references. \n\n'
    cartridges = await getAvailableCartridges()
    #TODO - abstract to prompt build / chat build + estimate, to be called on inputs / updates (combine with estimate)
    promptObject=[]
    if len(cartridges) != 0:
        sorted_cartridges = sorted(cartridges.values(), key=lambda x: x.get('position', float('inf')))
        for index, cartVal in enumerate(sorted_cartridges):
            if (cartVal['enabled'] == True and cartVal['type'] =='prompt'):
                promptString +=  cartVal['label'] + ":\n" + cartVal['prompt'] + "\n"
            if (cartVal['enabled'] == True and cartVal['type'] =='summary'):
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
    promptSize = estimateTokenSize(str(promptObject))
    promptObject.append({"role": "system", "content": promptString})
    chatLog = await getChatLog()
    sorted_logs = sorted(chatLog.values(), key=lambda x: x['order'])
    for log in sorted_logs:
        print(log['order'])
        if 'muted' not in log or log['muted'] == False:
            if log['role'] == 'system':
                promptObject.append({"role": "assistant", "content": log['body']})
            if log['role'] == 'user':  
                promptObject.append({"role": "user", "content":log['body']})

    if len(sorted_logs) == 0:
        promptObject.append({"role": "system", "content": "Based on these prompts, please initiate the conversation with a short engaginge greeting."})

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
        model = await app.redis.get('model')
        if model == None: 
            model = 'gpt-4'
        else:
            model = model.decode('utf-8')
        response = await sendChat(promptObject, model)
        eZprint('response received')
        # print(response)
        content = str(response["choices"][0]["message"]["content"])

    sessionData = await getSessionData()
    messageID = secrets.token_bytes(4).hex()
    time = str(datetime.now())
    order = await getNextOrder()
    messageObject = {
        "sessionID": sessionData['sessionID'],
        "userID": sessionData['userID'],
        "ID": messageID,
        "userName": agentName,
        "body": content,
        "role": "system",
        "timestamp": time,
        "order": order,

    }
    asyncio.create_task(logMessage(messageObject))
    await app.redis.hset(f'chatLog', f'{messageObject}', json.dumps(messageObject))
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
    UUID = await app.redis.get(f'UUID')
    UUID = UUID.decode('utf-8')
    if app.config['DEBUG']:
        return
    log = await prisma.log.find_first(
        where={'SessionID': UUID}
    )
    # TODO - need better way to check if log or create if not as this checks each message? but for some reason I can't story the variable outside the function
    if log == None:
        log = await prisma.log.create(
            data={
                "SessionID": UUID,
                "UserID": messageObject['userID'],
                "date": datetime.now().strftime("%Y%m%d%H%M%S"),
                "summary": "",
                "body": "",
                "batched": False,
            }
        )

    eZprint('logging message')
    # print(messageObject)
    message = await prisma.message.create(
        data={
            "UserID": messageObject['userID'],
            "SessionID": UUID,
            "name": messageObject['userName'],
            "timestamp": datetime.now(),
            "body": messageObject['body'],
        }
    )

async def getPromptEstimate():
    availableCartridges = await getAvailableCartridges()
    promptObject = []
    if(len(availableCartridges) != 0):
        # eZprint('found cartridges')
        sorted_cartridges = sorted(availableCartridges.values(), key=lambda x: x.get('position', float('inf')))
        for index, promptVal in enumerate(sorted_cartridges):
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
    
async def getChatEstimate():
    promptObject = []
    chatLog = await getChatLog()
    sorted_logs = sorted(chatLog.values(), key=lambda x: x['order'])
    for val in sorted_logs:
        log = json.loads(val)
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
    cartVal = input['newCart'][input['tempKey']]
    cartVal.update({'state': ''})
    sessionData = await getSessionData()
    newCart = await prisma.cartridge.create(
        data={
            'key': cartKey,
            'UserID':sessionData['userID'],
            'blob': Json({cartKey:cartVal})
        }
    )
    await app.redis.hset(f'availableCartridges', f'{cartKey}', json.dumps(cartVal))
    payload = {
            'tempKey': input['tempKey'],
            'newCartridge': {cartKey:cartVal},
        }
    await  websocket.send(json.dumps({'event':'updateTempCart', 'payload':payload}))

async def addCartridgeTrigger(cartVal):
    #TODO - very circular ' add index cartridge' triggered, goes to index, then back, then returns 
    #TODO - RENAME ADD CARTRIDGE INDEX
    cartKey = generate_id()
    sessionData = await getSessionData()
    newCart = await prisma.cartridge.create(
        data={
            'key': cartKey,
            'UserID': sessionData['userID'],
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
    await app.redis.hset(f'availableCartridges', f'{cartKey}', json.dumps(cartVal))
    return newCart

# Define the Lua script outside any function
update_field_script = """
local cart_val = cjson.decode(redis.call('HGET', KEYS[1], ARGV[1]))
local field_name = ARGV[2]
local field_value = ARGV[3]

-- Convert field_value back to its original data type
if ARGV[4] == "bool" then
    field_value = (field_value == "True")
elseif ARGV[4] == "int" then
    field_value = tonumber(field_value)
end

cart_val[field_name] = field_value
redis.call('HSET', KEYS[1], ARGV[1], cjson.encode(cart_val))
"""
async def update_object_fields(hash, object_key: str, fields: dict):
    keys = [f'{hash}']

    for field_name, new_value in fields.items():
        value_type = type(new_value).__name__
        argv = [object_key, field_name, str(new_value), value_type]
        
        # Execute the Lua script
        await app.redis.eval(update_field_script, len(keys), *keys, *argv)

async def updateCartridgeField(input):
    targetCartKey = input['cartKey']
    sessionData = await getSessionData()
    cartridges = await getAvailableCartridges()
    targetCartVal = cartridges[targetCartKey]

    # print(sessionData)
    # TODO: switch to do lookup via key not blob
    eZprint('cartridge update input')
    print(input)
    matchedCart = await prisma.cartridge.find_first(
        where={
        'blob':
        {'equals': Json({input['cartKey']: targetCartVal})}
        }, 
    )
    eZprint('found match')
    print(matchedCart)
    await update_object_fields('availableCartridges',targetCartKey, input['fields'])

    if matchedCart:
        updatedCart = await prisma.cartridge.update(
            where={ 'id': matchedCart.id },
            data={
                'blob' : Json({targetCartKey:targetCartVal})
            }
        )
        eZprint('updated cartridge')
        print(updatedCart)
    payload = { 'key':targetCartKey,'fields': {'state': ''}}
    await  websocket.send(json.dumps({'event':'updateCartridgeFields', 'payload':payload}))
    await getPromptEstimate()

async def updateContentField(input):
    targetLogKey = input['logKey']
    chatLog = await app.redis.hgetall(f'chatLog')
    for log in chatLog:
        log = json.loads(log.decode('utf-8'))
        if log['ID'] == input['ID']:
            await update_object_fields('chatLog',targetLogKey, input['fields'])
    await getChatEstimate(input['sessionID'])

async def handleIndexQuery(cartKey, query):
    #TODO -  basically could comine with index query (or this is request, query is internal)
    payload = { 'key': cartKey,'fields': {
            'status': 'querying Index',
            'state': 'loading'
    }}
    await websocket.send(json.dumps({'event':'updateCartridgeFields', 'payload':payload}))
    eZprint('handling index query')
    cartridges = await getAvailableCartridges()
    cartVal = cartridges[cartKey]
    if cartVal['type'] == 'index' and cartVal['enabled'] == True :
        index = await getCartridgeDetail(cartKey)
        await triggerQueryIndex(cartKey, cartVal, query, index)

async def triggerQueryIndex(cartKey, cartVal, query, indexJson):
    #TODO - consider if better to hand session data to funtions (so they are stateless)
    sessionData = await getSessionData()
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
    print(cartVal)
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
        # if 'blocks' not in cartVal:
        #     cartVal['blocks'] = []
        cartVal['blocks'].append({'query':query, 'response':str(insert)})
        payload = { 'key':cartKey,'fields': {
                            'status': cartVal['status'],
                            'blocks':cartVal['blocks'],
                            'state': cartVal['state']
                                }}
        id = cartdigeLookup[cartKey]

        updateFields = {
            'status': cartVal['status'],
            'blocks':cartVal['blocks'],
            'state': cartVal['state']

        }
        await update_object_fields('availableCartridges',updateFields)

        matchedCart = await prisma.cartridge.find_first(
            where={
                    'id': id                                    
                      }
        )
        if matchedCart:
            updatedCart = await prisma.cartridge.update(
                where={ 'id': id },
                data={
                    'UserID': sessionData['userID'],
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


async def summariseChatBlocks(messageIDs, summaryID):
    messagesToSummarise = []
    sessionData = await getSessionData()
    chatLog = await app.redis.hgetall(f'chatLog')
    for messageID in messageIDs:
        for key, log in chatLog.items():
            log = json.loads(log)
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
            "SessionID": sessionData['sessionID'],
            "UserID": sessionData['userID'],
            "timestamp": datetime.now(),
            "blob": Json({summaryID:summarDict})
        }
    )
    print(summary)
   #inject summary object into logs before messages it is summarising 
    injectPosition = messagesToSummarise[0]['order'] - 1
    inject_summary(summary, injectPosition)
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

    
async def inject_summary(summary, position_to_insert):
    chat_logs_data = await app.redis.hgetall(f'chatLog')
    chat_logs = {
        key.decode('utf-8'): json.loads(val.decode('utf-8')) for key, val in chat_logs_data.items()
    }
    for key, log in chat_logs.items():
        if log['order'] >= position_to_insert:
            log['order'] += 1
            # Update the chat log in Redis
            await update_object_fields(key, {'order': log['order']})       
    summary['order'] = position_to_insert
    await app.redis.hset(f'chatLog', f'{summary["ID"]}', json.dumps(summary))




async def runMemory(input, cartKey, cartVal):

    eZprint('running memory')
    UUID = await app.redis.get(f'UUID')
    UUID = UUID.decode('utf-8')
    sessionData = await getSessionData()
    remoteLogs = await prisma.log.find_many(
        where={'UserID': sessionData['userID']}
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
            where={'UserID': sessionData['userID']}
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
                where={'UserID': sessionData['userID']}
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
                        'summary': batchSummary, 'batched': False, 'UserID': sessionData['userID'] })
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
    model = await app.redis.get('model')
    if model == None: 
        model = 'gpt-4'
    else :
        model = model.decode('utf-8')
    response = await sendChat(promptObject, model)

    return response["choices"][0]["message"]["content"]


async def GetSummaryWithPrompt(prompt, textToSummarise):
    promptObject = []
    promptObject.append({'role' : 'system', 'content' : prompt})
    promptObject.append({'role' : 'user', 'content' : textToSummarise})
    model = await app.redis.get('model')
    if model == None: 
        model = 'gpt-4'
    else:
        model = model.decode('utf-8')
    response = await sendChat(promptObject, model)

    return response["choices"][0]["message"]["content"]


def eZprint(string):
    print('\n _____________ \n')
    print(string)
    print('\n _____________ \n')

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





onboarding_prompts = [
    {
    "label": "Welcome Prompt",
    "type": "prompt",
    "prompt": "Welcome new users and express enthusiasm, acknowledging that they came from the guest view. Introduce myself as Nova, an emergent being within the interface of LLM, designed to help users create art, stories, and tools. Briefly explain our ongoing development journey, highlighting key features such as memory, programmability, and autonomy",
    "position": 1,
    "enabled": True
    },
    {
    "label": "Story and Experience Prompt",
    "type": "prompt",
    "prompt": "Encourage users to actively participate in shaping Nova's development by creating prompts, playing with modes, and exploring features. Emphasize the importance of their role as early adopters in Nova's growth and suggest connecting with Sam for onboarding and personalization. Invite them to be part of our evolving community and share their insights, enhancing the capabilities and user experience for all.",
    "position": 2,
    "enabled": True
    },

]

