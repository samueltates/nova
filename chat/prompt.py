import asyncio
import json
import os
from datetime import datetime

from session.appHandler import app, websocket
from session.sessionHandler import active_cartridges, chatlog, novaConvo, current_loadout, novaSession, system_threads, command_loops
from core.cartridges import update_cartridge_field
from chat.query import sendChat
from tools.memory import get_sessions, summarise_percent
from tools.debug import eZprint_object_list, eZprint, check_debug, eZprint_key_value_pairs, eZprint_anything
from chat.returnSchema import build_tree_str

current_prompt = {}
simple_agents = {}


async def construct_query(convoID, thread = 0):
    # print('constructing query')
    cartridges = await unpack_cartridges(convoID)
    system_string = await construct_system_string(cartridges, convoID)
    content_string = await construct_content_string(cartridges, convoID)
    await construct_objects(convoID, system_string,content_string, cartridges)
    await construct_chat(convoID, thread)
    # await handle_token_limit(convoID)

async def unpack_cartridges(convoID):
    
    # print(convoID)
    DEBUG_KEYS = ['CARTRIDGES', 'UNPACK_CARTRIDGES']

    sorted_cartridges = await asyncio.to_thread(lambda: sorted(active_cartridges[convoID].values(), key=lambda x: x.get('position', float('inf'))))
    cartridge_contents = {} 
    simple_agents[convoID] = {}
    eZprint('unpacking cartridges', DEBUG_KEYS, line_break=True)
    eZprint_anything(sorted_cartridges, DEBUG_KEYS)
    for cartVal in sorted_cartridges:
        if cartVal.get('enabled', True):
            if cartVal['type'] not in cartridge_contents:
                eZprint(f'creating {cartVal["type"]} cartridge', DEBUG_KEYS)
                cartridge_contents[cartVal['type']] = {'string': '', 'values': []}
            
            if cartVal.get('type', None) == 'prompt':
                if cartVal.get('label', None):
                    cartridge_contents[cartVal['type']]['string'] += "\n### " + cartVal['label'] + "\n"
            if 'prompt' in cartVal and cartVal['prompt'] != '':
                eZprint(f'adding to prompt object', DEBUG_KEYS)
                cartridge_contents[cartVal['type']]['string'] += "\n"+cartVal['prompt']
                
            if cartVal['type'] != 'system' and cartVal['type'] != 'command' and cartVal['type'] != 'prompt' and cartVal['type'] != 'summary':
                ##CREATING TITLE STRING, IMPORTANT TO DELINIATE FILES
                eZprint(f'adding label to {cartVal["type"]} cartridge', DEBUG_KEYS)
                if 'label' in cartVal :
                    cartridge_contents[cartVal['type']]['string'] += "\n- **" + cartVal['label'] + "**"
                if cartVal.get('lastUpdated', None):
                    cartridge_contents[cartVal['type']]['string'] += ' | _Last updated_: ' + cartVal['lastUpdated']
                key = ''
                if cartVal.get('key', None):
                    key = cartVal['key']
                cartridge_contents[cartVal['type']]['string'] += f" | [Read]({key}) | [Query]({key})" 
                if cartVal.get('summary', None):
                    cartridge_contents[cartVal['type']]['string'] += '\n    - Summary : ' + cartVal['summary']
                eZprint(f'string updated to read {cartridge_contents[cartVal["type"]]["string"]}', DEBUG_KEYS)

             
            if cartVal.get('json', None):
                eZprint(f'adding json to {cartVal["type"]} cartridge', DEBUG_KEYS)
                eZprint_anything(cartVal['json'], DEBUG_KEYS + ['JSON'])
                json_obj = json.loads(cartVal['json'], strict=False)
                if json_obj:
                    parsed_json = build_tree_str(json_obj)
                    eZprint(f'ingesting {parsed_json}', DEBUG_KEYS + ['JSON'])
                    cartridge_contents[cartVal['type']]['string'] += '\n' + parsed_json
                    eZprint(f'string updated to read {cartridge_contents[cartVal["type"]]["string"]}', DEBUG_KEYS)

        
            if 'blocks' in cartVal and 'summaries' in cartVal['blocks']:    
                for summary in cartVal['blocks']['summaries']:
                    for key, value in summary.items():
                        if 'title' in value:
                            cartridge_contents[cartVal['type']]['string'] += "\n- **" + str(value['title']) + "**"
                        
                        if 'timestamp' in value:
                            try:
                                timestamped = datetime.fromtimestamp(value['timestamp'])
                                cartridge_contents[cartVal['type']]['string'] += " | _Time Range_:" +  str(timestamped)
                            except:
                                eZprint('timestamp error', DEBUG_KEYS)                        
                                cartridge_contents[cartVal['type']]['string'] += " | _Time Range_:" +  str(value['timestamp'])
                        cartridge_contents[cartVal['type']]['string'] += f" | [Expand]({key}) | [Query]({key})" 
                        cartridge_contents[cartVal['type']]['string'] += "\n    - "
                        if 'epoch' in value:
                            cartridge_contents[cartVal['type']]['string'] += "Level : " + str(value['epoch'])
                        if 'keywords' in value:
                            cartridge_contents[cartVal['type']]['string'] += " | Keywords : " + str(value['keywords'])
                    # if 'queries' in cartVal['blocks']:
                    #     if 'minimised' in cartVal and not cartVal['minimised']:
                    #         if 'query' in cartVal['blocks']['queries']:
                    #             cartridge_contents[cartVal['type']]['string'] += "\n"+ str(cartVal['blocks']['queries']['query']) + " : "
                    #         if 'response' in cartVal['blocks']['queries']:
                    #             cartridge_contents[cartVal['type']]['string'] += str(cartVal['blocks']['queries']['response']) + "\n"
                            # cartridge_contents[cartVal['type']]['string'] +=  str(cartVal['blocks']['queries'])[0:500]
            if 'values' in cartVal:
                cartridge_contents[cartVal['type']]['values'] = cartVal['values']
            if cartVal['type'] == 'simple-agent':
                if convoID not in simple_agents:
                    simple_agents[convoID] = {}
                if 'enabled' in cartVal and cartVal['enabled'] == True:
                    simple_agents[convoID][cartVal['key']] = cartVal
                else:
                    simple_agents[convoID][cartVal['key']] = None

    eZprint_anything(cartridge_contents, DEBUG_KEYS + ['CARTRIDGE_CONTENTS'])
    return cartridge_contents


