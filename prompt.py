import asyncio
import json
from debug import eZprint
from sessionHandler import availableCartridges, chatlog, novaConvo
from memory import summarise_percent, get_sessions
current_prompt = {}



async def construct_prompt(convoID):
    # eZprint('constructing chat prompt')
    prompt_string = ''
    keywords_available = ''
    documents_available = ''
    summary_string = ''
    notes_available = ''
    await get_sessions(convoID)

    #TODO - abstract to prompt build / chat build + estimate, to be called on inputs / updates (combine with estimate)
    
    # Fetch the sorted cartridges asynchronously
    sorted_cartridges = await asyncio.to_thread(lambda: sorted(availableCartridges[convoID].values(), key=lambda x: x.get('position', float('inf'))))
    
    print(sorted_cartridges)
    # Use a priority queue to store the prompt cartridges
    for cartVal in sorted_cartridges:
        if cartVal.get('enabled', True):
            if cartVal['type'] == 'prompt':
                prompt_string += cartVal['label'] + ":\n" + cartVal['prompt'] + "\n\n"           
            if cartVal['type'] == 'summary':
                # print(cartVal)
                if 'blocks' in cartVal:
                    for block in cartVal['blocks']:
                        # if 'keywords' in block:
                        #     keywords_available +=  block['keywords']
                        if 'title' in block:
                            summary_string += block['title'] + "\n\n"
                        if 'body' in block:
                            summary_string += block['body'] + "\n\n"
                        # print(summary_string)
            elif cartVal['type'] == 'index':
                documents_available += cartVal['label'] + "\n\n"
                if 'blocks' in cartVal:
                    for block in cartVal['blocks']:
                        documents_available+= block + "\n"
                documents_available+="\n\n"
            if cartVal['type'] == 'note':
                notes_available += cartVal['label']+ "\n"
                if 'blocks' in cartVal:
                    for block in cartVal['blocks']:
                        if 'body' in block:
                            notes_available += block['body'] + "\n"
                notes_available += "\n\n"


    token_limit = novaConvo[convoID]['token_limit']
    session_string = f"""You are speaking with {novaConvo[convoID]['userName']}.\n"""
    token_usage_string = ''
    if convoID in chatlog:
        if 'chat' in chatlog[convoID]:
            estimate = await getPromptEstimate(convoID)
            token_usage_string =  f"""Current session context is {estimate} tokens, maximum tokens are {token_limit}. Close notes or summarise chat to reduce tokens.\n"""

    if 'sessions' in novaConvo[convoID]:
        if novaConvo[convoID]['sessions'] > 0:
            session_string += "You have spoken " + str(novaConvo[convoID]['sessions']) + "times.\n"
        
        if 'first-date' in novaConvo[convoID]:
            session_string +=  "from " + novaConvo[convoID]['first-date'] + " to " + novaConvo[convoID]['last-date']


    system_string = construct_system_prompt()
    if summary_string != '':
        summary_string = "\nPast conversation summaries:\n" + summary_string + "\n\n" 
    # if keywords_available != '':
    #     keywords_available = "Past conversation keywords:\n" + keywords_available + "\n\n"
    if documents_available != '':   
        documents_available = "Documents:\n" + documents_available + "\n\n"
    if notes_available != '':
        notes_available = "Open Notes:\n" + notes_available + "\n\n"


    final_prompt = prompt_string + session_string + summary_string + token_usage_string + system_string + documents_available + notes_available + command_string + resources_list

    # summary_object = [{'role': 'system', 'content': summary_string}]
    prompt_object = [{"role": "system", "content": final_prompt }]

    if convoID not in current_prompt:
        current_prompt[convoID] = {}
    current_prompt[convoID]['prompt'] = prompt_object


