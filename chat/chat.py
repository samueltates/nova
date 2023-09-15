from datetime import datetime
import json
import asyncio
import re
import secrets
import openai
from copy import deepcopy

from session.appHandler import websocket
from session.sessionHandler import novaConvo, novaSession, chatlog, active_cartridges, agentName, system_threads, command_loops
from session.tokens import handle_token_use, check_tokens

from core.loadout import current_loadout, update_loadout_field
from session.prismaHandler import prisma
from core.cartridges import updateContentField
from chat.prompt import construct_query, construct_chat, current_prompt, simple_agents, summarise_at_limit
from chat.query import sendChat
from tools.debug import eZprint
from tools.commands import handle_commands
from tools.memory import get_sessions, summarise_from_range, summarise_percent
from tools.jsonfixes import correct_json


async def agent_initiate_convo(sessionID, convoID, loadout):
    """
    This function is called when the agent initiates a conversation. It will check if there is a message in the novaConvo object, and if so, it will send it to the GPT. It will then construct the query object and send it to GPT 
    """

    # print('agent initiate convo')
    convoID = novaSession[sessionID]['convoID']
    if 'message' in novaConvo[convoID]:       
        # print('message in nova convo' + novaConvo[convoID]['message'])  
        await handle_message(convoID, novaConvo[convoID]['message'], 'user', novaSession[sessionID]['userName'])
    
    await construct_query(convoID),

    if 'message' in novaConvo[convoID]:
        query_object = current_prompt[convoID]['prompt'] + current_prompt[convoID]['chat']
    else:
        query_object = current_prompt[convoID]['prompt']

    if 'emphasise' in current_prompt[convoID]:
        query_object += current_prompt[convoID]['emphasise']

    # if 'command' in novaConvo[convoID]:
    #     if novaConvo[convoID]['command']:
    #         query_object.append({"role": "user", "content": "Based on the prompts, and files available, assess best approach for the conversation, then begin the conversatin with a casual greeting, and complete any actions in parallel:"})
    # else :
    #     query_object.append({"role": "user", "content": "Based on the prompts and content available, begin the conversation with a short response:"})

    model = 'gpt-3.5-turbo'
    if 'model' in novaConvo[convoID]:
        model = novaConvo[convoID]['model']
        # print ('model: ' + model)
    await send_to_GPT(convoID, query_object, 0, model)


async def user_input(sessionData):

    """
    
    """
    #takes user iput and runs message cycle
    # print('user input')
    # print(sessionData)
    convoID = sessionData['convoID']
    message = sessionData['body']
    sessionID = sessionData['sessionID']
    userName = novaSession[sessionID]['userName']

    # print(availableCartridges[convoID])
    
    if 'command' in novaConvo[convoID]:
        message = userName + ': ' + message
        
    await handle_message(convoID, message, 'user', userName, sessionData['key'])
    await construct_query(convoID)
    query_object = current_prompt[convoID]['prompt'] + current_prompt[convoID]['chat'] 

    if 'emphasise' in current_prompt[convoID]:
        query_object += current_prompt[convoID]['emphasise']
    
    if 'command-loop' in novaConvo[convoID] and novaConvo[convoID]['command-loop']:
        print('setting user interupt to true')
        novaConvo[convoID]['user-interupt'] = True
    # print(query_object)    current_prompt[convoID]['prompt'] = list_to_send
    model = 'gpt-3.5-turbo'
    if 'model' in novaConvo[convoID]:
        model = novaConvo[convoID]['model']
        # print ('model: ' + model)
    if message[0] == '/':
        #remove the / and then send to command interface
        message = message[1:]
        json_object = await parse_json_string(message)
        if json_object != None:
            command = await get_json_val(json_object, 'command')
            if command:
                await command_interface(command, convoID, 0)
                print('command found from user')
                return

    print('sending user message to GPT')
    functions = None
    if novaConvo[convoID].get('return_type', '') == 'openAI' and current_prompt[convoID].get('openAI_functions', None):
        functions = current_prompt[convoID]['openAI_functions']


    await send_to_GPT(convoID, query_object, 0, model, functions)

