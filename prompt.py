import asyncio

from debug import eZprint
from sessionHandler import availableCartridges, chatlog

current_prompt = {}

async def construct_prompt(convoID):
    eZprint('constructing chat prompt')
    prompt_string = ''
    keywords_available = []
    documents_available = []

    #TODO - abstract to prompt build / chat build + estimate, to be called on inputs / updates (combine with estimate)
    promptObject=[]
    
    # Fetch the sorted cartridges asynchronously
    sorted_cartridges = await asyncio.to_thread(lambda: sorted(availableCartridges[convoID].values(), key=lambda x: x.get('position', float('inf'))))
    
    prompt_string += "PROMPTS\n"
    # Use a priority queue to store the prompt cartridges
    for cartVal in sorted_cartridges:
        if cartVal.get('enabled', True):
            if cartVal['type'] == 'prompt':
                prompt_string += cartVal['label'] + ":\n" + cartVal['prompt'] + "\n"           
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

    ##creating sub commands
    command_string = ''
    keyword_string = ''
    document_string = ''


    if len(keywords_available) != 0:
        keyword_string = "\nCONVERSATION HISTORY\nThere have been 300 seperate conversations between Nova and Sam, from september 2022 to June 2023. \n\nKEYWORDS.\n"
        for keyword in keywords_available:
            keyword_string +=  str(keyword['keywords']) + "\n"
        keyword_string += "If it is relavent to conversation, use {'command':'select keyword [keyword]' to open a summary. This is encouraged as it will increase your context.\n\n"
        command_string += "-select keyword [keyword] (opens a summary based on a keyword)\n"
        # command_string += "__________\nselect [keyword] [summary ID]' - open a document based on a keyword. "

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
        command_string = "AVAILABLE COMMANDS\n " + command_string + "\n" 
    if keyword_string != '':
        prompt_string = keyword_string + prompt_string
    if document_string != '':
        prompt_string += document_string
    if command_string != '':
        prompt_string += command_string

    prompt_string += formatting_instruction + example_response
    eZprint('prompt string constructed')
    print(f'{prompt_string}')
    promptObject.append({"role": "user", "content": prompt_string})

    if convoID not in current_prompt:
        current_prompt[convoID] = {}
    current_prompt[convoID]['prompt'] = promptObject
    
async def construct_chat_query(convoID):
    eZprint('constructing chat')
    chat_log = []
    if convoID in chatlog:
        # if len(chatlog[convoID]) == 0:
            # promptObject.append({"role": "system", "content": "Based on these prompts, please initiate the conversation with a short engaginge greeting."})
        for log in chatlog[convoID]:
            # print(log['order'])
            if 'muted' not in log or log['muted'] == False:
                if log['role'] == 'system':
                    chat_log.append({"role": "assistant", "content": log['body']})
                if log['role'] == 'user':  
                    chat_log.append({"role": "user", "content":log['body']})
    if convoID not in current_prompt:
        current_prompt[convoID] = {}
    current_prompt[convoID]['chat'] = chat_log


formatting_instruction = """

FORMATTING INSTRUCTIONS
Provide response in JSON format, including answer, reasoning and any commands, eg:

    {
        "answer":"response to prompt in natural language",
        "reasoning":"any reasoning or thinking behind the response",
        "commands": "command-1 arg, command-2 arg"
    }

"""



example_response  = """

EXAMPLE RESPONSE
'user': 'hey Nova, lets kick off the week.'

'nova': 
    {
        'answer' : 'Ok sounds good, lets start with a quick check in. How are you feeling today?',
        'reasoning' : 'I want to start with a check in to see how Sam is feeling today, and to get a sense of what he has been up to.',
        'commands' : 'select keyword weekly-planning, query calender 'what appointments are coming this week',
    }
"""