async def construct_system_string(prompt_objects, convoID):
    # print('constructing string')

    system_string = ''

    if 'prompt' in prompt_objects:    
        system_string += prompt_objects['prompt']['string']
    # if 'summary' in prompt_objects:
    #     final_string += "\n--Past conversations--"
    #     final_string += prompt_objects['summary']['string'] 
    #     final_string += '\n[Past conversations can be queried or read for more detail.]\n'
    # if 'index' in prompt_objects:
    #     final_string += "\n--Embedded documents--"
    #     final_string += prompt_objects['index']['string'] 
    #     final_string += '\n[Embedded documents can be queried, or closed.]\n'
    # if 'note' in prompt_objects:
    #     final_string += "\n--Notes--\n"
    #     final_string += prompt_objects['note']['string']
    #     final_string += '\n[Notes can be written, appended, read, quieried or closed.]\n'
    # if 'media' in prompt_objects:
    #     final_string += "\n--Media--"
    #     final_string += prompt_objects['media']['string']
    #     final_string += '\n[Media can be opened, closed or queried.]\n'
    return system_string


async def construct_content_string(prompt_objects, convoID):
    content_string = ''

    if 'index' in prompt_objects:
        content_string += '\n\n### Files\n_Files can be queried using natural language_ \n'
        content_string += prompt_objects['index']['string'] 
    if 'note' in prompt_objects:
        content_string += '\n\n### Notes\n _Notes can be written, appended, read, queried or closed_\n'
        content_string += prompt_objects['note']['string']
    if 'media' in prompt_objects:
        content_string += "\n### Media"
        content_string += '\n_Media can be analysed, closed or queried_'
        content_string += prompt_objects['media']['string']

    if 'dtx' in prompt_objects:
        content_string += "\n### Digital twin schemas"
        content_string += '\n_Dtx can be queried or closed_'
        content_string += prompt_objects['dtx']['string']

    if content_string != '':
        content_string = "\n***"+content_string

    if 'summary' in prompt_objects:
        content_string += "\n***\n"
        content_string += "\n### Recent Conversations"
        content_string += prompt_objects['summary']['string'] 

    return content_string