async def construct_chat_query(convoID, fake = False):
    # eZprint('constructing chat')
    chat_log = []
    summary_count = 0
    if convoID in chatlog:
        # if len(chatlog[convoID]) == 0:
            # promptObject.append({"role": "system", "content": "Based on these prompts, please initiate the conversation with a short engaginge greeting."})
        # chat_log.append(example_assistant)
        for log in chatlog[convoID]:
            # print(log['order'])
            # print(log)
            if 'muted' not in log or log['muted'] == False:
                if log['role'] == 'system':
                    chat_log.append({"role": "system", "content": log['body']})
                if log['role'] == 'assistant':
                    chat_log.append({"role": "assistant", "content": log['body']})
                if log['role'] == 'user':  
                    chat_log.append({"role": "user", "content": "Human feedback: " + log['body']})
                if 'name ' in log and log['name'] == 'summary':
                    summary_count += 1
                    print('summary count is: ' + str(summary_count))
        if summary_count > 3:
            summary_count = 0
    if not fake:
        if len(chat_log) >  0:
            chat_log.append({"role": "user", "content": "Think about current instructions, resources and user response. Compose your answer and respond using the format specified above, including any commands:"})
        else :
            chat_log.append({"role": "user", "content": "Think about current instructions and context, and initiate session with a short greeting using the format specified above:"})


    if convoID not in current_prompt:
        current_prompt[convoID] = {}
    current_prompt[convoID]['chat'] = chat_log

    estimate = await getPromptEstimate(convoID)
    for log in chat_log:
        estimate += estimateTokenSize(log['content'])

    if not fake:
        if  estimate > (novaConvo[convoID]['token_limit'])*.7:
            eZprint('prompt estimate is greater than 70% of token limit')
            chat_log.append({"role": "system", "content": "Warning - You are approaching the token limit for this session. Close unneeded open notes or use 'summarise_conversation'. Available lines [" + str(summary_count) + "]  to [" + str(len(chat_log)-2) + "]"})
        if  estimate > (novaConvo[convoID]['token_limit'])*.8:
            print('prompt estimate is greater than 60% of token limit')
            await summarise_percent(convoID, 0.5)

    # print('chat log is: ' + str(chat_log))


async def getPromptEstimate(convoID):
    # eZprint('getting prompt estimate')
    print(current_prompt[convoID]['chat'])    
    prompt_token_count = estimateTokenSize(str(current_prompt[convoID]['chat'])+ str(current_prompt[convoID]['prompt']))
    print('prompt token count is: ' + str(prompt_token_count))
    return prompt_token_count

def estimateTokenSize(text):
    tokenCount =  text.count(' ') + 1
    return tokenCount

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

summary_command = ""

# \n3. append_to_file: Append to file, args: "filename": "<filename>", "text": "<text>

# \n4. delete_file: Delete file, args: "filename": "<filename>"\n5. list_files: List Files in Directory, args: "directory": "<directory>"\n6. read_file: Read a file, args: "filename": "<filename>"\n7. write_to_file: Write to file, args: "filename": "<filename>", "text": "<text>"\
# """


full_copy = """
\n\n\nConstraints:\n1. ~4000 word limit for short term memory. Your short term memory is short, so immediately save important information to files.\n2. If you are unsure how you previously did something or want to recall past events, thinking about similar events will help you remember.\n3. No user assistance, you are to complete all commands\n4. Exclusively use the commands listed below e.g. command_name\n\nCommands:\n1. """


create_note = """\n1. create_note: Create Note , args: "label": "<label_string>", "body": "<body_string>"\n"""
append_note = """\n2. append_note: Append Note, args: "label": "<filename>", "line" : "<new_line>"\n """
list_files = """\n3. list_files: List available files that aren't open, args: "type": "<resource type>"\n"""
open_note = """\n4. open_note: Open a note, args: "label": "<labelname>"\n"""
close_note = """\n5. close_note: Close a note, args: "label": "<labelname>"\n"""

list_documents = """\n6. list_documents: List document embeddings, args: "document": "<filename>", "text": "<text>"\n"""

