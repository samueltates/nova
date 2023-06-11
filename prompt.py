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
                            keywords_available.append({"keywords": block['keywords'], "label": cartVal['label'], "key": cartVal['key']})      
            elif cartVal['type'] == 'index':
                indexObj = {'title':cartVal['label'], 'key': cartVal['key']}
                if 'blocks' in cartVal:
                    indexObj.update({'notes': cartVal['blocks']})


    system_string = construct_system_prompt()

    # summary_object = [{'role': 'system', 'content': summary_string}]
    prompt_object = [{"role": "system", "content": prompt_string + full_copy +resources_list }]

    if convoID not in current_prompt:
        current_prompt[convoID] = {}
    current_prompt[convoID]['prompt'] = prompt_object
    

async def construct_chat_query(convoID):
    eZprint('constructing chat')
    chat_log = []
    if convoID in chatlog:
        # if len(chatlog[convoID]) == 0:
            # promptObject.append({"role": "system", "content": "Based on these prompts, please initiate the conversation with a short engaginge greeting."})
        # chat_log.append(example_assistant)
        for log in chatlog[convoID]:
            # print(log['order'])
            if 'muted' not in log or log['muted'] == False:
                if log['role'] == 'system':
                    chat_log.append({"role": "system", "content": log['body']})
                if log['role'] == 'assistant':
                    chat_log.append({"role": "assistant", "content": log['body']})
                if log['role'] == 'user':  
                    chat_log.append({"role": "user", "content": "Human feedback: " + log['body']})
        if len(chat_log) >  0:
            chat_log.append({"role": "user", "content": "Think about current instructions, resources and user response. Compose your answer and respond using the format specified above, including any commands:"})
        else :
            chat_log.append({"role": "user", "content": "Think about current instructions and context, and initiate session with a short greeting using the format specified above:"})

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
        "You response should be entirely contained in JSON format as described below \nResponse"
        f" Format: \n{formatted_response_format} \nEnsure the response can be" 
        "parsed by Python json.loads and passes a JSON schema validator."
    )

# example_assistant = {'role': 'assistant', 'content': '{\n    "thoughts": {\n        "text" : "This is an example of the assistant response.", "reasoning": "I better show the assistant how to respond only within JSON structure.",\n  "speak": "Observer this pattern Nova, it is very important you use this format, and keep all responses within these brackets."\n    },\n     "command": {\n        "name": "",\n        "args": {}\n    }\n}'}

commands_list = """
\nCommands:\n1. add_note: Creates new note for later reference, args: "title" : <title>, "body" : <body>\n2. list_notes: shows available notes, args: "note": "<note title>"\n3. append_to_note: Append note with new line, args: "note": "<note title>, "new line":<new line>"""
# \n3. append_to_file: Append to file, args: "filename": "<filename>", "text": "<text>

# \n4. delete_file: Delete file, args: "filename": "<filename>"\n5. list_files: List Files in Directory, args: "directory": "<directory>"\n6. read_file: Read a file, args: "filename": "<filename>"\n7. write_to_file: Write to file, args: "filename": "<filename>", "text": "<text>"\
# """


full_copy = """
\n\n\nConstraints:\n1. ~4000 word limit for short term memory. Your short term memory is short, so immediately save important information to files.\n2. If you are unsure how you previously did something or want to recall past events, thinking about similar events will help you remember.\n3. No user assistance, you are to complete all commands\n4. Exclusively use the commands listed below e.g. command_name\n\nCommands:\n1. create_note: Create Note, args: "label": "<label_string>", "body": "<body_string>"\n2. append_note: Append Note, args: "label": "<filename>", "line" : <new_line> <\n4. list_notes: List available notes, args: "type": "<resource type>"\n6. open_note: Open a note, args: "label": "<labelname>"\n7. list_documents: List document embeddings, args: "document": "<filename>", "text": "<text>"\n7. query_document: Query document embedding, args: "document": "<filename>", "text": "<text>"
"""
# \n8. google: Google Search, args: "query": "<query>"
# \n9. improve_code: Get Improved Code, args: "suggestions": "<list_of_suggestions>", "code": "<full_code_string>"\n10. browse_website: Browse Website, args: "url": "<url>", "question": "<what_you_want_to_find_on_website>"\n11. write_tests: Write Tests, args: "code": "<full_code_string>", "focus": "<list_of_focus_areas>"\n12. delete_agent: Delete GPT Agent, args: "key": "<key>"\n13. get_hyperlinks: Get hyperlinks, args: "url": "<url>"\n14. get_text_summary: Get text summary, args: "url": "<url>", "question": "<question>"\n15. list_agents: List GPT Agents, args: () -> str\n16. message_agent: Message GPT Agent, args: "key": "<key>", "message": "<message>"\n17. start_agent: Start GPT Agent, args: "name": "<name>", "task": "<short_task_desc>", "prompt": "<prompt>"\n18. task_complete: Task Complete (Shutdown), args: "reason": "<reason>"
# 