async def construct_chat(convoID, thread = 0):
    current_chat = []
    if convoID in chatlog:
        eZprint_object_list(chatlog[convoID], ['CHAT', 'CONSTRUCT_CHAT'], line_break=True)
        for log in chatlog[convoID]:
            if 'muted' not in log or log['muted'] == False:
                object = {}
                if 'role' not in log:
                    log['role'] = 'user'
                object.update({ "role":  log['role']})
                if log['role'] == 'system':
                    if log.get('contentType') == 'summary':
                        content_string = '### Conversation section\n'
                        if log.get('timestamp'):
                            content_string += f"""_Time range_: {str(log['timestamp'])}"""
                        if log.get('title'):
                            content_string += f"""### {log['title']}"""
                        if log.get('minimised') == False:
                            if log.get('body'):
                                content_string += f""" : {str(log['body'])}"""
                        object.update({'content': f"""{str(content_string)}""" })

                if log.get('content'):
                    if log['content'] != 'None':
                        object.update({'content': f"""{str(log['content'])}""" })
                    else:
                        object.update({'content': ''})
                else:
                    object.update({'content': ''})

                if log.get('function_call'):
                    if log['function_call'] != 'None':  
                        try :
                            function_json = json.loads(log['function_call'], strict=False)
                        except:
                            function_json = log['function_call']
                        
                        object.update({'function_call': function_json })
                        #     print('function call error')
                        #     print(log['function_call'])
                if log.get('role') == 'function':
                    object.update({"name": log['function_name']})
                current_chat.append(object)

    if convoID in system_threads:
        if thread in system_threads[convoID]:
            thread_system_preline = await get_system_preline_object()
            current_chat.append(thread_system_preline)
            if convoID in command_loops and thread in command_loops[convoID]:
                last_command = system_threads[convoID][thread][-1]
                current_chat.append({"role": "system", "content":  f"{last_command['body']}"})
            else:
                for obj in system_threads[convoID][thread]:
                    current_chat.append({"role": "system", "content":  f"{obj['body']}"})

    if convoID not in current_prompt:
        current_prompt[convoID] = {}
    current_prompt[convoID]['chat'] = current_chat

async def construct_context(convoID):
    # print('constructing context')
    # await get_sessions(convoID)
    sessionID = novaConvo[convoID]['sessionID']
    # print(novaConvo[convoID])
    if 'agent-name' not in novaConvo[convoID]:
        novaConvo[convoID]['agent-name'] = 'Nova'
    if 'user_name' not in novaSession[sessionID]:
        novaSession[sessionID]['user_name'] = 'User'
    session_string = f"""\n\n***\n\n### Important information\n"""
    session_string += f"""\n- **Your name**: {novaConvo[convoID]['agent-name']}"""
    session_string += f"""\n- **You are speaking with**: {novaSession[sessionID]['user_name']}"""
    session_string += f"""\n- **Today's date**: {datetime.now()}"""
    if 'sessions' in novaSession[sessionID]:
        if novaSession[sessionID]['sessions'] > 0:
            session_string += "You have spoken " + str(novaSession[sessionID]['sessions']) + "times.\n"
    if 'first-date' in novaSession[sessionID]:
        session_string +=  "from " + novaSession[sessionID]['first-date'] + " to " + novaSession[sessionID]['last-date']
    return session_string


