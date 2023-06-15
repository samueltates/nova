from datetime import datetime
import json
import asyncio
import re
import secrets
import openai
from copy import deepcopy

from debug import eZprint
from appHandler import websocket
from sessionHandler import novaConvo, chatlog, availableCartridges
from loadout import current_loadout
from prismaHandler import prisma
from prompt import construct_query, current_prompt
from query import sendChat
from commands import handle_commands, system_threads
from memory import get_sessions
from jsonfixes import correct_json
agentName = 'nova'


async def agent_initiate_convo(convoID):
    query_object = await construct_query(convoID),
    await send_to_GPT(convoID, query_object)


async def user_input(sessionData):
    #takes user iput and runs message cycle
    print('user input')
    convoID = sessionData['convoID']
    message = sessionData['body']
    userName = novaConvo[convoID]['userName']

    # print(availableCartridges[convoID])
    await handle_message(convoID, message, 'user', userName, sessionData['ID'])
    await construct_query(convoID),
    query_object = current_prompt[convoID]['prompt'] + current_prompt[convoID]['chat']
    if 'commands' in novaConvo[convoID]:
        if novaConvo[convoID]['commands']:
            query_object.append({"role": "user", "content": "Think about current instructions, resources and user response. Compose your answer and respond using the format specified above, including any commands:"})
    await send_to_GPT(convoID, query_object)
    

async def handle_message(convoID, message, role = 'user', userName ='', key = None, thread = 0):
    print('handling message')
    #handles input from any source, adding to logs and records 
    # TODO: UPDATE SO THAT IF ITS TOO BIG IT SPLITS AND SUMMARISES OR SOMETHING
    userID = novaConvo[convoID]['userID']
    sessionID = novaConvo[convoID]['sessionID'] +"-"+convoID
    if 'commands' in novaConvo[convoID]:
        json_return = novaConvo[convoID]['commands']
    else:
        json_return = False

    if convoID in current_loadout:
        sessionID += "-"+str(current_loadout[convoID])

    if key == None:
        key = secrets.token_bytes(4).hex()
    if convoID not in chatlog:
        chatlog[convoID] = []
    order = await getNextOrder(convoID)
    
    messageObject = {
        "sessionID": sessionID,
        "ID": key, ##actually sending what is stored as key
        "userName": userName,
        "userID": str(userID),
        "body": message,
        "role": role,
        "timestamp": str(datetime.now()),
        "order": order,
    }

    if thread:
        ##TODO : command returns can give those deeper functions, and include 'close' to close loop
        ##TODO : heck it could even be an array of loops, should get / build events for this
        ##TODO : Clear these threads when done 
        if convoID not in system_threads:
            system_threads[convoID] = {}
            if thread not in system_threads[convoID]:
                ##first log in thread updates chatlog with injected thread (to keep system thread referring to that)
                system_threads[convoID][thread] = []
                messageObject.update({'thread':thread})
                chatlog[convoID].append(messageObject)
            else:
                ##after that each loop it adds to thread 
                ##may be that it needs to bring in updates every so often, but I think just 'waiting for result' on main, and then 'finished or updated' and that can be driven by config
                system_threads[convoID][thread].append(messageObject)
    else:     
        chatlog[convoID].append(messageObject)

    asyncio.create_task(logMessage(messageObject))
    copiedMessage = deepcopy(messageObject)
    print(copiedMessage)
    if role != 'user' :
        ## if its expecting JSON return it'll parse, otherwise keep it normal
        if json_return:
            json_object = await parse_json_string(message)
            if json_object != None:
                copiedMessage = deepcopy(messageObject)
                response = await get_json_val(json_object, 'speak')
                command = await get_json_val(json_object, 'command')
                
                ##then if there's a response it sends it... wait no this is handling the agent response? so its handling everything, but if the agent responds with the thread no it'll parse that way, or just stay 
                ##basically thinking 'thread requested' so if the message is coming from a specific thread then it'll use / keep to that, otherwise it'll start a new one, using zero as false in this instance.

                await command_interface(command, convoID, thread)
                copiedMessage['body'] = response
        print(copiedMessage)

        asyncio.create_task(websocket.send(json.dumps({'event':'sendResponse', 'payload':copiedMessage})))
        
    # eZprint('MESSAGE LINE ' + str(len(chatlog[convoID])) + ' : ' + copiedMessage['body'])    
    await  websocket.send(json.dumps({'event':'agentState', 'payload':{'agent': agentName, 'state': ''}}))


async def send_to_GPT(convoID, promptObject, thread = 0):
    
    ## sends prompt object to GPT and handles response
    eZprint('sending to GPT')
    print(promptObject)

    content = ''
    await  websocket.send(json.dumps({'event':'agentState', 'payload':{'agent': agentName, 'state': 'typing'}}))
    try:
        response = await sendChat(promptObject, 'gpt-3.5-turbo')
        content = str(response["choices"][0]["message"]["content"])
        print(response)
    except Exception as e:
        print(e)
        print('trying again')
        try: 
            response = await sendChat(promptObject, 'gpt-3.5-turbo')
            content = str(response["choices"][0]["message"]["content"])

        except Exception as e:
            print(e)
            content = e
    eZprint('response recieved')

    asyncio.create_task(handle_message(convoID, content, 'assistant', 'Nova', None, thread))
        
            