async def handle_message(convoID, message, role = 'user', userName ='', key = None, thread = 0, meta= ''):
    # print('handling message on thread: ' + str(thread)) 
    #handles input from any source, adding to logs and records 
    # TODO: UPDATE SO THAT IF ITS TOO BIG IT SPLITS AND SUMMARISES OR SOMETHING
    sessionID = novaConvo[convoID]['sessionID']
    userID = novaSession[sessionID]['userID']
    sessionID = sessionID  +"-"+convoID
    if novaConvo[convoID].get('command'):
        json_return = novaConvo[convoID]['command']
    else:
        json_return = False

    if sessionID in current_loadout:
        sessionID += "-"+str(current_loadout[sessionID])

    if key == None:
        key = secrets.token_bytes(4).hex()
    if convoID not in chatlog:
        chatlog[convoID] = []
    order = await getNextOrder(convoID)
    
    content = ""
    function_call = ""

    if isinstance(message, dict):
        content = message.get('content', "")
        function_call = message.get('function_call', "")
    
    messageObject = {
        "sessionID": convoID,
        "key": key,
        "userName": userName,
        "userID": str(userID),
        "body": message,
        "content": content,
        "function_call":function_call,
        "role": role,
        "timestamp": str(datetime.now()),
        "order": order,
        "thread": thread,
        "contentType" : 'message'
    }
    print('message object is: ' + str(messageObject))

    id = await logMessage(messageObject)
    # print('message logged' + str(id)    )
    # input = {
    #     'convoID':convoID,
    #     'key':key,
    #     'fields': {'id' : id}
    # }
    # updateContentField(input)
    messageObject['id'] = id
    copiedMessage = deepcopy(messageObject)
    # print(copiedMessage)
    
    command = None

    if thread:
        ##TODO : command returns can give those deeper functions, and include 'close' to close loop
        ##TODO : heck it could even be an array of loops, should get / build events for this
        ##TODO : Clear these threads when done 

        if convoID not in system_threads:
            system_threads[convoID] = {}
        if thread not in system_threads[convoID]:
            ##first log in thread updates chatlog with injected thread (to keep system thread referring to that)
            eZprint('NEW THREAD')
            system_threads[convoID][thread] = []
            messageObject.update({'thread':thread})
            # chatlog[convoID].append(messageObject)
            system_threads[convoID][thread].append(messageObject)
            # print(system_threads[convoID][thread])

        else:

            ##after that each loop it adds to thread 
            ##may be that it needs to bring in updates every so often, but I think just 'waiting for result' on main, and then 'finished or updated' and that can be driven by config
            eZprint('THREAD UPDATE')
            # print(system_threads[convoID][thread])
            system_threads[convoID][thread].append(messageObject)

  

    else:     
        chatlog[convoID].append(messageObject)

    simple_response = None
    # print('json return is ' + str(json_return)) 

    if role == 'user':
        update_message_payload = {
            'convoID':convoID,
            'key':key,
            'fields': {'id' : id}
        }
        asyncio.create_task(websocket.send(json.dumps({'event':'updateMessageFields', 'payload':update_message_payload})))

    if role == 'assistant' :
        # print('role not user')
        ## if its expecting JSON return it'll parse, otherwise keep it normal
        if json_return:
            # print('json return')
            json_object = await parse_json_string(content)
            if json_object != None:
                # print('json object', json_object)
                command = await get_json_val(json_object, 'command')
                
                ##then if there's a response it sends it... wait no this is handling the agent response? so its handling everything, but if the agent responds with the thread no it'll parse that way, or just stay 

                ##basically thinking 'thread requested' so if the message is coming from a specific thread then it'll use / keep to that, otherwise it'll start a new one, using zero as false in this instance.
                # if command:
                # print('command', command)
                print('sending response')
                copiedMessage['body'] = json_object
                copiedMessage['convoID'] = convoID
                asyncio.create_task(websocket.send(json.dumps({'event':'sendResponse', 'payload':copiedMessage, 'convoID': convoID})))
            else: 
                copiedMessage['convoID'] = convoID
                asyncio.create_task(websocket.send(json.dumps({'event':'sendResponse', 'payload':copiedMessage, 'convoID': convoID})))


        else:
            if function_call != "":

                print(function_call)
                print(isinstance, function_call)
                asyncio.create_task(command_interface(function_call, convoID, thread))
            if content != "":
                message = copiedMessage['body']
                # json_wrapped = '{"thoughts": { "speak " : "' + message + '"} }'
                # json_object = await parse_json_string(json_wrapped)
                # print('wrapping in json for return object')
                # print (json_object)
                # if json_object != None:
                #     copiedMessage['body'] = json_object
                #     print('copied message')
                copiedMessage['convoID'] = convoID
                asyncio.create_task(websocket.send(json.dumps({'event':'sendResponse', 'payload':copiedMessage})))




        # print(copiedMessage)
        if len(simple_agents) > 0 and thread == 0:
            if 'user-interupt' not in novaConvo[convoID] or not novaConvo[convoID]['user-interupt']:
                asyncio.create_task(simple_agent_response(convoID))
        if command:
            print('comand found')
            asyncio.create_task(command_interface(command, convoID, thread))
        else:
            print('no command, resetting')
            novaConvo[convoID]['command-loop']= False
            novaConvo[convoID]['steps-taken'] = 0



    if meta == 'terminal':
        messageObject['convoID'] = convoID
        asyncio.create_task(websocket.send(json.dumps({'event':'sendResponse', 'payload':messageObject})))

    if meta == 'simple':
        messageObject['convoID'] = convoID
        asyncio.create_task(websocket.send(json.dumps({'event':'sendResponse', 'payload':messageObject})))
    
    
        
    # eZprint('MESSAGE LINE ' + str(len(chatlog[convoID])) + ' : ' + copiedMessage['body'])    


