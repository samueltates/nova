import asyncio
import json
from datetime import datetime

from session.appHandler import app, websocket
from session.sessionHandler import active_cartridges, chatlog, novaConvo, current_loadout, novaSession, system_threads, command_loops
from core.cartridges import update_cartridge_field
from chat.query import sendChat
from tools.memory import get_sessions, summarise_percent
from tools.debug import eZprint

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
    print(convoID)
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
                cartridge_contents[cartVal['type']]['string'] += "\n-" + cartVal['label']
                if cartVal['type'] != 'prompt':
                    if cartVal.get('lastUpdated', None):
                        cartridge_contents[cartVal['type']]['string'] += ' | Last updated : ' + cartVal['lastUpdated']
                    if cartVal.get('summary', None):
                        cartridge_contents[cartVal['type']]['string'] += ' | Summary: ' + cartVal['summary']
                    if cartVal.get('text', None):
                        cartridge_contents[cartVal['type']]['string'] += '\n' + cartVal['text'][0:140] + ' ...\n'
                    if cartVal.get('blocks', None):
                        if cartVal['blocks'].get('overview', None):
                            cartridge_contents[cartVal['type']]['string'] += '\n' + cartVal['blocks']['overview'][0:140] + ' ...\n'
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
        system_string += "\n--Instructions--"
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
    current_chat = []
    # print('constructing chat for thread ' + str(thread))
    # eZprint('chatlog is ')
    # print(chatlog[convoID])
    if convoID in chatlog:
        for log in chatlog[convoID]:
            # eZprint('log is: ' + str(log))    
            if 'muted' not in log or log['muted'] == False:
                # if 'thread' in log and thread > 0:
                #     if log['thread'] == thread:
                #         # print('thread indicator found so breaking main chat')
                #         break
                # if log['role'] == 'user':
                #     log['body'] = log['body']if
                object = {}

                if 'role' not in log:
                    log['role'] = 'user'
                object.update({ "role":  log['role']})
                if 'body' in log:
                    object.update({"content": str(log['body'])})
                if log['role'] == 'assistant':
                    if log.get('content'):
                        object.update({'content': str(log['content']) })
                    if log.get('function_calls'):
                        object.update({'function_calls': log['function_calls'] })
                if 'userName' in log:
                    # removes all characters except alphanum
                    name = ''.join(e for e in log['userName'] if e.isalnum())
                    object.update({"name": name})

                current_chat.append(object)
                
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

    # if 'command' in novaConvo[convoID]:
    #     # print('command found appending sys')
    #     if novaConvo[convoID]['command']:

    #         if thread == 0:
    #             current_chat.append(basic_system_endline)
    #             # print('thread is 0 so appending basic')
    #         else:
    #             current_chat.append(thread_system_endline)

    current_prompt[convoID]['chat'] = current_chat
    # print(current_chat)

async def construct_context(convoID):
    # print('constructing context')
    # await get_sessions(convoID)
    sessionID = novaConvo[convoID]['sessionID']
    # print(novaConvo[convoID])
    if 'agent-name' not in novaConvo[convoID]:
        novaConvo[convoID]['agent-name'] = 'Nova'
    session_string = f"""Your name is {novaConvo[convoID]['agent-name']}.\n"""
    session_string += f"""You are speaking with {novaSession[sessionID]['userName']}.\n"""
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
    # print('main string is: ' + str(main_string))
    # print('chat objects are: ' + str(chat_objects))
    emphasise_string = ''
    final_prompt_string = ''
    give_context = False
    if system_string:
        final_prompt_string += system_string

    print(prompt_objects)
    if prompt_objects.get('openAI_functions', None):

        novaConvo[convoID]['return_type'] = 'openAI'
        for value in prompt_objects['openAI_functions']['values']:
            if value.get('functions',None):
                if convoID not in current_prompt:
                    current_prompt[convoID] = {}
                current_prompt[convoID]['openAI_functions'] = value['functions'][0]
                print(current_prompt[convoID]['openAI_functions'])

    if 'system' in prompt_objects:
        print('system found')
        print(prompt_objects['system']['values'])
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
                print(value['model'])
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

    if prompt_objects.get('command', None):
        print('command found')
        # print(prompt_objects['command']['values'])
        for value in prompt_objects['command']['values']:
            if 'openAI_functions' in value:
                # print(value)
                if value['openAI_functions'] == True:
                    novaConvo[convoID]['return_type'] = 'openAI'
                else:
                    novaConvo[convoID]['return_type'] = 'json-string'

            if 'steps-allowed' in value:
                novaConvo[convoID]['steps-allowed'] = int(value['steps-allowed'])
            elif 'steps-allowed' not in novaConvo[convoID]:
                novaConvo[convoID]['steps-allowed'] = 3
            
        
        # if novaConvo[convoID]['return_type'] == 'openAI':
        #     if convoID not in current_prompt:
        #         current_prompt[convoID] = {}
        #     openAI_functions = await construct_commands(prompt_objects['command'], 'openAI', thread)    
        #     print('openAI functions are: ' + str(openAI_functions))
        #     current_prompt[convoID]['openAI_functions'] = openAI_functions

        # else:

        final_command_string = ''
        final_command_string += "\n"+prompt_objects['command']['string']
        if 'emphasise' in prompt_objects['command']['values'] and prompt_objects['command']['values']['emphasise'] != '':
            emphasise_string += " " + prompt_objects['command']['values']['emphasise']
        # print('command found' + str(prompt_objects['command']))
        if 'label' in prompt_objects['command']:
            # print('command label found')
            # print(prompt_objects['commands']['label'])
            final_command_string +=  prompt_objects['command']['label'] + "\n"
        if 'prompt' in prompt_objects['command']:
            # print('command prompt found')
            # print(prompt_objects['commands']['prompt'])
            final_command_string +=  prompt_objects['command']['prompt']
        return_format = await construct_commands(prompt_objects['command'], 'json-string', thread)
        # print('return format is: ' + str(return_format))
        final_command_string += return_format
        # print('command string is: ' + str(final_command_string))
        final_prompt_string += "\n"+final_command_string

        novaConvo[convoID]['command'] = True
    else:
        novaConvo[convoID]['command'] = False
        emphasis_to_send.append({'role' : 'user', 'content': emphasise_string})
    # print('final prompt string is: ' + str(final_prompt_string))
    list_to_send.append({"role": "system", 'content': final_prompt_string})
    list_to_send.append({"role": "system", 'content': content_string})
    list_to_send.append({"role": "system", 'content': emphasise_string})

    # print('list to send is: ' + str(list_to_send))
    if convoID not in current_prompt:
        current_prompt[convoID] = {}
    current_prompt[convoID]['prompt'] = list_to_send
    current_prompt[convoID]['emphasise'] = emphasis_to_send
    

