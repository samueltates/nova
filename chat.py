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
from prismaHandler import prisma
from prompt import construct_prompt, construct_chat_query, current_prompt
from query import sendChat
from commands import handle_commands    

agentName = 'nova'



async def initiate_conversation(convoID):
    
    if convoID not in chatlog:
        chatlog[convoID] = {}
    chatlog[convoID]['agent_name'] = agentName
    chatlog[convoID]['token_limit'] = 4000

    await construct_prompt(convoID),
    await construct_chat_query(convoID)
    query_object = current_prompt[convoID]['prompt'] + current_prompt[convoID]['chat']
    await send_to_GPT(convoID, query_object)

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

    # print(message, role, key)
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

    
    estimate = getPromptEstimate(convoID)
    chatlog[convoID]['prompt_estimate'] = estimate
    if estimate > chatlog[convoID]['token_limit']:
        print('prompt too big')

    chatlog[convoID].append(messageObject)
    asyncio.create_task(logMessage(messageObject))
    copiedMessage = deepcopy(messageObject)

    if( role != 'user'):
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
    # print(promptObject)
    await  websocket.send(json.dumps({'event':'agentState', 'payload':{'agent': agentName, 'state': 'typing'}}))
    response = await sendChat(promptObject, 'gpt-3.5-turbo')
    content = str(response["choices"][0]["message"]["content"])
    eZprint('response recieved')
    print(response)

    ##check if response string is able to be parsed as JSON or is just a  or string
    json_object = None
    parsed_reply = ''
    json_object = parse_json_string(content)
    await handle_message(convoID, content, 'assistant')

    if json_object != None:
        eZprint('response is JSON')
        command = await get_json_val(json_object, 'command')
        if command != None:
            eZprint('command found')
            command_response = await handle_commands(command, convoID)
            eZprint(command_response)
            if command_response:
                #bit of a lazy hack to get it to match what the assistant parse takes
                command_response.update({"speak" : "Command " + command_response['name'] + " returned " + command_response['status'] + " with message " + command_response['message']})
                command_object = {
                    "system": command_response,
                }
                command_object = json.dumps(command_object)
                await handle_message(convoID, command_object, 'system')
    await fake_user_input(convoID)
    

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
    prompt = ''
    if convoID not in chatlog:
        prompt = ''
    else:
        for message in chatlog[convoID]:
            prompt += message['body'] + '\n'
    prompt_token_count = estimateTokenSize(prompt)
    return prompt_token_count

async def get_json_val(json_object, key_requested):
 
    eZprint('getting val ' + key_requested+ ' from json')
    for responseKey, responseVal in json_object.items():
        if responseVal is not None and not isinstance(responseVal, str):
            for key, val in responseVal.items():
                if key_requested == key:
                    return val
            if key_requested ==  responseKey:
                return responseVal
            
    return None 



def parse_json_string(content):

    # eZprint('parsing json string')
    # print(content)
    json_object = None

    try:
        json_object = json.loads(content)
        return json_object

    except ValueError as e:
        # the string is not valid JSON, try to remove unwanted characters
        print(f"Error parsing JSON: {e}")
        print(content)

    if json_object == None:
        
        print('clearing anything before and after brackets')
        start_index = content.find('{')
        end_index = content.rfind('}')
        json_data = content[start_index:end_index+1]
        print(json_data)
    try: 
        json_object = json.loads(json_data)
        return json_object
    
    except ValueError as e:
        # the string is still not valid JSON, print the error message
        print(f"Error parsing JSON: {e}")

    if json_object == None:
        print('trying to parse json with commas')
        json_string = re.sub(r',(?!.*})', r'', content)
        print(json_string)

    try: 
        json_object = json.loads(json_string)
        return json_object
    
    except ValueError as e:
        # the string is still not valid JSON, print the error message
        print(f"Error parsing JSON: {e}")
    
    return None

def remove_trailing_commas(broken_json):
    # Find all commas at the end of a line
    regex = re.compile(r',\s*([\]}])')
    # Replace them with just the matched bracket/brace
    return regex.sub(r'\g<1>', broken_json)


async def fake_user_input(convoID):
    # await construct_prompt(convoID),
    await construct_chat_query(convoID, True)
    eZprint('fake user input triggered')
    key = secrets.token_bytes(4).hex()
    fake_user = [{"role": "system", "content": "You are playing an interested customer visiting NOVA for the first time, and hoping to learn more about the product. You are not sure what to ask, but you are curious about the product and want to learn more."}]
    fake_user_end = [{"role": "system", "content": "Based on the above conversations and prompts from the NOVA agent, respond with a message that simulates a response from a potential customer."}]
    query_object = fake_user + current_prompt[convoID]['chat']  + fake_user_end
    print(query_object)
    response = await sendChat(query_object, 'gpt-3.5-turbo')
    content = str(response["choices"][0]["message"]["content"])
    print(content)
    fake_session = {    
        "convoID": convoID,
        "body": content,
        "ID": key,
    }
    await user_input(fake_session)

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