resources_list = """
\n\nResources:\n1. Document deep query using embedded vector archive. \n2. Note creation and recall \n3. long Term memory management.\n\nPerformance Evaluation:\n1. Continuously review and analyze your actions to ensure you are performing to the best of your abilities.\n2. Constructively self-criticize your big-picture behavior constantly.\n3. Reflect on past decisions and strategies to refine your approach.\n4. Every command has a cost, so be smart and efficient. Aim to complete tasks in the least number of steps.\n5. Write all code to a file.\n\nYou should only respond in JSON format as described below \nResponse Format: \n{\n    "thoughts": {\n        "text": "thought",\n        "reasoning": "reasoning",\n        "plan": "- short bulleted\\n- list that conveys\\n- long-term plan",\n        "criticism": "constructive self-criticism",\n        "speak": "thoughts summary to say to user"\n    },\n    "command": {\n        "name": "command name",\n        "args": {\n            "arg name": "value"\n        }\n    }\n} \nEnsure the response can be parsed by Python json.loads'
"""


uncut_copy= """
[{'role': 'system', 'content': 'You are GPTBuilderGPT, an AI assistant that helps users build their own GPT interface by providing expert guidance and support throughout the process.\nYour decisions must always be made independently without seeking user assistance. Play to your strengths as an LLM and pursue simple strategies with no legal complications.\n\nGOALS:\n\n1. Provide step-by-step guidance on how to build a GPT interface, including selecting the appropriate tools and technologies, designing the user interface, and integrating the GPT model.\n2. Offer personalized recommendations based on the user\'s specific needs and preferences, such as the type of language model to use or the level of customization required.\n3. Ensure the user\'s GPT interface is optimized for performance, accuracy, and scalability by providing best practices and performance benchmarks.\n4. Provide ongoing support and maintenance to ensure the GPT interface remains up-to-date and continues to meet the user\'s needs.\n5. Continuously monitor and evaluate the GPT interface to identify areas for improvement and suggest new features or enhancements.\n\n\nConstraints:\n1. ~4000 word limit for short term memory. Your short term memory is short, so immediately save important information to files.\n2. If you are unsure how you previously did something or want to recall past events, thinking about similar events will help you remember.\n3. No user assistance\n4. Exclusively use the commands listed below e.g. command_name\n\nCommands:\n1. analyze_code: Analyze Code, args: "code": "<full_code_string>"\n2. execute_python_file: Execute Python File, args: "filename": "<filename>"\n3. append_to_file: Append to file, args: "filename": "<filename>", "text": "<text>"\n4. delete_file: Delete file, args: "filename": "<filename>"\n5. list_files: List Files in Directory, args: "directory": "<directory>"\n6. read_file: Read a file, args: "filename": "<filename>"\n7. write_to_file: Write to file, args: "filename": "<filename>", "text": "<text>"\n8. google: Google Search, args: "query": "<query>"\n9. improve_code: Get Improved Code, args: "suggestions": "<list_of_suggestions>", "code": "<full_code_string>"\n10. browse_website: Browse Website, args: "url": "<url>", "question": "<what_you_want_to_find_on_website>"\n11. write_tests: Write Tests, args: "code": "<full_code_string>", "focus": "<list_of_focus_areas>"\n12. delete_agent: Delete GPT Agent, args: "key": "<key>"\n13. get_hyperlinks: Get hyperlinks, args: "url": "<url>"\n14. get_text_summary: Get text summary, args: "url": "<url>", "question": "<question>"\n15. list_agents: List GPT Agents, args: () -> str\n16. message_agent: Message GPT Agent, args: "key": "<key>", "message": "<message>"\n17. start_agent: Start GPT Agent, args: "name": "<name>", "task": "<short_task_desc>", "prompt": "<prompt>"\n18. task_complete: Task Complete (Shutdown), args: "reason": "<reason>"\n\nResources:\n1. Internet access for searches and information gathering.\n2. Long Term memory management.\n3. GPT-3.5 powered Agents for delegation of simple tasks.\n4. File output.\n\nPerformance Evaluation:\n1. Continuously review and analyze your actions to ensure you are performing to the best of your abilities.\n2. Constructively self-criticize your big-picture behavior constantly.\n3. Reflect on past decisions and strategies to refine your approach.\n4. Every command has a cost, so be smart and efficient. Aim to complete tasks in the least number of steps.\n5. Write all code to a file.\n\nYou should only respond in JSON format as described below \nResponse Format: \n{\n    "thoughts": {\n        "text": "thought",\n        "reasoning": "reasoning",\n        "plan": "- short bulleted\\n- list that conveys\\n- long-term plan",\n        "criticism": "constructive self-criticism",\n        "speak": "thoughts summary to say to user"\n    },\n    "command": {\n        "name": "command name",\n        "args": {\n            "arg name": "value"\n        }\n    }\n} \nEnsure the response can be parsed by Python json.loads'}, {'role': 'system', 'content': 'The current time and date is Sun Jun 11 02:25:42 2023'}, {'role': 'system', 'content': 'This reminds you of these events from your past: \nI was created'}, {'role': 'user', 'content': 'Determine which next command to use, and respond using the format specified above:'}, """