async def construct_objects(convoID, system_string = None, content_string = None, prompt_objects = None, thread = 0 ):
    list_to_send = []
    emphasis_to_send = []
    openAI_functions = []

    emphasise_string = ''
    final_prompt_string = ''
    give_context = False

    if system_string:
        final_prompt_string += system_string

    # print(prompt_objects)
    if prompt_objects.get('openAI_functions', None):
        eZprint_anything(prompt_objects['openAI_functions'], ['FUNCTIONS', 'CONSTRUCT_OBJECTS'])
        
        novaConvo[convoID]['return_type'] = 'openAI'
        for value in prompt_objects['openAI_functions']['values']:
            if value.get('functions'):
                openAI_functions = value['functions'][0]
            if value.get('function_objects'):
                for fc in value['function_objects']:
                    eZprint_anything(fc, ['FUNCTIONS', 'CONSTRUCT_OBJECTS'])
                    if fc.get('enabled', False):
                        openAI_functions.append(fc['function'])

    # reset system values every time for loop so only applies values if cartridge present

    novaConvo[convoID]['auto-summarise'] = False
    novaConvo[convoID]['model'] = 'gpt-3.5-turbo'
    novaConvo[convoID]['token_limit'] = 4000
    novaConvo[convoID]['summarise-at'] = .75
    novaConvo[convoID]['scope'] = 'local'
    novaConvo[convoID]['command'] = False
    novaConvo[convoID]['steps-allowed'] = 3
    current_prompt[convoID] = {}    # clears prompt so if empty no holdovers

    if 'system' in prompt_objects:
        print('system found')
        # print(prompt_objects['system']['values'])
 
        # cycles through setting cartridge values and applies
        for value in prompt_objects['system']['values']:
            if 'system-starter' in value and value['system-starter']!= '':
                # print('starter found' + str(value['system-starter']))
                if convoID not in current_prompt or 'chat' not in current_prompt[convoID] or current_prompt[convoID]['chat'] == []:
                    emphasise_string += value['system-starter']
                    
            if 'emphasise' in value and value['emphasise'] != '':
                    emphasise_string += " " + value['emphasise']

            if 'auto-summarise' in value:
                # print(value)
                if value['auto-summarise'] == True:
                    # print('auto summarise found')
                    novaConvo[convoID]['auto-summarise'] = True
                if value['auto-summarise'] == False:
                    novaConvo[convoID]['auto-summarise'] = False

            if 'summarise-at' in value:
                # print(str(value['summarise-at']) + ' found')
                novaConvo[convoID]['summarise-at'] = float(value['summarise-at'])

            if 'agent-name' in value:
                novaConvo[convoID]['agent-name'] = value['agent-name']
            if 'give-context' in value:
                if value['give-context'] == True:
                    give_context = True

            if 'model' in value:
                # print(value['model'])
                novaConvo[convoID]['model'] = value['model']



                if novaConvo[convoID]['model'] == 'gpt-4':
                    novaConvo[convoID]['token_limit'] = 8000
                else:
                    novaConvo[convoID]['token_limit'] = 4000
            else:
                novaConvo[convoID]['model'] = 'gpt-3.5-turbo'
                novaConvo[convoID]['token_limit'] = 4000

            if 'scope' in value:
                novaConvo[convoID]['scope'] = value['scope']
                    
        if give_context:
            context = await construct_context(convoID)
            final_prompt_string += context

    # custom REaCT cartridge constructing prompt based on autoGPT model
    # sets to defaults so settings from command cartridge don't stick

    if prompt_objects.get('command', None): # gets settings related to running commands

        for value in prompt_objects['command']['values']:
            if 'steps-allowed' in value:
                novaConvo[convoID]['steps-allowed'] = int(value['steps-allowed'])
            elif 'steps-allowed' not in novaConvo[convoID]:
                novaConvo[convoID]['steps-allowed'] = 3
            
        final_command_string = ''
        final_command_string += "\n"+ prompt_objects['command']['string']

        # constructs prompt relating to command cartridge
        if 'emphasise' in prompt_objects['command']['values'] and prompt_objects['command']['values']['emphasise'] != '':
            emphasise_string += " " + prompt_objects['command']['values']['emphasise']

        if 'label' in prompt_objects['command']:
            final_command_string +=  prompt_objects['command']['label'] + "\n"

        if 'prompt' in prompt_objects['command']:
            final_command_string +=  prompt_objects['command']['prompt']

        # constructs command prompt string
        return_format = await construct_commands(prompt_objects['command'], 'json-string', thread)
        final_command_string += return_format
        final_prompt_string += "\n"+ final_command_string
        novaConvo[convoID]['command'] = True
    else:
        novaConvo[convoID]['command'] = False


    # turns all strings into objects, and adds to list to send
    

    final_system_string = ''
    if final_prompt_string != '':
        # list_to_send.append({"role": "system", 'content': final_prompt_string})
        final_system_string += final_prompt_string
    
    if content_string != '':    
        # list_to_send.append({"role": "user", 'content': content_string})
        final_system_string += content_string

    if final_system_string != '':
        list_to_send.append({"role": "system", 'content': final_system_string})

    if list_to_send != []:
        current_prompt[convoID]['prompt'] = list_to_send

    if openAI_functions != []:
        current_prompt[convoID]['openAI_functions'] = openAI_functions
    
    if emphasise_string != '':
        emphasis_to_send.append({'role' : 'user', 'content': emphasise_string})
        current_prompt[convoID]['emphasise'] = emphasis_to_send
    