async def send_to_GPT(convoID, promptObject, thread = 0, model = 'gpt-3.5-turbo', functions = None):
    if novaConvo[convoID].get('summarising'):
        return
    sessionID = novaConvo[convoID]['sessionID']
    userID = novaSession[sessionID]['userID']
    if 'agent-name' not in novaConvo[convoID]:
        # print('setting name to default in chat')
        novaConvo[convoID]['agent-name'] = 'nova'

    print('checking tokens')

    await websocket.send(json.dumps({'event': 'send_prompt_object', 'payload': promptObject}))
    print('sending prompt object' + str(promptObject))
    tokens = await check_tokens(userID)
    if not tokens:
        asyncio.create_task(handle_message(convoID, 'Not enough NovaCoin to continue', 'assistant', 'system', None, thread))
        return
    
    content = ''
    function_call = None
    if thread == 0:
        await  websocket.send(json.dumps({'event':'recieve_agent_state', 'payload':{'agent': novaConvo[convoID]['agent-name'], 'state': 'typing', 'convoID': convoID}}))
    agent_name = novaConvo[convoID]['agent-name']
    try:

        response = await sendChat(promptObject, model, functions)
        message = response["choices"][0]["message"]
        # content = str(response["choices"][0]["message"]["content"])
        print(response)
        # if response["choices"][0]["message"].get('function_call', None):
        #     function_call = response["choices"][0]["message"]["function_call"]
        completion_tokens = response["usage"]['completion_tokens']
        prompt_tokens = response["usage"]['prompt_tokens']
        await handle_token_use(userID, model, completion_tokens, prompt_tokens)

    # except Exception as e:
        
    #     print(e)
    #     print('trying again')

    #     try: 
    #         response = await sendChat(promptObject, model, functions )
    #         message = response["choices"][0]["message"]
    #         content = str(response["choices"][0]["message"]["content"])
    #         if response["choices"][0]["message"].get('function_call', None):
    #             function_call = response["choices"][0]["message"]["function_call"]
    #         completion_tokens = response["usage"]['completion_tokens']
    #         prompt_tokens = response["usage"]['prompt_tokens']
    #         await handle_token_use(userID, model, completion_tokens, prompt_tokens)


    except Exception as e:
        print(e)
        message = str(e)
        agent_name = 'system'

    # eZprint('response recieved')
    
    
    await  websocket.send(json.dumps({'event':'recieve_agent_state', 'payload':{'agent': agent_name, 'state': ''}, 'convoID': convoID}))

    asyncio.create_task(handle_message(convoID, message, 'assistant', agent_name, None, thread))

    # if function_call:
    #     asyncio.create_task(handle_message(convoID, function_call, 'assistant', agent_name, None, thread, meta = 'function_call'))


    # if len(chatlog[convoID]) == 4:
        