async def construct_commands(command_object, prompt_type = 'json-string', thread = 0):
    # print('constructing commands')
    # print(command_object)
    response_format = {}
    response_format_before = ""
    response_format_after = ""
    command_string = ""
    open_AI_functions = []

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

            # print(value['command'])


            for command in value['command']:
                command_line = ""
                openAI_function = {}
                # print('command is ')
                # print(command)
                ##TODO DEFINITELY MAKE THIS RECURSIVE
                for element in command:
                    # print('element is '  + str(element))
                    for key, value in element.items():
                        if key == 'name':
                            command_line += str(counter) + ". " + value
                            openAI_function['name'] = value
                        if key == 'description':
                            command_line += ": " + value
                            openAI_function['description'] = value

                        if isinstance(value, list):
                            if key == 'args' and value != []:
                                command_line += ", args: "
                                openAI_function['parameters'] = {}
                                openAI_function['parameters']['properties'] = {}
                                openAI_function['parameters']['type'] = 'object'
                            # print('value is list' + str(value))
                            for args in value:
                                for elements in args:
                                    # print('sub element is ' + str(elements))
                                    name = ""
                                    for subKey, subVal in elements.items():
                                        if subKey == 'name':

                                            command_line += subVal + ": "
                                            name = subVal
                                            openAI_function['parameters']['properties'][subVal] = {}
                                            
                                        if subKey == 'example':
                                            command_line += subVal + ", "
                                            if name in openAI_function['parameters']['properties']:
                                                openAI_function['parameters']['properties'][name]['type'] = subVal


                        if key == 'active':
                            # print('active is ' + str(value))
                            if value == False:
                                command_line = ""
                                continue
                            counter += 1
                if command_line != "":
                    command_string += command_line + "\n"
                if command_object != {}:
                    open_AI_functions.append(openAI_function)

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
    if prompt_type == 'json-string':
        return final_return
    elif prompt_type == 'openAI':
        return open_AI_functions
    
                
    
async def handle_token_limit(convoID):
    print('handling token limit')
    # print(novaConvo[convoID])
    await summarise_at_limit(current_prompt[convoID]['prompt'] + current_prompt[convoID]['emphasise'], .25, convoID, 'prompt')
    await summarise_at_limit(current_prompt[convoID]['chat'], .75, convoID, 'chat')
    # await summarise_at_limit(current_prompt[convoID]['emphasise'], .25, convoID, 'emphasise')
    # print (novaConvo[convoID]['auto-summarise'])
    if convoID in novaConvo and 'auto-summarise' in novaConvo[convoID] and novaConvo[convoID]['auto-summarise']:
        summarise_at = .8
        if 'summarise-at' in novaConvo[convoID]:
            summarise_at = novaConvo[convoID]['summarise-at']
        else:
            novaConvo[convoID]['summarise-at'] = .6
        prompt_too_long = await summarise_at_limit(current_prompt[convoID]['prompt'] + current_prompt[convoID]['chat'] + current_prompt[convoID]['emphasise'], summarise_at, convoID, 'combined')
        if prompt_too_long: 
            novaConvo[convoID]['summarising'] = True
            if convoID in chatlog:
                await summarise_percent(convoID, .5)
                novaConvo[convoID]['summarising'] = False
                await construct_chat(convoID,0)
                await summarise_at_limit(current_prompt[convoID]['prompt'] + current_prompt[convoID]['emphasise'], .25, convoID, 'prompt')
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
    print(novaConvo[convoID])
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
