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

current_prompt = {}
simple_agents = {}


async def construct_query(convoID, thread = 0):
    # print('constructing query')
    cartridges = await unpack_cartridges(convoID)
    system_string = await construct_system_string(cartridges, convoID)
    content_string = await construct_content_string(cartridges, convoID)
    await construct_objects(convoID, system_string,content_string, cartridges)
    await construct_chat(convoID, thread)
    await handle_token_limit(convoID)

async def unpack_cartridges(convoID):
    # print(convoID)
    sorted_cartridges = await asyncio.to_thread(lambda: sorted(active_cartridges[convoID].values(), key=lambda x: x.get('position', float('inf'))))
    cartridge_contents = {} 
    simple_agents[convoID] = {}
    # print('unpacking cartridges')
    # print(sorted_cartridges)
    for cartVal in sorted_cartridges:
        if cartVal.get('enabled', True):
            if cartVal['type'] not in cartridge_contents:
                cartridge_contents[cartVal['type']] = {'string': '', 'values': []}
            if 'label' in cartVal and cartVal['type'] != 'system' and cartVal['type'] != 'command':
                ##CREATING TITLE STRING, IMPORTANT TO DELINIATE FILES
                cartridge_contents[cartVal['type']]['string'] += "\n" + cartVal['label']
                if cartVal['type'] != 'prompt':
                    if cartVal.get('lastUpdated', None):
                        cartridge_contents[cartVal['type']]['string'] += ' | Last updated : ' + cartVal['lastUpdated']
                    if cartVal.get('summary', None):
                        cartridge_contents[cartVal['type']]['string'] += ' | Summary: ' + cartVal['summary']
                    if cartVal.get('text', None):
                        cartridge_contents[cartVal['type']]['string'] += '\n' + cartVal['text'][0:140] + ' ...\n'
                    # if cartVal.get('blocks', None):
                    #     if cartVal['blocks'].get('overview', None):
                            # cartridge_contents[cartVal['type']]['string'] += '\n' + cartVal['blocks']['overview'][0:140] + ' ...\n'
                        # if cartVal['type'] == 'note' or cartVal['type'] == 'index':
                        #     if 'minimised' in cartVal and cartVal['minimised']:
                        #         cartridge_contents[cartVal['type']]['string'] +="\n[STATE : CLOSED]\n"
                        #     else:
                        #         cartridge_contents[cartVal['type']]['string'] += "\n[STATE : OPEN]\n"
                        # if cartVal['type']=='summary' or cartVal['type']=='index':
                        #     cartridge_contents[cartVal['type']]['string'] += "\n[STATE : QUERIABLE] \n"
                        # cartridge_contents[cartVal['type']]['string'] +=  "\n"
            if 'prompt' in cartVal:
                cartridge_contents[cartVal['type']]['string'] += "\n"+cartVal['prompt'] + "\n"
            if 'blocks' in cartVal:
                if 'overview' in cartVal['blocks']:
                        cartridge_contents[cartVal['type']]['string'] += "\n"+ str(cartVal['blocks']['overview']) + "\n"
            # if 'minimised' in cartVal and cartVal['minimised'] == False:
            #     if 'text' in cartVal:
            #         cartridge_contents[cartVal['type']]['string'] += "\n"+cartVal['text'] + "\n--\n"
            #     if 'blocks' in cartVal:
            #         #THINKING BLOCKS IS FOR STORED BUT NOT IN CONTEXT (BUT QUERIABLE)
            #         #THOUGH AT A CERTAIN POINT IT WOULD BE SAME ISSUE WITH NOTES, SO PROBABLY JUST NEED RULE FOR CERTAIN LENGTH
            #         if 'blocks' in cartVal:
            #             if 'summaries' in cartVal['blocks']:
            #                 for summary in cartVal['blocks']['summaries']:
            #                     for key, value in summary.items():
            #                         if 'title' in value:
            #                             cartridge_contents[cartVal['type']]['string'] += "\n"+ str(value['title']) 
            #                             if 'timestamp' in value:
            #                                 cartridge_contents[cartVal['type']]['string'] += " - " + str(value['timestamp'])
            #                             if 'epoch' in value:
            #                                 cartridge_contents[cartVal['type']]['string'] += " - layer " + str(value['epoch'])
            #                             # if 'minimised' in value:
            #                             #     if value['minimised']:
            #                             #         cartridge_contents[cartVal['type']]['string'] += " [CLOSED]"
            #                             #     else:
            #                             #         cartridge_contents[cartVal['type']]['string'] += " [OPEN]"
            #                             #         # if 'body' in value:
            #                             #         #     cartridge_contents[cartVal['type']]['string'] += "\n"+ str(value['body']) + "\n"
            #                             # else:
            #                             #     cartridge_contents[cartVal['type']]['string'] += " [OPEN]"
            #                                 # if 'body' in value:
            #                                 #     cartridge_contents[cartVal['type']]['string'] += "\n"+ str(value['body']) + "\n"
            #                             cartridge_contents[cartVal['type']]['string'] += "\n"
            #             if 'queries' in cartVal['blocks']:
            #                 if 'minimised' in cartVal and not cartVal['minimised']:
            #                     if 'query' in cartVal['blocks']['queries']:
            #                         cartridge_contents[cartVal['type']]['string'] += "\n"+ str(cartVal['blocks']['queries']['query']) + " : "
            #                     if 'response' in cartVal['blocks']['queries']:
            #                         cartridge_contents[cartVal['type']]['string'] += str(cartVal['blocks']['queries']['response']) + "\n"
            #                     # cartridge_contents[cartVal['type']]['string'] +=  str(cartVal['blocks']['queries'])[0:500]
            if 'values' in cartVal:
                cartridge_contents[cartVal['type']]['values'] = cartVal['values']
            if cartVal['type'] == 'simple-agent':
                if convoID not in simple_agents:
                    simple_agents[convoID] = {}
                if 'enabled' in cartVal and cartVal['enabled'] == True:
                    simple_agents[convoID][cartVal['key']] = cartVal
                else:
                    simple_agents[convoID][cartVal['key']] = None

    # print(cartridge_contents)
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
        content_string += "\nEmbedded documents:"
        content_string += prompt_objects['index']['string'] 
        content_string += '\n[Embedded documents can be queried, or closed.]\n'
    if 'note' in prompt_objects:
        content_string += "\nNotes:"
        content_string += prompt_objects['note']['string']
        content_string += '\n[Notes can be written, appended, read, queried or closed.]\n'
    if 'media' in prompt_objects:
        content_string += "\nMedia:"
        content_string += prompt_objects['media']['string']
        content_string += '\n[Media can be opened, closed or queried.]\n'

    if 'dtx' in prompt_objects:
        content_string += "\nDigital twin schemas:"
        content_string += prompt_objects['dtx']['string']
        content_string += '\n[Dtx can be queried or closed.]\n'

    if content_string != '':
        content_string = "\n--Files available--"+content_string

    if 'summary' in prompt_objects:
        content_string += "\n--Past conversations--"
        content_string += prompt_objects['summary']['string'] 
        content_string += '\n[The summary can be queried or read for more detail.]\n'


        
    return content_string

async def construct_chat(convoID, thread = 0):
    eZprint_object_list(chatlog[convoID], ['CHAT', 'CONSTRUCT_CHAT'], line_break=True)
    current_chat = []
    if convoID in chatlog:
        for log in chatlog[convoID]:


            if 'muted' not in log or log['muted'] == False:
                object = {}
                if 'role' not in log:
                    log['role'] = 'user'
                object.update({ "role":  log['role']})
                if log.get('content'):
                    object.update({'content': f"""{str(log['content'])}""" })
                if log.get('function_call'):
                    if log['function_call'] != 'None':  
                        object.update({'function_call': log['function_call'] })
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
    session_string = f"""Your name is {novaConvo[convoID]['agent-name']}.\n"""
    session_string += f"""You are speaking with {novaSession[sessionID]['user_name']}.\n"""
    session_string += f"""Today's date is {datetime.now()}.\n"""
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
        
        novaConvo[convoID]['return_type'] = 'openAI'
        for value in prompt_objects['openAI_functions']['values']:
            if value.get('functions'):
                if convoID not in current_prompt:
                    current_prompt[convoID] = {}
                openAI_functions = value['functions'][0]

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