async def command_interface(command, convoID, threadRequested):
    #handles commands from user input
    print('running commands')
    # print('nova convo is ' + str(novaConvo))
    # await  websocket.send(json.dumps({'event':'recieve_agent_state', 'payload':{'agent': 'system', 'state': 'thinking'}}))

    command_response = None
    # def error_handler():
    #     logging.basicConfig(filename='errors.log', level=logging.ERROR)
    # try:
        # Your code here
    # command_parser = [
    #     handle_commands(command, convoID, threadRequested)
    # ]

    # command_response = await asyncio.gather(*command_parser)
    # await websocket.send(json.dumps({'event':'recieve_agent_state', 'payload':{'agent': 'system', 'state': ''}}))
    command_response = await handle_commands(command, convoID, threadRequested)

    # except Exception as e:
    #     error_handler()
    #     logging.error(str(e))
    #     await handle_message(convoID, e, 'user', 'terminal', None, 0, 'terminal')


    if not command_response:
        novaConvo[convoID]['command-loop']= False
        novaConvo[convoID]['steps-taken'] = 0
    # eZprint('command response recieved from command')
    # eZprint(command_response)
    
    thread = 0

    if command_response:
        #bit of a lazy hack to get it to match what the assistant parse takes
        name = ''
        status = ''
        message = ''
        speak = ''
        if 'name' in command_response:
            name = command_response['name']
        if 'status' in command_response:
            status = command_response['status']
        if 'message' in command_response:
            message = command_response['message']

        
        ##if return, it'll send back to user and end thread
        status_lower = status.lower()
        ## TODO : FINALISE THE THREAD ETC STRUCTURE< FOR NOW EVERYTHING STAYS ON MAIN AND IS GATED BY CHAT
        # if 'return' in status_lower or 'success' in status_lower or 'error' in status_lower:
            # print('success returned')
        return_string = 'system response : ' + name + ' - ' + status + ' : ' + message
        command_object = {'command':{
                "name" : name, 
                "status" : status, 
                "message" : message
                },
            }
    
        command_object = json.dumps(command_object)

        meta = 'terminal'
        # await  websocket.send(json.dumps({'event':'recieve_agent_state', 'payload':{'agent': 'system', 'state': ''}}))

        # await handle_message(convoID, return_string, 'user', 'terminal', None, 0, 'terminal')
        # return
  
        
        ##if there's not a new thread requested, it'll open a new one and return a message to the main thread
        if not threadRequested:
            print('no recognised return, so far in progress from command')
            if convoID not in system_threads:
                system_threads[convoID] = {}
            
            command_object = {'command':{
                    "name" : name, 
                    "status" : status, 
                    "message" : message,
                    }
                }
            
            # command_object = json.dumps(command_object)
            # await  websocket.send(json.dumps({'event':'recieve_agent_state', 'payload':{'agent': 'system', 'state': ''}}))

            await handle_message(convoID, message, 'function', name, None, 0, 'terminal')
        
        else:
            print('thread requested so same again but this time on a thread')
            thread = threadRequested
            command_object = {'system':{
                    "name" : name, 
                    "status" : status, 
                    "message" : message
                    },

                }
            
            command_object = json.dumps(command_object)

            # await  websocket.send(json.dumps({'event':'recieve_agent_state', 'payload':{'agent': 'system', 'state': ''}}))

            await handle_message(convoID, message, 'function', name, None, thread, 'terminal')

        await return_to_GPT(convoID, thread)
 

