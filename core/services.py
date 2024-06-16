import os
import requests
from tools.debug import eZprint, eZprint_anything
import json
import aiohttp 

timeout = aiohttp.ClientTimeout(total=5000)

session = None

async def initiate_session():
    global session
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
    headers = {'content-type': 'application/json'}

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

# debug request sends time ti wait before return
async def debug_request(payload):
    eZprint('debug request', ['DEBUG','SERVICE'])

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



