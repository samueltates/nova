import asyncio
import json
from debug import eZprint
from sessionHandler import availableCartridges, chatlog

current_prompt = {}



async def construct_prompt(convoID):
    eZprint('constructing chat prompt')
    prompt_string = ''
    keywords_available = []
    documents_available = []


    #TODO - abstract to prompt build / chat build + estimate, to be called on inputs / updates (combine with estimate)
    
    # Fetch the sorted cartridges asynchronously
    sorted_cartridges = await asyncio.to_thread(lambda: sorted(availableCartridges[convoID].values(), key=lambda x: x.get('position', float('inf'))))
    

    # Use a priority queue to store the prompt cartridges
    for cartVal in sorted_cartridges:
        if cartVal.get('enabled', True):
            if cartVal['type'] == 'prompt':
                prompt_string += cartVal['label'] + ":\n" + cartVal['prompt'] + "\n\n"           
            if cartVal['type'] == 'summary':
                print(cartVal)
                if 'blocks' in cartVal:
                    for block in cartVal['blocks']:
                        if 'keywords' in block:
                            if 'key' not in cartVal:
                                cartVal['key'] = ''
                            keywords_available.append({'keywords': block['keywords'], 'label': cartVal['label'], 'key': cartVal['key']})      
            elif cartVal['type'] == 'index':
                indexObj = {'title':cartVal['label'], 'key': cartVal['key']}
                if 'blocks' in cartVal:
                    indexObj.update({'notes': cartVal['blocks']})


    system_string = construct_system_prompt()

    # summary_object = [{'role': 'system', 'content': summary_string}]
    prompt_object = [{'role': 'system', 'content': prompt_string + commands_list + system_string }]

    if convoID not in current_prompt:
        current_prompt[convoID] = {}
    current_prompt[convoID]['prompt'] = prompt_object
    

async def construct_chat_query(convoID):
    eZprint('constructing chat')
    chat_log = []
    if convoID in chatlog:
        # if len(chatlog[convoID]) == 0:
            # promptObject.append({"role": "system", "content": "Based on these prompts, please initiate the conversation with a short engaginge greeting."})
        chat_log.append(example_assistant)
        for log in chatlog[convoID]:
            # print(log['order'])
            if 'muted' not in log or log['muted'] == False:
                if log['role'] == 'system':
                    chat_log.append({"role": "assistant", "content": log['body']})
                if log['role'] == 'user':  
                    chat_log.append({"role": "user", "content": "Human feedback: " + log['body']})
        chat_log.append({'role': 'user', 'content': "Respond only with the output in the exact format specified in the system prompt, with no explanation or conversation."})

    if convoID not in current_prompt:
        current_prompt[convoID] = {}
    current_prompt[convoID]['chat'] = chat_log


def construct_system_prompt():
    response_format = {
        "thoughts": {
            "text": "thought",
            "reasoning": "reasoning",
            "criticism": "constructive self-criticism",
            "speak": "thoughts summary to say to user"
        },
        "command": {"name": "command name", "args": {"arg name": "value"}},
    }
        
    formatted_response_format = json.dumps(response_format, indent=4)
    return(
        "You should only respond in JSON format as described below \nResponse"
        f" Format: \n{formatted_response_format} \nEnsure the response can be"
        " parsed by Python json.loads"
    )

example_assistant = {'role': 'assistant', 'content': '{\n    "thoughts": {\n        "text" : "understanding new session", "reasoning": "A user has logged on, I will greet them and .",\n  "speak": ""\n    },\n     "command": {\n        "name": "",\n        "args": {}\n    }\n}'}

commands_list = """
\nCommands:\n1. add_note: Creates new note for later reference, args: "title" : <title>, "body" : <body>\n2. list_notes: shows available notes, args: "note": "<note title>"\n3. append_to_note: Append note with new line, args: "note": "<note title>, "new line":<new line>"""
# \n3. append_to_file: Append to file, args: "filename": "<filename>", "text": "<text>

# \n4. delete_file: Delete file, args: "filename": "<filename>"\n5. list_files: List Files in Directory, args: "directory": "<directory>"\n6. read_file: Read a file, args: "filename": "<filename>"\n7. write_to_file: Write to file, args: "filename": "<filename>", "text": "<text>"\
# """