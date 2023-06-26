import asyncio
import json
from debug import eZprint
from appHandler import app, websocket
from sessionHandler import available_cartridges, chatlog, novaConvo
from memory import get_sessions, summarise_percent
from commands import system_threads, command_loops
from query import sendChat
from datetime   import datetime
from cartridges import update_cartridge_field

current_prompt = {}
simple_agents = {}


async def construct_query(convoID, thread = 0):
    print('constructing query')
    cartridges = await unpack_cartridges(convoID)
    main_string = await construct_string(cartridges, convoID)
    await construct_objects(convoID, main_string, cartridges)
    await construct_chat(convoID, thread)
    truncuated = await handle_token_limit(convoID)
    if truncuated == True:
        print('truncuated')
        return await construct_query(convoID, thread)
    

async def unpack_cartridges(convoID):
    sorted_cartridges = await asyncio.to_thread(lambda: sorted(available_cartridges[convoID].values(), key=lambda x: x.get('position', float('inf'))))
    cartridge_contents = {} 
    simple_agents[convoID] = {}
    print('unpacking cartridges')
    print(sorted_cartridges)
    for cartVal in sorted_cartridges:
        if cartVal.get('enabled', True):
            if cartVal['type'] not in cartridge_contents:
                cartridge_contents[cartVal['type']] = {'string': '', 'values': []}
            if 'label' in cartVal:
                ##CREATING TITLE STRING, IMPORTANT TO DELINIATE FILES
                cartridge_contents[cartVal['type']]['string'] += "\n__________________________\n" + cartVal['label']
                if cartVal['type'] == 'note' or cartVal['type'] == 'index' or cartVal['type'] == 'summary':
                    if 'minimised' in cartVal and cartVal['minimised']:
                        cartridge_contents[cartVal['type']]['string'] += " | expand"
                    else:
                        cartridge_contents[cartVal['type']]['string'] += " | minimise"
                cartridge_contents[cartVal['type']]['string'] +=  "\n"
            if 'prompt' in cartVal:
                cartridge_contents[cartVal['type']]['string'] += cartVal['prompt'] + "\n \n"
            if 'blocks' in cartVal:
                if 'text' in cartVal:
                    cartridge_contents[cartVal['type']]['string'] += "\n"+ cartVal['text'] + "\n"
                #THINKING BLOCKS IS FOR STORED BUT NOT IN CONTEXT (BUT QUERIABLE)
                #THOUGH AT A CERTAIN POINT IT WOULD BE SAME ISSUE WITH NOTES, SO PROBABLY JUST NEED RULE FOR CERTAIN LENGTH
                if 'blocks' in cartVal:
                    if 'overview' in cartVal['blocks']:
                            cartridge_contents[cartVal['type']]['string'] += "\n"+ str(cartVal['blocks']['overview']) + "\n"
                    if 'summaries' in cartVal['blocks']:
                        cartridge_contents[cartVal['type']]['string'] += "\n__________________________\nSummaries available:\n"
                        for summary in cartVal['blocks']['summaries']:
                            for key, value in summary.items():
                                if 'title' in value:
                                    cartridge_contents[cartVal['type']]['string'] += "\n--"+ str(value['title']) 
                                    if 'minimised' in value:
                                        if value['minimised']:
                                            cartridge_contents[cartVal['type']]['string'] += " | expand"
                                        else:
                                            cartridge_contents[cartVal['type']]['string'] += " | expand"
                                    else:
                                        cartridge_contents[cartVal['type']]['string'] += " | expand"
                                    cartridge_contents[cartVal['type']]['string'] += "\n"

                        cartridge_contents[cartVal['type']]['string'] += "\n"
            if 'values' in cartVal:
                cartridge_contents[cartVal['type']]['values'].append(cartVal['values'])
            if cartVal['type'] == 'simple-agent':
                if convoID not in simple_agents:
                    simple_agents[convoID] = {}
                if 'enabled' in cartVal and cartVal['enabled'] == True:
                    simple_agents[convoID][cartVal['key']] = cartVal

    # print(cartridge_contents)
    return cartridge_contents