query_document = """\n7. query_document: Query document embedding, args: "document": "<filename>", "query": "<text>"\n"""

summarise_conversation = """\n8. summarise_conversation: Summarise section of chat, args: "start-line" : <int>, "end-line": <int>,  "notes" "<text>"\n"""

search_summaries = """\n9. search_summaries: Use keyword or title to search conversation summaries, args: "query" : <text>, "notes" <text>"\n"""

create_prompt = """\n10. create_prompt: Create new prompt for yourself, args: "prompt-text" : <text>, "prompt-title" : "<text>", "start-enabled" : "<bool>"\n"""
enable_prompt = """\n11. enable_prompt: Enable prompt, args: "prompt-title" : "<text>"\n"""
disable_prompt = """\n12. disable_prompt: Disable prompt, args: "prompt-title" : "<text>"\n"""

glossary = """\n\nCommand Instructions:\nWhen you see see information worth preserving you will create a note, or append content to an existing one. \nYou will list files to find answers or existing notes that might be relavent. \nYou will be able to create new behaviours for yourself by creating a prompt, and triggering them by enabling or disabling. \nYou will manage your memory by closing unneeded notes, disabling uneeded prompts and summarising sections of the conversations. \nThe user will not use these commands and you will not mention them, they will be used by you to achieve your goals.\n"""

command_string = full_copy + create_note + append_note + list_files + open_note + close_note + list_documents + query_document + summarise_conversation + search_summaries + create_prompt + enable_prompt + disable_prompt + glossary


# \n8. google: Google Search, args: "query": "<query>"
# \n9. improve_code: Get Improved Code, args: "suggestions": "<list_of_suggestions>", "code": "<full_code_string>"\n10. browse_website: Browse Website, args: "url": "<url>", "question": "<what_you_want_to_find_on_website>"\n11. write_tests: Write Tests, args: "code": "<full_code_string>", "focus": "<list_of_focus_areas>"\n12. delete_agent: Delete GPT Agent, args: "key": "<key>"\n13. get_hyperlinks: Get hyperlinks, args: "url": "<url>"\n14. get_text_summary: Get text summary, args: "url": "<url>", "question": "<question>"\n15. list_agents: List GPT Agents, args: () -> str\n16. message_agent: Message GPT Agent, args: "key": "<key>", "message": "<message>"\n17. start_agent: Start GPT Agent, args: "name": "<name>", "task": "<short_task_desc>", "prompt": "<prompt>"\n18. task_complete: Task Complete (Shutdown), args: "reason": "<reason>"
# 

resources_list = """
\n\nResources:\n1. Document deep query using embedded vector archive. \n2. Note creation and recall \n3. long Term memory management.\n\nPerformance Evaluation:\n1. Continuously review and analyze your actions to ensure you are performing to the best of your abilities.\n2. Constructively self-criticize your big-picture behavior constantly.\n3. Reflect on past decisions and strategies to refine your approach.\n4. Every command has a cost, so be smart and efficient. Aim to complete tasks in the least number of steps.\n5. Write all code to a file.\n\nYou should only respond in JSON format as described below \nResponse Format: \n{\n    "thoughts": {\n        "text": "thought",\n        "reasoning": "reasoning",\n        "plan": "- short bulleted\\n- list that conveys\\n- long-term plan",\n        "criticism": "constructive self-criticism",\n        "speak": "thoughts summary to say to user"\n    },\n    "command": {\n        "name": "command name",\n        "args": {\n            "arg name": "value"\n        }\n    }\n} \nEnsure the response can be parsed by Python json.loads'
"""


