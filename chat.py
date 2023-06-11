from datetime import datetime
import json
import asyncio
import random
import secrets
import openai
from copy import deepcopy

from debug import eZprint
from appHandler import websocket
from sessionHandler import novaConvo, chatlog, availableCartridges
from prismaHandler import prisma
from prompt import construct_prompt, construct_chat_query, current_prompt
from query import sendChat
from commands import handle_commands    

agentName = 'nova'


async def user_input(sessionData):
    #takes user iput and runs message cycle
    #TODO add prompt size management
    convoID = sessionData['convoID']
    message = sessionData['body'].strip()
    await handle_message(convoID, message, 'user', sessionData['ID']), 
    await construct_prompt(convoID),
    await construct_chat_query(convoID)
    query_object = current_prompt[convoID]['prompt'] + current_prompt[convoID]['chat']
    await send_to_GPT(convoID, query_object)

async def handle_message(convoID, message, role = 'user', key = None):

    eZprint('handling new log')

    print(message, role, key)
    #handles input from any source, adding to logs and records 
    # TODO: UPDATE SO THAT IF ITS TOO BIG IT SPLITS AND SUMMARISES OR SOMETHING

    userID = novaConvo[convoID]['userID']
    if role == 'user':
        userName = novaConvo[convoID]['userName']
    elif role == 'assistant':
        userName = agentName
    else:
        userName = 'system'

    sessionID = novaConvo[convoID]['sessionID']

    if key == None:
        key = secrets.token_bytes(4).hex()
    if convoID not in chatlog:
        chatlog[convoID] = []

    order = await getNextOrder(convoID)

    messageObject = {
        "sessionID": sessionID +'-'+convoID,
        "ID": key, ##actually sending what is stored as key
        "userName": userName,
        "userID": str(userID),
        "body": message,
        "role": role,
        "timestamp": str(datetime.now()),
        "order": order,
    }

    chatlog[convoID].append(messageObject)
    asyncio.create_task(logMessage(messageObject))
    copiedMessage = deepcopy(messageObject)

    if( role == 'assistant'):
        json_object = parse_json_string(message)
        if json_object != None:
            copiedMessage = deepcopy(messageObject)
            response = await get_json_val(json_object, 'speak')
            copiedMessage['body'] = response
        
        asyncio.create_task(websocket.send(json.dumps({'event':'sendResponse', 'payload':copiedMessage})))
        await  websocket.send(json.dumps({'event':'agentState', 'payload':{'agent': agentName, 'state': ''}}))


async def send_to_GPT(convoID, promptObject):
    
    ## sends prompt object to GPT and handles response
    eZprint('sending to GPT')
    print(promptObject)
    await  websocket.send(json.dumps({'event':'agentState', 'payload':{'agent': agentName, 'state': 'typing'}}))
    response = await sendChat(promptObject, 'gpt-3.5-turbo')
    content = str(response["choices"][0]["message"]["content"])
    eZprint('response recieved')
    print(response)

    ##check if response string is able to be parsed as JSON or is just a  or string
    json_object = None
    parsed_reply = ''
    json_object = parse_json_string(content)
    
    if json_object != None:
        eZprint('response is JSON')
        command = await get_json_val(json_object, 'command')
        if command != None:
            eZprint('command found')
            command_response = await handle_commands(command, convoID)
            eZprint(command_response)
            if command_response:
                command_response = json.dumps(command_response)
                await handle_message(convoID, command_response, 'system')
    await handle_message(convoID, content, 'assistant')

    

async def command_interface(responseVal, convoID):
    #handles commands from user input
    system_response = await handle_commands(responseVal, convoID)

    handle_message(convoID, system_response, 'system')
    

def estimateTokenSize(text):
    tokenCount =  text.count(' ') + 1
    return tokenCount

async def sendChat(promptObj, model):
    loop = asyncio.get_event_loop()
    response = await loop.run_in_executor(None, lambda: openai.ChatCompletion.create(model=model,messages=promptObj))
    return response

async def logMessage(messageObject):
    print('logging message')

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

async def get_json_val(json_object, key_requested):
 
    eZprint('getting val ' + key_requested+ ' from json')
    for responseKey, responseVal in json_object.items():
        if responseVal != None:
            for key, val in responseVal.items():
                if key_requested == key:
                    return val
            if key_requested ==  responseKey:
                return responseVal
            
    return None 



def parse_json_string(content):

    # eZprint('parsing json string')
    # print(content)
    try:
        # try to parse the content string as a JSON object
        # eZprint('trying to parse json')
        # print(content)

        json_object = json.loads(content)
        # eZprint('json parsed')

        return json_object

    except ValueError as e:
        # the string is not valid JSON, try to remove unwanted characters
        print(f"Error parsing JSON: {e}")
        print('trying to remove newlines and extra spaces...')
        print(content)

        # remove unwanted newline and whitespace characters using the replace function
        content = content.replace('\n', '').replace('  ', '')

        try: 
            eZprint('trying to parse json')
            print(content)

            # try to parse the string as a JSON object again after removing unwanted characters
            json_object = json.loads(content)
            # print(json_object)

            return json_object

        except ValueError as e:
            # the string is still not valid JSON, print the error message
            print(f"Error parsing JSON: {e}")
            return None