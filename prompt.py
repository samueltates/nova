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
    
    prompt_objects = []

    prompt_string += """"\nPrompts:
    # Instructions from Sam:
    """
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


    summary_string = """
    There have been 300 seperate conversations between Nova and Sam, from september 2022 to June 2023.
    """



    ##creating sub commands
    command_string = ''
    keyword_string = ''
    document_string = ''

    print(keywords_available)
    print(len(keywords_available))

    # if len(keywords_available) > 1:
    #     keyword_string = """
    #     The following are keywords from all conversation sumaries.\n
    #     """
    #     for keyword in keywords_available:
    #         keyword_string +=  str(keyword['keywords']) + "\n"
        
    #     command_string += """
    #     command: select-keyword args:[keyword] (opens a summary based on a keyword)\n"""

    if len(documents_available) != 0:
        document_string =  "__________\nThe following are documents and current notes, which can queried via query command.\n"
        documents_available += cartVal['label'] + "\n\n"
        for document in documents_available:
            document_string += document['label'] + ":\n" 
            if 'notes' in document:
                for note in document['notes']:
                    document_string += str(note['notes']) + "\n"
            document_string += "\nQuery via docID: " + document['key'] + "\n"
        command_string += "__________\n 'query' [docID] ['question'] - query the index for a specific keyword or phrase.\n"



    if command_string != '':
        command_string = """
        Available commands are:"""+command_string+"""
        command: update-note args:[title]
        command: add-note args:[title]
        command: delete-note args:[title]
        command: search args:[keyword]
        command: query args:[docID] args:[question]
        """
 
    

    #setting up final prompts
    # if keyword_string != '':
    #     prompt_string = keyword_string + prompt_string
    # if document_string != '':
    #     prompt_string += document_string
    # if command_string != '':
    system_string = await construct_system_prompt()

    # summary_object = [{'role': 'system', 'content': summary_string}]
    prompt_object = [{'role': 'system', 'content': prompt_string + command_string + system_string }]

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
                    chat_log.append({"role": "user", "content":log['body']})
        chat_log.append({'role': 'user', 'content': 'Based on prompts & any messages, respond using the format specified above:'})

    if convoID not in current_prompt:
        current_prompt[convoID] = {}
    current_prompt[convoID]['chat'] = chat_log


async def construct_system_prompt():
    response_format = {
        "thoughts": {
            "reasoning": "any reasoning or thinking behind the response",
            "answer": "response to prompt in natural language",
        },
        "command": {"name": "command name", "args": {"arg name": "value"}},
    }
        
    formatted_response_format = json.dumps(response_format, indent=4)
    return(
        "You should only respond in JSON format as described below \nResponse"
        f" Format: \n{formatted_response_format} \nEnsure the response can be"
        " parsed by Python json.loads"
    )

example_assistant = {'role': 'assistant', 'content': '{\n    "thoughts": {\n         "reasoning": "A user has logged on, and there are instructions and formats I must adhere to.",\n  "answer": ""\n    },\n     "command": {\n        "name": "",\n        "args": {}\n    }\n}'}

commands_list = """
\nCommands:\n1. analyze_code: Analyze Code, args: "code": "<full_code_string>"\n2. execute_python_file: Execute Python File, args: "filename": "<filename>"\n3. append_to_file: Append to file, args: "filename": "<filename>", "text": "<text>"\n4. delete_file: Delete file, args: "filename": "<filename>"\n5. list_files: List Files in Directory, args: "directory": "<directory>"\n6. read_file: Read a file, args: "filename": "<filename>"\n7. write_to_file: Write to file, args: "filename": "<filename>", "text": "<text>"\
"""