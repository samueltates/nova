import os
import requests
from quart import request
from tools.debug import eZprint, eZprint_anything
import json
import aiohttp 
# import logging
from session.appHandler import app

timeout = aiohttp.ClientTimeout(total=5000)

session = None

awaited_media = {}

async def initiate_session():
    global session
    # async def on_request_start(
    #     session, trace_config_ctx, params):
    #     print("Starting request")
    #     logging.getLogger('aiohttp.client').debug(f'Starting request <{params}>')



    # async def on_request_end(session, trace_config_ctx, params):
    #     print("Ending request")

    # trace_config = aiohttp.TraceConfig()
    # trace_config.on_request_start.append(on_request_start)
    # trace_config.on_request_end.append(on_request_end)
    # trace_config.on_request_exception.append(on_request_end)

    # session = aiohttp.ClientSession(timeout=timeout, trace_configs=[trace_config])
    session = aiohttp.ClientSession(timeout=timeout)



async def transcribe_file(file_key, file_name, file_type):

    if not session:
        await initiate_session()


    payload = {
        'file_key' : file_key,
        'file_name' : file_name,
        'file_type' : file_type
    }
    eZprint('request to transcribe sending to API', ['TRANSCRIBE','SERVICE'])
    headers = {'content-type': 'application/json'
               }

    async with session.post(os.getenv('MEDIA_URL') + 'get_transcript', data=json.dumps(payload), headers=headers) as response:
        

        response_text = await response.text()
        response_json = json.loads(response_text)
    # async with aiohttp.ClientSession(timeout=timeout) as session:
    #     async with session.post(os.getenv('MEDIA_URL') + 'get_transcript', data=json.dumps(payload), headers=headers) as response:
    #         # eZprint(response, ['TRRANSCRIBE'], message='API  response')
    #         response_text = await response.text()
    #         response_json = json.loads(response_text)

    # Your debug print functions
    eZprint('transcribe json response', ['TRANSCRIBE','SERVICE'])
    return response_json


async def get_b_roll_images_from_request(payload):
    # Your debug print functions
    eZprint('b_roll requested', ['BROLL','SERVICE'])

    headers = {'content-type': 'application/json'}

    if not session:
        await initiate_session()

    async with session.post(os.getenv('MEDIA_URL') + 'handle_generate_b_roll', data=json.dumps(payload), headers=headers) as response:
        # eZprint(response, ['BROLL'], message='b_roll response')
        response_text = await response.text()
        response_json = json.loads(response_text)

    # async with aiohttp.ClientSession(timeout=timeout) as session:
    #     async with session.post(os.getenv('MEDIA_URL') + 'handle_generate_b_roll', data=json.dumps(payload), headers=headers) as response:
    #         # eZprint(response, ['BROLL'], message='b_roll response')
    #         response_text = await response.text()
    #         response_json = json.loads(response_text)

    # Your debug print functions
    eZprint('b_roll returned', ['BROLL', 'SERVICE'])
    return response_json

async def get_media_from_request(payload):
    # Your debug print functions
    eZprint('media payload', ['MEDIA','SERVICE'])

    if not session:
        await initiate_session()
        

    headers = {'content-type': 'application/json'}

    async with session.post(os.getenv('MEDIA_URL') + 'transform', data=json.dumps(payload), headers=headers) as response:
        response_text = await response.text()
        response_json = json.loads(response_text)
    # async with aiohttp.ClientSession(timeout=timeout) as session:
    #     async with session.post(os.getenv('MEDIA_URL') + 'transform', data=json.dumps(payload), headers=headers) as response:
    #         response_text = await response.text()
    #         response_json = json.loads(response_text)

    # Your debug print functions
    eZprint('media returned', ['MEDIA', 'SERVICE'])
    return response_json


app.route('/receive_response', methods=['POST'])
async def receive_response():
    data = await request.get_json()
    eZprint(data, ['RECEIVE'], message='received response')
    awaited_media[data['file_key']] = data
    return jsonify({'status':'success'})



# debug request sends time ti wait before return
async def debug_request(payload):
    eZprint('debug request' , ['DEBUG','SERVICE'])

    if not session:
        await initiate_session()



    headers = {'content-type': 'application/json'}

    try:
        async with session.post(os.getenv('MEDIA_URL') + 'debug_request', data=json.dumps(payload), headers=headers) as response:

            response_text = await response.text()
            response_json = json.loads(response_text)
    except Exception as e:
        eZprint(f'Error: {e} of Type: {type(e)}', ['DEBUG','SERVICE'])
        response_json = {'status':'error', 'message':'error in debug request'}


    # async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=5000)) as session:
    #     try:
    #         async with session.post(os.getenv('MEDIA_URL') + 'debug_request', data=json.dumps(payload), headers=headers) as response:
    #             response_text = await response.text()
    #             response_json = json.loads(response_text)
    #     except Exception as e:
    #         eZprint(f'Error: {e} of Type: {type(e)}', ['DEBUG', 'SERVICE'])
    #         response_json = {'status':'error', 'message':'error in debug request'}


    eZprint('debug response', ['DEBUG', 'SERVICE'])
    return response_json