async def return_to_GPT(convoID, thread = 0):
    novaConvo[convoID]['command-loop'] = True
    if novaConvo[convoID].get('summarising'):
        return
    if 'steps-taken' not in novaConvo[convoID]:
        print('no steps taken')
        novaConvo[convoID]['steps-taken'] = 0

    if 'steps-allowed' not in novaConvo[convoID]:
        novaConvo[convoID]['steps-allowed'] = 3
    novaConvo[convoID]['steps-taken'] += 1 
    print(novaConvo[convoID]['steps-taken'])
    await construct_query(convoID, thread)
    model = 'gpt-3.5-turbo'
    if 'model' in novaConvo[convoID]:
        model = novaConvo[convoID]['model']
        print ('model: ' + model)

    
    query_object = []
    if 'prompt' in current_prompt[convoID]:
        query_object += current_prompt[convoID]['prompt']
    if 'chat' in current_prompt[convoID]:
        query_object += current_prompt[convoID]['chat']
    if 'emphasise' in current_prompt[convoID]:
        query_object += current_prompt[convoID]['emphasise']
    
    
    # if novaConvo[convoID].get('return_type', '') == 'openAI' and current_prompt[convoID].get('openAI_functions', None):
    #     query_object += current_prompt[convoID]['openAI_functions']


    print(query_object)
    if 'steps-taken' in novaConvo[convoID]:
        if ('user-interupt' not in novaConvo[convoID] or not novaConvo[convoID]['user-interupt']) and not novaConvo[convoID]['steps-taken'] >= novaConvo[convoID]['steps-allowed']:
            print('sending to GPT')
            functions = None
            if novaConvo[convoID].get('return_type', '') == 'openAI' and current_prompt[convoID].get('openAI_functions', None):
                functions = current_prompt[convoID]['openAI_functions']

            await send_to_GPT(convoID, query_object, thread, model, functions)
        else:
            await handle_message(convoID, 'maximum independent steps taken, awaiting user input', 'system', 'terminal', None, 0, 'terminal')
            novaConvo[convoID]['command-loop'] =  False
            novaConvo[convoID]['steps-taken'] = 0
            novaConvo[convoID]['user-interupt'] = False

        if 'user-interupt' in novaConvo[convoID]:
            novaConvo[convoID]['user-interupt'] = False
        
async def get_thread_summary(convoID, thread ):
    await construct_query(convoID, thread)
    to_summarise = ''
    content = ''
    if thread in system_threads[convoID]:
        for obj in system_threads[convoID][thread]:
            to_summarise += obj['role'] +": " + obj['body'] + '\n'

            query_object = [{"role": "user", "content": to_summarise}]
            query_object.append({"role": "user", "content": "Return concise summary of above contents."})
        try:

            response = await sendChat(query_object, "gpt-3.5-turbo")
            content = str(response["choices"][0]["message"]["content"])

        except Exception as e:
            print(e)
            print('trying again')
            try: 
                response = await sendChat(query_object, "gpt-3.5-turbo")
                content = str(response["choices"][0]["message"]["content"])

            except Exception as e:
                print(e)
                content = e
    return content