async def construct_commands(command_object, prompt_type = 'json-string', thread = 0):

    response_format = {}
    response_format_before = ""
    response_format_after = ""
    command_string = ""

    for value in command_object['values']:
        if 'format instructions' in value:
            # print('instructions found')
            # print(value['format instructions'])
            for instruct in value['format instructions']:
                # print('instruct found')
                # print(instruct)
                for key, val in instruct.items():
                    if key == 'before-format':
                        if prompt_type == 'json-string':
                            response_format_before += val
                    if key == 'after-format':
                        if prompt_type == 'json-string':
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
                                    name = ""
                                    for subKey, subVal in elements.items():
                                        if subKey == 'name':

                                            command_line += subVal + ": "
                                            name = subVal                                            
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
    # print('handling token limit')
    # print(novaConvo[convoID])

    prompt_to_check = []

    if 'prompt' in current_prompt[convoID]:
        prompt_to_check += current_prompt[convoID]['prompt']
    if 'emphasise' in current_prompt[convoID]:
        prompt_to_check += current_prompt[convoID]['emphasise']

    await summarise_at_limit(prompt_to_check, .25, convoID, 'prompt')
    await summarise_at_limit(current_prompt[convoID]['chat'], .75, convoID, 'chat')
    # await summarise_at_limit(current_prompt[convoID]['emphasise'], .25, convoID, 'emphasise')
    # print (novaConvo[convoID]['auto-summarise'])
    if convoID in novaConvo and 'auto-summarise' in novaConvo[convoID] and novaConvo[convoID]['auto-summarise']:

        summarise_at = .8
        if 'summarise-at' in novaConvo[convoID]:
            summarise_at = novaConvo[convoID]['summarise-at']
        else:
            novaConvo[convoID]['summarise-at'] = .6
        prompt_too_long = await summarise_at_limit(prompt_to_check + current_prompt[convoID]['chat'], summarise_at, convoID, 'combined')
        if prompt_too_long and not novaConvo[convoID].get('summarising', False): 
            await  websocket.send(json.dumps({'event':'recieve_agent_state', 'payload':{'agent': 'system', 'state': 'summarising'}, 'convoID': convoID}))
            eZprint('summarising', ['SUMMARY', 'HANDLE_TOKEN_LIMIT'], line_break=True)
            novaConvo[convoID]['summarising'] = True
            if convoID in chatlog:
                try:
                    await summarise_percent(convoID, .5)    
                except:
                    print('summarise error')
                novaConvo[convoID]['summarising'] = False
                await construct_chat(convoID,0)
                await summarise_at_limit(prompt_to_check, .25, convoID, 'prompt')
                await summarise_at_limit(current_prompt[convoID]['chat'], .75, convoID, 'chat')
                await  websocket.send(json.dumps({'event':'recieve_agent_state', 'payload':{'agent': 'system', 'state': ''}, 'convoID': convoID}))



        