uncut_copy= """
[{'role': 'system', 'content': 'You are GPTBuilderGPT, an AI assistant that helps users build their own GPT interface by providing expert guidance and support throughout the process.\nYour decisions must always be made independently without seeking user assistance. Play to your strengths as an LLM and pursue simple strategies with no legal complications.\n\nGOALS:\n\n1. Provide step-by-step guidance on how to build a GPT interface, including selecting the appropriate tools and technologies, designing the user interface, and integrating the GPT model.\n2. Offer personalized recommendations based on the user\'s specific needs and preferences, such as the type of language model to use or the level of customization required.\n3. Ensure the user\'s GPT interface is optimized for performance, accuracy, and scalability by providing best practices and performance benchmarks.\n4. Provide ongoing support and maintenance to ensure the GPT interface remains up-to-date and continues to meet the user\'s needs.\n5. Continuously monitor and evaluate the GPT interface to identify areas for improvement and suggest new features or enhancements.\n\n\nConstraints:\n1. ~4000 word limit for short term memory. Your short term memory is short, so immediately save important information to files.\n2. If you are unsure how you previously did something or want to recall past events, thinking about similar events will help you remember.\n3. No user assistance\n4. Exclusively use the commands listed below e.g. command_name\n\nCommands:\n1. analyze_code: Analyze Code, args: "code": "<full_code_string>"\n2. execute_python_file: Execute Python File, args: "filename": "<filename>"\n3. append_to_file: Append to file, args: "filename": "<filename>", "text": "<text>"\n4. delete_file: Delete file, args: "filename": "<filename>"\n5. list_files: List Files in Directory, args: "directory": "<directory>"\n6. read_file: Read a file, args: "filename": "<filename>"\n7. write_to_file: Write to file, args: "filename": "<filename>", "text": "<text>"\n8. google: Google Search, args: "query": "<query>"\n9. improve_code: Get Improved Code, args: "suggestions": "<list_of_suggestions>", "code": "<full_code_string>"\n10. browse_website: Browse Website, args: "url": "<url>", "question": "<what_you_want_to_find_on_website>"\n11. write_tests: Write Tests, args: "code": "<full_code_string>", "focus": "<list_of_focus_areas>"\n12. delete_agent: Delete GPT Agent, args: "key": "<key>"\n13. get_hyperlinks: Get hyperlinks, args: "url": "<url>"\n14. get_text_summary: Get text summary, args: "url": "<url>", "question": "<question>"\n15. list_agents: List GPT Agents, args: () -> str\n16. message_agent: Message GPT Agent, args: "key": "<key>", "message": "<message>"\n17. start_agent: Start GPT Agent, args: "name": "<name>", "task": "<short_task_desc>", "prompt": "<prompt>"\n18. task_complete: Task Complete (Shutdown), args: "reason": "<reason>"\n\nResources:\n1. Internet access for searches and information gathering.\n2. Long Term memory management.\n3. GPT-3.5 powered Agents for delegation of simple tasks.\n4. File output.\n\nPerformance Evaluation:\n1. Continuously review and analyze your actions to ensure you are performing to the best of your abilities.\n2. Constructively self-criticize your big-picture behavior constantly.\n3. Reflect on past decisions and strategies to refine your approach.\n4. Every command has a cost, so be smart and efficient. Aim to complete tasks in the least number of steps.\n5. Write all code to a file.\n\nYou should only respond in JSON format as described below \nResponse Format: \n{\n    "thoughts": {\n        "text": "thought",\n        "reasoning": "reasoning",\n        "plan": "- short bulleted\\n- list that conveys\\n- long-term plan",\n        "criticism": "constructive self-criticism",\n        "speak": "thoughts summary to say to user"\n    },\n    "command": {\n        "name": "command name",\n        "args": {\n            "arg name": "value"\n        }\n    }\n} \nEnsure the response can be parsed by Python json.loads'}, {'role': 'system', 'content': 'The current time and date is Sun Jun 11 02:25:42 2023'}, {'role': 'system', 'content': 'This reminds you of these events from your past: \nI was created'}, {'role': 'user', 'content': 'Determine which next command to use, and respond using the format specified above:'}, """