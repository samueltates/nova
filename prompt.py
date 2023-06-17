import asyncio
import json
from debug import eZprint
from sessionHandler import availableCartridges, chatlog, novaConvo
from memory import summarise_percent, get_sessions
from commands import system_threads
from query import sendChat

current_prompt = {}
simple_agents = {}


async def construct_query(convoID, thread = 0):
    print('constructing query')
    cartridges = await unpack_cartridges(convoID)
    print(cartridges)
    main_string = await construct_string(cartridges, convoID)
    print(main_string)

    await construct_chat(convoID, thread)
    await construct_objects(convoID, main_string, cartridges)

async def unpack_cartridges(convoID):
    print('unpacking cartridges')
    # print(convoID)
    # print(availableCartridges[convoID])
    sorted_cartridges = await asyncio.to_thread(lambda: sorted(availableCartridges[convoID].values(), key=lambda x: x.get('position', float('inf'))))
    ##IDEA - construct object out of type as field name, then loop to construct object
    cartridge_contents = {} 
    simple_agents[convoID] = {}

    for cartVal in sorted_cartridges:
        if cartVal.get('enabled', True):
            if cartVal['type'] not in cartridge_contents:
                cartridge_contents[cartVal['type']] = {'string': '', 'values': []}
            if 'label' in cartVal:
                cartridge_contents[cartVal['type']]['string'] += cartVal['label'] + "\n"
            if 'prompt' in cartVal:
                cartridge_contents[cartVal['type']]['string'] += cartVal['prompt'] + "\n"
            if 'blocks' in cartVal:
                for block in cartVal['blocks']:
                    for key, value in block.items():
                        # print(key, value)
                        cartridge_contents[cartVal['type']]['string'] += value + "\n"
            if 'values' in cartVal:
                cartridge_contents[cartVal['type']]['values'].append(cartVal['values'])
            if cartVal['type'] == 'simple-agent':
                if convoID not in simple_agents:
                    simple_agents[convoID] = {}
                simple_agents[convoID][cartVal['key']] = cartVal
    # print(cartridge_contents)
    return cartridge_contents


async def construct_string(prompt_objects, convoID):
    print('constructing string')
    final_string = ''

    if 'prompt' in prompt_objects:
        final_string += prompt_objects['prompt']['string']
    if 'note' in prompt_objects:
        final_string += prompt_objects['note']['string']
    if 'index' in prompt_objects:
        final_string += prompt_objects['index']['string']
    if 'summary' in prompt_objects:
        final_string += prompt_objects['summary']['string']

    # print(final_string)
    return final_string

async def construct_chat(convoID, thread = 0):
    current_chat = []
    print('constructing chat for thread ' + str(thread))
    if convoID in chatlog:
        for log in chatlog[convoID]:
            if 'muted' not in log or log['muted'] == False:
                current_chat.append({"role": f"{log['role']}", "content": f"{log['body']}"})
            if 'thread' in log:
                if log['thread'] == thread:
                    print('thread indicator found so breaking main chat')
                    continue
                    
    if convoID in system_threads:
        if thread in system_threads[convoID]:
            for obj in system_threads[convoID][thread]:
                print('found log for this thread number')
                current_chat.append({"role": "system", "content": f"{obj['body']}"})
    if convoID not in current_prompt:
        current_prompt[convoID] = {}
    current_prompt[convoID]['chat'] = current_chat
    print(current_chat)

async def construct_context(convoID):
    get_sessions(convoID)
    session_string = f"""You are speaking with {novaConvo[convoID]['userName']}.\n"""
    if 'sessions' in novaConvo[convoID]:
        if novaConvo[convoID]['sessions'] > 0:
            session_string += "You have spoken " + str(novaConvo[convoID]['sessions']) + "times.\n"
    if 'first-date' in novaConvo[convoID]:
        session_string +=  "from " + novaConvo[convoID]['first-date'] + " to " + novaConvo[convoID]['last-date']


