import openai
import os
import json
import asyncio
openai.api_key = os.getenv('OPENAI_API_KEY', default=None)
from tokens import check_tokens

async def sendChat(promptObj, model):
    loop = asyncio.get_event_loop()
    try:
        response = await loop.run_in_executor(None, lambda: openai.ChatCompletion.create(model=model,messages=promptObj))

    except:
        try:
            response = await loop.run_in_executor(None, lambda: openai.ChatCompletion.create(model=model,messages=promptObj))
        except Exception as e:
            print(e)
            print(promptObj)
            response = None
            response = {}
            response["choices"] = []
            response["choices"].append({})
            response["choices"][0]["message"] = {}
            response["choices"][0]["message"]["content"] = e

    return response



async def get_summary_with_prompt(prompt, textToSummarise, model = 'gpt-3.5-turbo', userID = ''):

    if userID:
        tokens = await check_tokens(userID)
        if not tokens:
            return


    promptObject = []
    promptObject.append({'role' : 'system', 'content' : prompt})
    promptObject.append({'role' : 'user', 'content' : textToSummarise})
    promptObject.append({"role": "user", "content": "Think about summary instructions and supplied content. Compose your answer and respond using the format specified above:"})

    
    # print(textToSummarise)
    # model = app.session.get('model')
    # if model == None:
    #     model = 'gpt-3.5-turbo'
    response = await sendChat(promptObject, model)

    # print(response)
    content = response["choices"][0]["message"]["content"]
    # print(content)
    return content





async def parse_json_string(content):

    # eZprint('parsing json string')
    # print(content)
    json_object = None
    error = None
    try:
        json_object = json.loads(content)
        return json_object

    except ValueError as e:
        # the string is not valid JSON, try to remove unwanted characters
        print(f"Error parsing JSON: {e}")
        # print(content)


##########################REMOVE BRACKETS

    if json_object == None:
        
        # print('clearing anything before and after brackets')
        start_index = content.find('{')
        end_index = content.rfind('}')
        json_data = content[start_index:end_index+1]
        # print(json_data)
    try: 
        json_object = json.loads(json_data)
        return json_object
    
    except ValueError as e:
        # the string is still not valid JSON, print the error message
        # print(f"Error parsing JSON: {e}")
        error = e

##########################MANUALLY REMOVE COMMA

    if json_object == None:
            # print('trying manual parsing')
            json_data = remove_commas_after_property(content)

    try: 
        json_object = json.loads(json_data)
        return json_object
    
    except ValueError as e:
        # the string is still not valid JSON, print the error message
        print(f"Error parsing JSON: {e}")
    return



def remove_commas_after_property(content):
    counter = 0
    lastChar = ''
    removal_candidate = 0
    removal_candidates = []
    for char in content:
        # print(char + ' | ')
        if not removal_candidate:
            if char == ',' and lastChar == '"':
                # print('found char for removal')
                removal_candidate = counter
        elif removal_candidate :
            if (char == ',' or char == ' ' or char == '\n') and (lastChar == ',' or lastChar == ' ' or lastChar == '\n'):
                # print('current and last either apostrophe, space or enter')
                pass
            elif char == '}' and (lastChar == ' ' or lastChar == ','):
                # print('now on close bracked followed by either space or comma,')
                removal_candidates.append(removal_candidate)
            else:
                # print('not on a space followed by comma or a space so not a candidate')
                removal_candidate = 0
        counter += 1
        lastChar = char
    removal_candidates.reverse()
    for candidate in removal_candidates:
        content = content[:candidate] + content[candidate+1:]
    # print (content)
    return content