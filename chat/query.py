
import os
import json
import asyncio

import tempfile
from session.tokens import check_tokens
from tools.debug import eZprint
from session.appHandler import app, websocket, openai_client
import base64
import time
from pydub import AudioSegment
import subprocess

# import 

DEBUG_KEYS = ['QUERY']

async def sendChat(promptObj, model, functions = None):
    loop = asyncio.get_event_loop()
    # try:
    if functions:
        response = await loop.run_in_executor(None, lambda: openai_client.chat.completions.create(model=model,messages=promptObj, functions=functions))
    else:
        response = await loop.run_in_executor(None, lambda: openai_client.chat.completions.create(model=model,messages=promptObj))

    return response


async def text_to_speech(input_text):
    #split by new line and then by full stop
    text_lines = input_text.split('.')
    line_index = 0

    for line in text_lines:
        eZprint(line, DEBUG_KEYS, message='line')
        response = await get_audio(line, line_index)
        line_index += 1


async def get_audio(input_text, line_index):

    response = openai_client.audio.speech.create(
        model="tts-1",
        voice="nova",
        input=input_text,
        response_format="opus"
    )

    chunk_index = 0
    output_file_path = 'output.webm'

    # The stream_to_file function saves data to a file
    response.stream_to_file(output_file_path)
    # Define a path for the output file


    # Usage example:
    with tempfile.NamedTemporaryFile(suffix='.webm', delete=False) as stream_source:
        response.stream_to_file(stream_source.name, chunk_size=8192)

        # Wait for some data to be written before starting to chunk
        await asyncio.sleep(2) 

        # Start reading from the stream and sending the data in chunks
        with open(stream_source.name, 'rb') as file_stream:
            while True:
                chunk = file_stream.read(8192)
                
                if not chunk:
                    break


                # If you're using WebSocket binary frames, you don't need to encode to base64
                # However, if you need to send as text data, you'll encode the chunk
                chunk_encoded = base64.b64encode(chunk).decode('utf-8')

                # Prepare the data payload for WebSocket
                payload = json.dumps({
                    'event': 'play_audio_chunk',
                    'payload': chunk_encoded,
                    'chunk_index': chunk_index,
                    'line_index': line_index,
                    'timestamp': time.time()
                })

                # Send the chunk over WebSocket. If the websocket.send() is an async function,
                # use 'await' to send data.
                await websocket.send(payload)
                chunk_index += 1
                

        # wait_time = 2
        # await asyncio.sleep(wait_time)
        # inspect_webm_file(stream_source.name)
# 
        os.unlink(stream_source.name)
    await websocket.send(json.dumps({'event': 'audio_chunks_finished', 'line_index': line_index}))
        
# def inspect_webm_file(file_path):
  
#     # Use ffprobe to get information about the webm file
#     command = ['ffprobe', '-v', 'quiet', '-print_format', 'json', '-show_format', '-show_streams', file_path]
#     result = subprocess.run(command, capture_output=True, text=True)
    
#     if result.returncode == 0:
#         output = result.stdout
#         print(output)
#     else:
#         print(f"Error inspecting webm file: {result.stderr}")






async def getModels():

    # TODO: The resource 'Engine' has been deprecated
    # models = openai.Engine.list()
    # models = openai_client.engine.list()
    # return models

    # except:
    #     try:
    #         if functions:
    #             response = await loop.run_in_executor(None, lambda: openai.ChatCompletion.create(model=model,messages=promptObj, functions=functions))
    #         else:
    #             response = await loop.run_in_executor(None, lambda: openai.ChatCompletion.create(model=model,messages=promptObj))        
    #     except Exception as e:
    #         print(e)
    #         # print(promptObj)
    #         response = None
    #         response = {}
    #         response["choices"] = []
    #         response["choices"].append({})
    #         response["choices"][0]["message"] = {}
    #         response["choices"][0]["message"]["content"] = str(e)

    # return response
    return 



async def get_summary_with_prompt(prompt, textToSummarise, model = 'gpt-3.5-turbo', userID = ''):

    if userID:
        tokens = await check_tokens(userID)
        if not tokens:
            return


    promptObject = []
    promptObject.append({'role' : 'system', 'content' : prompt})
    promptObject.append({'role' : 'user', 'content' : textToSummarise})
    promptObject.append({"role": "user", "content": "Think about summary instructions and supplied content. Compose your answer and respond using the format specified above:"})

    
    eZprint(textToSummarise, DEBUG_KEYS, message='textToSummarise') 
    # model = app.session.get('model')
    # if model == None:
    #     model = 'gpt-3.5-turbo'
    response = await sendChat(promptObject, model)

    eZprint(response, DEBUG_KEYS, message='response')
    content = response.choices[0].message.content
    # print(content)
    return content





async def parse_json_string(content):

    # eZprint('parsing json string')
    # print(content)
    json_object = None
    error = None
    try:
        json_object = json.loads(content, strict=False)
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
        json_object = json.loads(json_data, strict=False)
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
        json_object = json.loads(json_data, strict=False)
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