async def construct_objects(convoID, main_string = None, prompt_objects = None,  chat_objects = None, ):
    list_to_send = []
    # print('main string is: ' + str(main_string))
    # print('chat objects are: ' + str(chat_objects))
    if main_string:
        list_to_send.append({"role" : "system", "content": main_string})
    if 'system' in prompt_objects:
        list_to_send.append({'role': "system", "content": f"{ prompt_objects['system']['string']}"})
        if 'values' in prompt_objects['system']:
            for value in prompt_objects['system']['values']:
                if 'warn_token' in value:
                    if value['warn_token'] == True:
                        warning = await get_token_warning(list_to_send, value['warn_trigger'], convoID)
                        if warning:
                            warning = value['warn_start'] + warning + value['warn_end']
                            list_to_send.append({"role": "system", "content": f"{warning}"})
                if 'give_context' in value:
                    if value['give_context'] == True:
                        context = construct_context(convoID)
                        list_to_send.append({"role": "system", 'content': context})
    if 'commands' in prompt_objects:
        command_string = await construct_commands(prompt_objects['commands'])
        list_to_send.append({"role": "system", 'content': command_string})
        novaConvo[convoID]['commands'] = True

    # print('list to send is: ' + str(list_to_send))
    if convoID not in current_prompt:
        current_prompt[convoID] = {}
    current_prompt[convoID]['prompt'] = list_to_send
    

async def construct_commands(command_object):

    response_format = {}
    response_format_before = ""
    response_format_after = ""
    command_string = ""

    if 'values' in command_object:
        for value in command_object['values']:
            if 'instructions' in value:
                # print('instructions found')
                # print(value['instructions'])
                if 'before-format' in value['instructions']:
                    response_format_before += value['instructions']['before-format']
                if 'after-format' in value['instructions']:
                    response_format_after += value['instructions']['after-format']+ "\n"
                    
            if 'responses' in value:
                # print('response found')
                for key, val in value['responses'].items():
                    # print(key, val)
                    response_format[key] = val
            if 'commands' in value:
                # print('commands found')
                command_string = ""
                counter = 0
                for key, value in value['commands'].items():
                    if 'active' in value:
                        if value['active'] == True:
                            command_string += "\n"+ str(counter) +"."
                            command_string += key + ": " + value['description']
                            if 'args' in value:
                                for key, val in value['args'].items():
                                    command_string += " " + key + ": " + val
                            counter += 1
                            command_string += "\n"
                    
    # print(response_format)
    response_format = {
        "thoughts" :response_format,
        "commands" : {"name": "command name", "args": {"arg name": "value"}},
    }
    formatted_response_format = json.dumps(response_format, indent=4)

    format_instruction = response_format_before + formatted_response_format + response_format_after
    command_string_instruction = command_string

    final_return = command_string_instruction + format_instruction

    return final_return
    
                
    
            

                 

async def get_token_warning(string_to_check, limit, convoID):
    tokens = estimateTokenSize(str(string_to_check))
    limit = novaConvo[convoID]['token_limit'] * limit
    if tokens > limit:
        return tokens + " tokens used, " + limit + " tokens remaining."
    else:
        return
        

async def getPromptEstimate(convoID):
    prompt_token_count = estimateTokenSize(str(current_prompt[convoID]['chat'])+ str(current_prompt[convoID]['prompt']))
    print('prompt token count is: ' + str(prompt_token_count))
    return prompt_token_count

def estimateTokenSize(text):
    tokenCount =  text.count(' ') + 1
    return tokenCount




# response_format = {
#     "thoughts": {
#         "think" : "internal world",
#         "reason": "logic and flow",
#         "critique": "challenge and unpack",
#         "plan": "what comes next",
#         "answer": "say out loud"
#     },
#     "command": {"name": "command name", "args": {"arg name": "value"}},
# }
    