async def construct_string(prompt_objects, convoID):
    # print('constructing string')
    final_string = ''

    if 'prompt' in prompt_objects:
        final_string += prompt_objects['prompt']['string']
    final_string += "\n__________________________\nFiles available:\n"
    if 'note' in prompt_objects:
        final_string += prompt_objects['note']['string'] + "\n__________________________\n"
    if 'index' in prompt_objects:
        final_string += prompt_objects['index']['string']   + "\n__________________________\n"
    context = await construct_context(convoID)
    final_string += context
    if 'summary' in prompt_objects:
        final_string += prompt_objects['summary']['string'] + "\n__________________________\n"




    # print('final_string')
    print(f'{final_string}')
    return final_string

async def construct_chat(convoID, thread = 0):
    current_chat = []
    # print('constructing chat for thread ' + str(thread))
    if convoID in chatlog:
        for log in chatlog[convoID]:
            if 'muted' not in log or log['muted'] == False:
                if 'thread' in log and thread > 0:
                    if log['thread'] == thread:
                        # print('thread indicator found so breaking main chat')
                        break
                if log['role'] == 'user':
                    log['body'] = log['body']
                current_chat.append({"role": f"{log['role']}", "content": f"{log['body']}"})
                
    if convoID in system_threads:
        if thread in system_threads[convoID]:
            # print('constructing chat for thread ' + str(thread) )
            thread_system_preline = await get_system_preline_object()
            current_chat.append(thread_system_preline)
            if convoID in command_loops and thread in command_loops[convoID]:
                # print("Command loop found, appending last command only")
                last_command = system_threads[convoID][thread][-1]
                current_chat.append({"role": "system", "content":  f"{last_command['body']}"})
            else:
                for obj in system_threads[convoID][thread]:
                    # print('found log for this thread number')
                    current_chat.append({"role": "system", "content":  f"{obj['body']}"})

    if convoID not in current_prompt:
        current_prompt[convoID] = {}


    if 'command' in novaConvo[convoID]:
        # print('command found appending sys')
        if novaConvo[convoID]['command']:

            if thread == 0:
                current_chat.append(basic_system_endline)
                # print('thread is 0 so appending basic')
            else:
                current_chat.append(thread_system_endline)

    current_prompt[convoID]['chat'] = current_chat
    # print(current_chat)

async def construct_context(convoID):
    await get_sessions(convoID)
    session_string = f"""You are speaking with {novaConvo[convoID]['userName']}.\n"""
    session_string += f"""todays date is {datetime.now()}.\n"""
    if 'sessions' in novaConvo[convoID]:
        if novaConvo[convoID]['sessions'] > 0:
            session_string += "You have spoken " + str(novaConvo[convoID]['sessions']) + "times.\n"
    if 'first-date' in novaConvo[convoID]:
        session_string +=  "from " + novaConvo[convoID]['first-date'] + " to " + novaConvo[convoID]['last-date']

    return session_string