async def command_interface(command, convoID, threadRequested):
    #handles commands from user input
    command_response = await handle_commands(command, convoID)
    eZprint(command_response)
    if command_response:
        #bit of a lazy hack to get it to match what the assistant parse takes
        command_response.update({"speak" : "Command " + command_response['name'] + " returned " + command_response['status'] + " with message " + command_response['message']})
        command_object = {
            "system": command_response,
        }
        ## get command as understood
        command_object = json.dumps(command_object)
        asyncio.create_task(handle_message(convoID, command_object, 'system'))
        
        ## gets return
        system_response = await handle_commands(command_object, convoID)

        ##if no specific thread requested, it'll make a new one, otherwise stick to current.
        if not threadRequested:
            thread = len(system_threads) +1
        else:
            thread = threadRequested

        await handle_message(convoID, system_response, 'system', 'sys', None, thread)

        ##sends back - will this make an infinite loop? I don't think so
        ##TODO : Handle the structure of the query, so eg take only certain amount, or add / abstract the goal and check against it.

        query_object = await construct_query(convoID, thread),
        await send_to_GPT(convoID, query_object, thread)





async def sendChat(promptObj, model):
    loop = asyncio.get_event_loop()
    response = await loop.run_in_executor(None, lambda: openai.ChatCompletion.create(model=model,messages=promptObj))
    return response


async def logMessage(messageObject):
    # print('logging message')

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
            "key": messageObject['ID'],
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




async def get_json_val(json_object, key_requested):
 
    # eZprint('getting val ' + key_requested+ ' from json')
    for responseKey, responseVal in json_object.items():
        if responseVal is not None and not isinstance(responseVal, str):
            for key, val in responseVal.items():
                if key_requested == key:
                    return val
            if key_requested ==  responseKey:
                return responseVal
    return None 



async def parse_json_string(content):

    # eZprint('parsing json string')
    # print(content)
    json_object = None
    error = None
    try:
        json_object = json.loads(content)
        return json_object

    except ValueError as e:
        # the string is not valid JSON, try to remove unwanted characters
        print(f"Error parsing JSON: {e}")
        print(content)


##########################REMOVE BRACKETS

    if json_object == None:
        
        print('clearing anything before and after brackets')
        start_index = content.find('{')
        end_index = content.rfind('}')
        json_data = content[start_index:end_index+1]
        # print(json_data)
    try: 
        json_object = json.loads(json_data)
        return json_object
    
    except ValueError as e:
        # the string is still not valid JSON, print the error message
        print(f"Error parsing JSON: {e}")
        error = e

##########################MANUALLY REMOVE COMMA

    if json_object == None:
            print('trying manual parsing')
            json_data = remove_commas_after_property(content)

    try: 
        json_object = json.loads(json_data)
        return json_object
    
    except ValueError as e:
        # the string is still not valid JSON, print the error message
        print(f"Error parsing JSON: {e}")
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
                print('found char for removal')
                removal_candidate = counter
        elif removal_candidate :
            if (char == ',' or char == ' ' or char == '\n') and (lastChar == ',' or lastChar == ' ' or lastChar == '\n'):
                print('current and last either apostrophe, space or enter')
                pass
            elif char == '}' and (lastChar == ' ' or lastChar == ','):
                print('now on close bracked followed by either space or comma,')
                removal_candidates.append(removal_candidate)
            else:
                print('not on a space followed by comma or a space so not a candidate')
                removal_candidate = 0
        counter += 1
        lastChar = char
    removal_candidates.reverse()
    for candidate in removal_candidates:
        content = content[:candidate] + content[candidate+1:]
    print (content)
    return content




async def fake_user_input(convoID, query):
    # await construct_prompt(convoID),
    eZprint('fake user input triggered')
    key = secrets.token_bytes(4).hex()
    await construct_chat_query(convoID, True)
    prompt = "Your name is " + novaConvo[convoID]['userName'] + ". " + fake_user_prompt_elderly
    fake_agent = [{"role": "system", "content": prompt}]
    fake_user_query = [{"role": "user", "content": query}]
    fake_agent_end = [{"role": "system", "content": fake_user__system_elderly}]
    query_object = fake_agent + fake_user_query  + fake_agent_end
    # print(query_object)
    print(query_object)
    try:
        response = await sendChat(query_object, 'gpt-3.5-turbo')
        content = str(response["choices"][0]["message"]["content"])
    except Exception as e:
        print(e)
        print('trying again')
        try: 
            response = await sendChat(query_object, 'gpt-3.5-turbo')
            content = str(response["choices"][0]["message"]["content"])

        except Exception as e:
            print(e)
            content = e
        
    # print(content)
    fake_session = {    
        "convoID": convoID,
        "body": content,
        "ID": key,


    }
    await user_input(fake_session, fake = True)


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
        print('trying to send back to gpt')

        system = [{"role": "user", "content": "As a JSON parser, your mission is to clean and reformat JSON strings that have raised exceptions. You'll receive a JSON string as input that doesn't pass validation and can't be loaded with json.loads(). Your goal is to properly format it according to the example schema below so it can be loaded and parsed without errors. Make sure the final output is valid JSON.\n\n" + JSON_SCHEMA}]
                
        user =[{"role": "user", "content": content }]
        system =[{"role": "user", "content": f"Error parsing JSON: {e}" }]

        response = await sendChat(user+system, 'gpt-3.5-turbo')
        json_data = str(response["choices"][0]["message"]["content"])
        print(json_data)
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