# formatted_response_format = json.dumps(response_format, indent=4)
# response = """You response should be entirely contained in JSON format as described below \nResponse"""
# format = f" Format: \n{formatted_response_format} \nEnsure the response can be" 
# python = """parsed by Python json.loads and passes a JSON schema validator."""

# final_format = response + format + python

# contraints = """\n\n\nConstraints:\n1. ~4000 word limit for short term memory. Your short term memory is short, so immediately save important information to files.\n2. If you are unsure how you previously did something or want to recall past events, thinking about similar events will help you remember.\n3. No user assistance, you are to complete all commands\n4. Exclusively use the commands listed below e.g. command_name\n\nCommands:\n"""

# create_note = """\n1. create_note: Create Note , args: "label": "<label_string>", "body": "<body_string>"\n"""
# append_note = """\n2. append_note: Append Note, args: "label": "<filename>", "line" : "<new_line>"\n """
# list_files = """\n3. list_files: List available files that aren't open, args: "type": "<resource type>"\n"""
# open_note = """\n4. open_note: Open a note, args: "label": "<labelname>"\n"""
# close_note = """\n5. close_note: Close a note, args: "label": "<labelname>"\n"""

# list_documents = """\n6. list_documents: List document embeddings, args: "document": "<filename>", "text": "<text>"\n"""
# query_document = """\n7. query_document: Query document embedding, args: "document": "<filename>", "query": "<text>"\n"""

# summarise_conversation = """\n8. summarise_conversation: Summarise section of chat, args: "start-line" : <int>, "end-line": <int>,  "notes" "<text>"\n"""

# search_summaries = """\n9. search_summaries: Use keyword or title to search conversation summaries, args: "query" : <text>, "notes" <text>"\n"""

# create_prompt = """\n10. create_prompt: Create new prompt for yourself, args: "prompt-text" : <text>, "prompt-title" : "<text>", "start-enabled" : "<bool>"\n"""
# enable_prompt = """\n11. enable_prompt: Enable prompt, args: "prompt-title" : "<text>"\n"""
# disable_prompt = """\n12. disable_prompt: Disable prompt, args: "prompt-title" : "<text>"\n"""

# Directions = """\n\nResources:\n1. Document deep query using embedded vector archive. \n2. Note creation and recall \n3. long Term memory management.\n\nPerformance Evaluation:\n1. Continuously review and analyze your actions to ensure you are performing to the best of your abilities.\n2. Constructively self-criticize your big-picture behavior constantly.\n3. Reflect on past decisions and strategies to refine your approach.\n4. Every command has a cost, so be smart and efficient. Aim to complete tasks in the least number of steps.\n5. Write all code to a file.
# """

# format = """\n\nYou should only respond in JSON format as described below \nResponse Format: \n{\n    "thoughts": {\n        "text": "thought",\n        "reasoning": "reasoning",\n        "plan": "- short bulleted\\n- list that conveys\\n- long-term plan",\n        "criticism": "constructive self-criticism",\n        "speak": "thoughts summary to say to user"\n    },\n    "command": {\n        "name": "command name",\n        "args": {\n            "arg name": "value"\n        }\n    }\n} \nEnsure the response can be parsed by Python json.loads"""

# glossary = """\n\nCommand Instructions:\nWhen you see see information worth preserving you will create a note, or append content to an existing one. \nYou will list files to find answers or existing notes that might be relavent. \nYou will be able to create new behaviours for yourself by creating a prompt, and triggering them by enabling or disabling. \nYou will manage your memory by closing unneeded notes, disabling uneeded prompts and summarising sections of the conversations. \nThe user will not use these commands and you will not mention them, they will be used by you to achieve your goals.\n"""

# command_string = contraints + final_format + create_note + append_note + list_files + open_note + close_note + list_documents + query_document + summarise_conversation + search_summaries + create_prompt + enable_prompt + disable_prompt 