async def construct_objects(convoID, main_string = None, prompt_objects = None, thread = 0 ):
    list_to_send = []
    # print('main string is: ' + str(main_string))
    # print('chat objects are: ' + str(chat_objects))
    final_prompt_string = ''
    if main_string:
        final_prompt_string += "\n"+ main_string
    if 'system' in prompt_objects:
        if 'string' in prompt_objects['system']:
            final_prompt_string += "\n"+prompt_objects['system']['string']
        # if 'values' in prompt_objects['system']:
        #     for value in prompt_objects['system']['values']:
        #         if 'auto-summarise' in value:
        #             if value['auto-summarise'] == True:
        #                 print('auto summarise found')

        #         # if 'warn_token' in value:
        #         #     summary = value['warn_start'] + summary + value['warn_end']
        #         #     if summary:
        #         #         list_to_send.append({"role": "system", "content": f"{summary}"})
        #         #     if value['warn_token'] == True:
        #         #         warning = await get_token_warning(list_to_send, value['warn_trigger'], convoID)
        #         #         if warning:
        #         #             warning = value['warn_start'] + warning + value['warn_end']
        #         #             list_to_send.append({"role": "system", "content": f"{warning}"})
        #         if 'give_context' in value:
        #             if value['give_context'] == True:
        #                 final_prompt_string += "\n"+context
    if 'command' in prompt_objects:
        final_command_string = ''
        final_command_string += "\n"+prompt_objects['command']['string']

        # print('command found' + str(prompt_objects['command']))
        if 'label' in prompt_objects['command']:
            # print('command label found')
            # print(prompt_objects['commands']['label'])
            final_command_string +=  prompt_objects['command']['label'] + "\n"
        if 'prompt' in prompt_objects['command']:
            # print('command prompt found')
            # print(prompt_objects['commands']['prompt'])
            final_command_string +=  prompt_objects['command']['prompt']
        return_format = await construct_commands(prompt_objects['command'], thread)
        # print('return format is: ' + str(return_format))
        final_command_string += return_format
        # print('command string is: ' + str(final_command_string))
        final_prompt_string += "\n"+final_command_string
        novaConvo[convoID]['command'] = True

    # print('final prompt string is: ' + str(final_prompt_string))
    list_to_send.append({"role": "system", 'content': final_prompt_string})
    # print('list to send is: ' + str(list_to_send))
    if convoID not in current_prompt:
        current_prompt[convoID] = {}
    current_prompt[convoID]['prompt'] = list_to_send


async def construct_commands(command_object, thread = 0):
    # print('constructing commands')
    # print(command_object)
    response_format = {}
    response_format_before = ""
    response_format_after = ""
    command_string = ""

    if 'values' in command_object:
        for values in command_object['values']:
            # print('values found')
            # print(values)
            for value in values:
                # print('value found')
                # print(value)
                if 'format instructions' in value:
                    # print('instructions found')
                    # print(value['format instructions'])
                    for instruct in value['format instructions']:
                        # print('instruct found')
                        # print(instruct)
                        for key, val in instruct.items():
                            if key == 'before-format':
                                response_format_before += val
                            if key == 'after-format':
                                response_format_after += val + "\n"
                                
                if 'response types requested' in value:
                    # print('response found')
                    for response_type in value['response types requested']:
                        # print('types found')
                        typeKey = ""
                        typeVal = ""
                        # print(response_type)
                        for element in response_type:
                            for key, val in element.items():
                                # if thread == 0:
                                if key == 'type':
                                    # print('type found' + str(val))
                                    typeKey = val
                                if key == 'instruction':
                                    # print('instruction found'  + str(val))
                                    typeVal = val
                                # else:
                                #     if val == 'reason' or val == 'plan':
                                #         if key == 'type':
                                #             # print('type found' + str(val))
                                #             typeKey = val
                                #         if key == 'instruction':
                                #             # print('instruction found'  + str(val))
                                #             typeVal = val

                            response_format[typeKey] =typeVal
                if 'command' in value:
                    # print('commands found')
                    command_string = ""
                    counter = 0
                    # print(value['command'])
                    for command in value['command']:
                        command_line = ""
                        # print('command is ')
                        # print(command)
                        ##TODO DEFINITELY MAKE THIS RECURSIVE
                        for element in command:
                            # print('element is '  + str(element))
                            for key, value in element.items():
                                if key == 'name':
                                    command_line += str(counter) + ". " + value
                                if key == 'description':
                                    command_line += ": " + value
                                if isinstance(value, list):
                                    if key == 'args' and value != []:
                                        command_line += ", args: "
                                    # print('value is list' + str(value))
                                    for args in value:
                                        for elements in args:
                                            # print('sub element is ' + str(elements))
                                            for subKey, subVal in elements.items():
                                                if subKey == 'name':
                                                    command_line += subVal + ": "
                                                if subKey == 'example':
                                                    command_line += subVal + ", "
                                if key == 'active':
                                    # print('active is ' + str(value))
                                    if value == False:
                                        command_line = ""
                                        continue
                                    counter += 1
                            if command_line != "":
                                command_string += command_line + "\n"
                    
    # print(response_format)
    response_format = {
        "thoughts" :response_format,
        "command" : {"name": "command name", "args": {"arg name": "value"}},
    }
    formatted_response_format = json.dumps(response_format, indent=4)

    # print(command_string)
    format_instruction = response_format_before + formatted_response_format + response_format_after
    command_string_instruction = command_string

    final_return = command_string_instruction + format_instruction

    # print('final return is: ' + str(final_return))
    return final_return
    
                
    