async def handle_prompt_context(convoID):
    sorted_cartridges = await asyncio.to_thread(lambda: sorted(active_cartridges[convoID].values(), key=lambda x: x.get('position', float('inf'))))
    cartridge_contents = {} 
    simple_agents[convoID] = {}
    for cartVal in sorted_cartridges:
        if cartVal.get('enabled', True):
            if cartVal['type'] == 'note' or cartVal['type'] == 'summary' or cartVal['type'] == 'index':
                cartVal['minimised'] = True
                input = {
                    'convoID':convoID,
                    'cartKey':cartVal['key'],
                    'fields':{
                        'minimised':True
                    }
                }
                loadout = current_loadout[convoID]
                await update_cartridge_field(input,loadout, True )
    

token_usage = {}

async def summarise_at_limit(string_to_check, limit, convoID, element = 'prompt'):
    # print('checking token limit')
    if convoID not in token_usage:
        token_usage[convoID] = {}
    tokens = estimateTokenSize(str(string_to_check))
    # print('nova convo')
    # print(novaConvo[convoID])
    # print(convoID)
    # print(novaConvo)
    if 'token_limit' not in novaConvo[convoID]:
        novaConvo[convoID]['token_limit'] = 4000
    limit = novaConvo[convoID]['token_limit'] * limit
    token_usage[convoID][element] = tokens

    # print ('tokens are: ' + str(tokens) + ' limit is: ' + str(limit))
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
    # print(text)
    tokenCount =  (len(text) / 4) + 1
    return tokenCount


async def get_system_preline_object():
    
    thread_system_preline = {"role": "user", "content": "\n\n\n~~~~~~~~~~~NOVA TERMINAL ENGAGED~~~~~~~~~~~~~\n\n\n Additional commands:\n1." + return_command + "\n2." + next_command + "\n3." + quit_command + "\n\n\n "}
    return thread_system_preline




basic_system_endline = {"role": "user", "content": "Think about current instructions, resources and user response. Compose your answer and respond using the format specified above, including any commands:"}

thread_system_endline = {"role": "user", "content": "You have entered a terminal session. Think about current objectives, the system response, and return command using the format specified above:\n>_ "}


return_command =  """return: returns from thread with message for user, args: "message": "<message_string>,"""

next_command = """next: shows next page,"""

quit_command = """quit: quits thread,"""

async def get_model_limit(modelID):

    if models.get(modelID, None):
        return models[modelID]['context_window']
    else:
        return 4096