simple_agent_counter = {}
async def simple_agent_response(convoID):
    # eZprint('simple agent response')
    #wait 
    await asyncio.sleep(3)
    if convoID not in simple_agent_counter:
        simple_agent_counter[convoID] = {}
    if 'counter' not in simple_agent_counter[convoID]:
        simple_agent_counter[convoID]['counter'] = 0
    simple_agent_counter[convoID]['counter'] += 1

    if simple_agent_counter[convoID]['counter'] > 10:
        # simple_agent_counter[convoID]['counter'] = 0
        return
    
    # print('simple agentcounter is: ' + str(simple_agent_counter[convoID]['counter']))

    if convoID in simple_agents:

        for key, val in simple_agents[convoID].items():
            
            await  websocket.send(json.dumps({'event':'recieve_agent_state', 'payload':{'agent': str(val['label']), 'state': 'typing'}, 'convoID': convoID}))

            promptObject = {'role': "system", "content": val['label']+'\n'+val['prompt']}
            await construct_chat(convoID)
            simple_chat = []
            simple_chat.append(promptObject)
            simple_chat += deepcopy(current_prompt[convoID]['chat'])
            # print(simple_chat)
            for chat in simple_chat:
                if 'role' in chat:
                    if chat['role'] == 'assistant':
                        chat['role'] = 'user'
                        if 'content' in chat:
                            json_object = await parse_json_string(chat['content'])
                            if json_object != None:
                                response = await get_json_val(json_object, 'speak')
                                chat['content'] = str(response)
                            chat['content'] = str(chat['content'])

                    elif chat['role'] == 'user':
                        chat['role'] = 'assistant'
            try:
                # print('reconstructing the chat')
                # print('sending simpleChat')
                # print(simple_chat)
                response = await sendChat(simple_chat, 'gpt-3.5-turbo')
                content = str(response["choices"][0]["message"]["content"])

            except Exception as e:
                print(e)
                print('trying again')
                try: 
                    response = await sendChat(promptObject, 'gpt-3.5-turbo')
                    content = str(response["choices"][0]["message"]["content"])

                except Exception as e:
                    print(e)
                    content = e
            # await  websocket.send(json.dumps({'event':'agentState', 'payload':{'agent': val['label'], 'state': 'typing'}}))
            ##to do, make this an array so handling multiple agent states.
            sessionID = novaConvo[convoID]['sessionID']
            userID = novaSession[sessionID]['userID']
            completion_tokens = response["usage"]['completion_tokens']
            prompt_tokens = response["usage"]['prompt_tokens']
            await handle_token_use(userID, 'gpt-3.5-turbo', completion_tokens, prompt_tokens)
            await  websocket.send(json.dumps({'event':'recieve_agent_state', 'payload':{'agent': str(val['label']), 'state': ''}, 'convoID': convoID}))
            eZprint('response recieved')
            await handle_message(convoID, content, 'user', str(val['label']), None, 0, 'simple')
            await construct_query(convoID),
            query_object = current_prompt[convoID]['prompt'] + current_prompt[convoID]['chat']
            await send_to_GPT(convoID, query_object)


async def sendChat(promptObj, model, functions = None):
    loop = asyncio.get_event_loop()
    if functions:
        response = await loop.run_in_executor(None, lambda: openai.ChatCompletion.create(model=model,messages=promptObj, functions=functions))
    else:
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
            "key": messageObject['key'],
            "UserID": str(messageObject['userID']),
            "SessionID": str(messageObject['sessionID']),
            "name": str(messageObject['userName']),
            "timestamp": datetime.now(),
            "body": str(messageObject['body']),
        }
    )
    # print('message record is : ' + str(message))
    return message.id



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