async def handle_token_limit(convoID):
    print('handling token limit')
    truncuate = False
    prompt_too_long = await get_token_warning(current_prompt[convoID]['prompt'], .2, convoID, 'prompt')
    chat_too_long = await get_token_warning(current_prompt[convoID]['chat'], .7, convoID, 'chat')
    if chat_too_long: 
        await summarise_percent(convoID, .5)
        truncuate = True
    # if prompt_too_long:
    #     handle_prompt_context(convoID)
    #     truncuate = True
    return truncuate
        

async def handle_prompt_context(convoID):
    sorted_cartridges = await asyncio.to_thread(lambda: sorted(available_cartridges[convoID].values(), key=lambda x: x.get('position', float('inf'))))
    cartridge_contents = {} 
    simple_agents[convoID] = {}
    for cartVal in sorted_cartridges:
        if cartVal.get('enabled', True):
            if cartVal['type'] == 'note' or cartVal['type'] == 'summary' or cartVal['type'] == 'index':
                cartVal['minimised'] = True
                await update_cartridge_field(convoID, cartVal)
    

token_usage = {}

async def get_token_warning(string_to_check, limit, convoID, element = 'prompt'):
    print('checking token limit')
    if convoID not in token_usage:
        token_usage[convoID] = {}
    tokens = estimateTokenSize(str(string_to_check))
    limit = novaConvo[convoID]['token_limit'] * limit
    token_usage[convoID][element] = tokens


    print ('tokens are: ' + str(tokens) + ' limit is: ' + str(limit))
    payload = {'convoID':convoID, 'element':element, 'tokens':tokens, 'limit':limit}
    await  websocket.send(json.dumps({'event':'update_token_usage', 'payload':payload}))  

    ##get warning for total tokens
    total_tokens = 0
    for usage in token_usage[convoID]:
        total_tokens += token_usage[convoID][usage]
        
    if total_tokens > novaConvo[convoID]['token_limit']:
        payload = {'convoID':convoID, 'element':'combined', 'tokens':tokens, 'limit':limit}
        await  websocket.send(json.dumps({'event':'update_token_usage', 'payload':payload}))  

    if tokens > limit:
        return str(tokens) + " tokens used, " + str(limit) + " tokens remaining."
    else:
        return
        

async def getPromptEstimate(convoID):
    prompt_token_count = estimateTokenSize(str(current_prompt[convoID]['chat'])+ str(current_prompt[convoID]['prompt']))
    # print('prompt token count is: ' + str(prompt_token_count))
    return prompt_token_count

def estimateTokenSize(text):
    tokenCount =  text.count(' ') + 1
    return tokenCount


async def get_system_preline_object():
    
    thread_system_preline = {"role": "user", "content": "\n\n\n~~~~~~~~~~~NOVA TERMINAL ENGAGED~~~~~~~~~~~~~\n\n\n Additional commands:\n1." + return_command + "\n2." + next_command + "\n3." + quit_command + "\n\n\n "}
    return thread_system_preline




basic_system_endline = {"role": "user", "content": "Think about current instructions, resources and user response. Compose your answer and respond using the format specified above, including any commands:"}

thread_system_endline = {"role": "user", "content": "You have entered a terminal session. Think about current objectives, the system response, and return command using the format specified above:\n>_ "}



return_command =  """return: returns from thread with message for user, args: "message": "<message_string>,"""

next_command = """next: shows next page,"""

quit_command = """quit: quits thread,"""




# thread_system_PS2 = {"role": "user", "content": "You are currently in a thread and have recieved a response from the command system. You can issue more commands, take notes, or return with message: "}

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