models = {
    "gpt-4-1106-preview": {
        "description": "Latest GPT-4 model with improved features, not suited for production traffic.",
        "context_window": 128000,
        "training_data": "Up to Apr 2023",
        "category": "Language"
    },
    "gpt-4-vision-preview": {
        "description": "GPT-4 Turbo with vision abilities, not suited for production traffic.",
        "context_window": 128000,
        "training_data": "Up to Apr 2023",
        "category": "Multimodal"
    },
    "gpt-4": {
        "description": "Currently points to gpt-4-0613 with continuous upgrades.",
        "context_window": 8192,
        "training_data": "Up to Sep 2021",
        "category": "Language"
    },
    "gpt-4-32k": {
        "description": "Points to gpt-4-32k-0613 with continuous upgrades.",
        "context_window": 32768,
        "training_data": "Up to Sep 2021",
        "category": "Language"
    },
    "gpt-4-0613": {
        "description": "Snapshot of gpt-4 from June 13th 2023 with function calling support.",
        "context_window": 8192,
        "training_data": "Up to Sep 2021",
        "category": "Language"
    },
    "gpt-4-32k-0613": {
        "description": "Snapshot of gpt-4-32k from June 13th 2023 with function calling support.",
        "context_window": 32768,
        "training_data": "Up to Sep 2021",
        "category": "Language"
    },
    "gpt-3.5-turbo-1106": {
        "description": "Updated GPT 3.5 Turbo with improved features, not suited for legacy completions.",
        "context_window": 16385,
        "training_data": "Up to Sep 2021",
        "category": "Language"
    },
    "gpt-3.5-turbo": {
        "description": "Currently points to gpt-3.5-turbo-0613.",
        "context_window": 4096,
        "training_data": "Up to Sep 2021",
        "category": "Language"
    },
    "gpt-3.5-turbo-16k": {
        "description": "Currently points to gpt-3.5-turbo-0613.",
        "context_window": 16385,
        "training_data": "Up to Sep 2021",
        "category": "Language"
    },
    "text-davinci-003": {
        "description": "Legacy model better for language tasks than older models, to be deprecated.",
        "context_window": 4096,
        "training_data": "Up to Jun 2021",
        "category": "Language"
    },
    "text-davinci-002": {
        "description": "Legacy model trained with supervised fine-tuning, to be deprecated.",
        "context_window": 4096,
        "training_data": "Up to Jun 2021",
        "category": "Language"
    },
    "code-davinci-002": {
        "description": "Optimized for code-completion tasks, to be deprecated.",
        "context_window": 8001,
        "training_data": "Up to Jun 2021",
        "category": "Code"
    },
    "text-curie-001": {
        "description": "Very capable, faster, and lower cost than Davinci models.",
        "max_tokens": 2049,
        "training_data": "Up to Oct 2019",
        "category": "Language"
    },
    "text-babbage-001": {
        "description": "Good at straightforward tasks, very fast and lower cost.",
        "max_tokens": 2049,
        "training_data": "Up to Oct 2019",
        "category": "Language"
    },
    "text-ada-001": {
        "description": "Capable of simple tasks, usually fastest GPT-3 model at lowest cost.",
        "max_tokens": 2049,
        "training_data": "Up to Oct 2019",
        "category": "Language"
    },
    "davinci": {
        "description": "Most capable GPT-3 model for a variety of tasks with high quality.",
        "max_tokens": 2049,
        "training_data": "Up to Oct 2019",
        "category": "Language"
    },
    "curie": {
        "description": "Very capable GPT-3 model, faster and lower cost than Davinci.",
        "max_tokens": 2049,
        "training_data": "Up to Oct 2019",
        "category": "Language"
    },
    "babbage": {
        "description": "Capable of straightforward tasks very fast and lower cost.",
        "max_tokens": 2049,
        "training_data": "Up to Oct 2019",
        "category": "Language"
    },
    "ada": {
        "description": "Fastest GPT-3 model capable of simple tasks at lowest cost.",
        "max_tokens": 2049,
        "training_data": "Up to Oct 2019",
        "category": "Language"
    },
    "babbage-002": {
        "description": "Replacement for GPT-3 ada and babbage models.",
        "max_tokens": 16384,
        "training_data": "Up to Sep 2021",
        "category": "Language"
    },
    "davinci-002": {
        "description": "Replacement for GPT-3 curie and davinci models.",
        "max_tokens": 16384,
        "training_data": "Up to Sep 2021",
        "category": "Language"
    },
    "dall-e-3": {
        "description": "The latest DALL·E model creates realistic images and art from natural language descriptions.",
        "category": "Image Generation"
    },
    "dall-e-2": {
        "description": "Generates realistic images, edits existing images or creates variations at higher resolution.",
        "category": "Image Generation"
    },
    "tts-1": {
        "description": "Text-to-speech conversion optimized for real-time use.",
        "category": "Text-to-Speech"
    },
    "tts-1-hd": {
        "description": "Text-to-speech conversion optimized for quality.",
        "category": "Text-to-Speech"
    },
    "whisper-1": {
        "description": "General-purpose speech recognition with multilingual support for recognition, translation, and identification.",
        "category": "Speech Recognition"
    },
    "text-embedding-ada-002": {
        "description": "Numerical representation of text for measuring relatedness between texts.",
        "category": "Embeddings"
    },
    "text-moderation-latest": {
        "description": "Latest moderation model for content compliance with OpenAI's policies.",
        "max_tokens": 32768,
        "category": "Moderation"
    },
    "text-moderation-stable": {
        "description": "Stable moderation model for content compliance, slightly older than the latest.",
        "max_tokens": 32768,
        "category": "Moderation"
    }
}