async def get_json_val(json_object, key_requested):
 
    # eZprint('getting val ' + key_requested+ ' from json')
    for responseKey, responseVal in json_object.items():
        if responseVal is not None and not isinstance(responseVal, str) and not isinstance(responseVal, list):
            for key, val in responseVal.items():
                if key_requested == key:
                    return val
            if key_requested ==  responseKey:
                return responseVal
        if responseVal is not None and isinstance(responseVal, list):
            for item in responseVal:
                if isinstance(item, dict):
                    for key, val in item.items():
                        if key_requested == key:
                            return val
    return None 



async def parse_json_string(content):

    # eZprint('parsing json string')
    # print(content)
    json_object = None
    error = None
    try:
        json_object = json.loads(content, strict=False)
        return json_object

    except ValueError as e:
        # the string is not valid JSON, try to remove unwanted characters
        print(f"Error parsing JSON: {e}")
        # print(content)


##########################REMOVE BRACKETS

    if json_object == None:
        
        # print('clearing anything before and after brackets')
        start_index = content.find('{')
        end_index = content.rfind('}')
        json_data = content[start_index:end_index+1]
        # print(json_data)
    try: 
        json_object = json.loads(json_data, strict=False)
        return json_object
    
    except:
        print('ehh')

##########################MANUALLY REMOVE COMMA

    if json_object == None:
            # print('trying manual parsing')
            json_data = remove_commas_after_property(content)

    try: 
        json_object = json.loads(json_data, strict=False)
        return json_object
    
    except:
        print('ehh')

    return
##########################AUTOGPT
    if json_object == None:
            print('trying auto gpt correct func')
            json_data = correct_json(content)

    try: 
        json_object = json.loads(json_data)
        return json_object
    
    except ValueError as e:
        # the string is still not valid JSON, print the error message
        print(f"Error parsing JSON: {e}")
        
    if json_object == None:

        json_data = await JSON_Parse_request_to_GPT(content, error)
        # print(json_data)
    try: 

        json_object = json.loads(json_data)
        return json_object
    
    except ValueError as e:
        # the string is still not valid JSON, print the error message
        print(f"Error parsing JSON: {e}")
        error = e

    if json_object == None:
        json_data = await JSON_Parse_request_to_GPT(content, error)
    try: 
        json_object = json.loads(json_data)
        return json_object
    
    except ValueError as e:
        # the string is still not valid JSON, print the error message
        print(f"Error parsing JSON: {e}")
        print(content)
    # if json_object == None:
    #     print('trying to parse json with commas')
    #     json_string = re.sub(r',(?!.*})', r'', content)
    #     print(json_string)

    # try: 
    #     json_object = json.loads(json_string)
    #     return json_object
    
    # except ValueError as e:
    #     # the string is still not valid JSON, print the error message
    #     print(f"Error parsing JSON: {e}")
    
    return None

def remove_trailing_commas(broken_json):
    # Find all commas at the end of a line
    regex = re.compile(r',\s*([\]}])')
    # Replace them with just the matched bracket/brace
    return regex.sub(r'\g<1>', broken_json)

def remove_commas_after_property(content):
    counter = 0
    lastChar = ''
    removal_candidate = 0
    removal_candidates = []
    for char in content:
        # print(char + ' | ')
        if not removal_candidate:
            if char == ',' and lastChar == '"':
                # print('found char for removal')
                removal_candidate = counter
        elif removal_candidate :
            if (char == ',' or char == ' ' or char == '\n') and (lastChar == ',' or lastChar == ' ' or lastChar == '\n'):
                # print('current and last either apostrophe, space or enter')
                pass
            elif char == '}' and (lastChar == ' ' or lastChar == ','):
                # print('now on close bracked followed by either space or comma,')
                removal_candidates.append(removal_candidate)
            else:
                # print('not on a space followed by comma or a space so not a candidate')
                removal_candidate = 0
        counter += 1
        lastChar = char
    removal_candidates.reverse()
    for candidate in removal_candidates:
        content = content[:candidate] + content[candidate+1:]
    # print (content)
    return content






###fake user customer#
fake_user_prompt="""You are playing an interested customer visiting NOVA for the first time, and hoping to learn more about the product. You are not sure what to ask, but you are curious about the product and want to learn more.
"""
fake_user__system = """
Based on the above conversations and prompts from the NOVA agent, respond with a message that simulates a response from a potential customer.
"""

###fake user elderly person entering a session of reminiscence therapy###
fake_user_prompt_elderly="""You are an elderly person entering a session of reminiscence therapy. You want to explore old memories and will bring up cherished and painful memories when prompted. You are initially uncertain but become familiar and comfortable with the agent in later sessions."""

fake_user__system_elderly = """
Based on the above conversations, respond with a message that simulates a response from an elderly person entering a session of reminiscence therapy.
"""


async def JSON_Parse_request_to_GPT(content, e):
        # print('trying to send back to gpt')

        system = [{"role": "user", "content": "As a JSON parser, your mission is to clean and reformat JSON strings that have raised exceptions. You'll receive a JSON string as input that doesn't pass validation and can't be loaded with json.loads(). Your goal is to properly format it according to the example schema below so it can be loaded and parsed without errors. Make sure the final output is valid JSON.\n\n" + JSON_SCHEMA}]
                
        user =[{"role": "user", "content": content }]
        system =[{"role": "user", "content": f"Error parsing JSON: {e}" }]

        response = await sendChat(user+system, 'gpt-3.5-turbo')
        json_data = str(response["choices"][0]["message"]["content"])
        # print(json_data)
        return json_data

broken_json="""
{
    "thoughts": {
        "text": "Absolutely! Prompts and modes allow you to interact with Nova in different ways, expanding the creative potential of the interface. Prompts are questions or statements that encourage users to generate new ideas or explore different perspectives. For example, a prompt might ask you to describe an object from a new angle or to imagine a fictional character with a unique backstory. Modes are like different "settings" that change the output or functionality of the interface. For example, a "collage mode" might combine elements from different documents or images to create a new composition. There are many different prompts and modes available, each with unique benefits for the creative process.",
        "reasoning": "Explaining the benefits of prompts and modes can help to provide users with practical examples of how Nova can assist them in their creative endeavors. Additionally, demonstrating the versatility of these tools can encourage continued exploration of the interface.",
        "plan": "- explain some of the available prompts and modes, such as collage mode or character design prompts\n- provide examples of how these tools can be used to generate new ideas or break creative blocks\n- emphasize the potential for customization and personalization",
        "criticism": "I need to ensure that I am providing clear and concise explanations of these features, including concrete examples of how they can be used in creative work.",
        "speak": "Prompts and modes are tools that can help you explore new ideas and expand your creative potential with Nova. Prompts are questions or statements that encourage you to generate new content or explore different perspectives, while modes are like different "settings" that change the output or functionality of the interface. For example, in "collage mode," you can combine elements from different documents or images to create a new composition. Some prompts might ask you to describe an object from a new angle, while others might prompt you to imagine a character with a unique backstory. These tools can be especially helpful for breaking through creative blocks or generating new ideas. Additionally, because Nova is programmable, you can customize and personalize each prompt or mode to meet your specific creative needs." 
    },
    "command": {}
}
"""



# async def main() -> None:
#     # json = remove_trailing_commas(broken_json)
#     # await prisma.connect()
#     # eZprint('running main')
#     # await get_keywords()

# if __name__ == '__main__':
#     asyncio.run(main())

JSON_SCHEMA = """
{
    "command": {
        "name": "command name",
        "args": {
            "arg name": "value"
        }
    },
    "thoughts":
    {
        "text": "thought",
        "reasoning": "reasoning",
        "plan": "- short bulleted\n- list that conveys\n- long-term plan",
        "criticism": "constructive self-criticism",
        "speak": "thoughts summary to say to user"
    }
}
"""