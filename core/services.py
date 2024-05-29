import os
import requests
from tools.debug import eZprint, eZprint_anything
import json
import aiohttp 


async def get_b_roll_images_from_request(payload):
    # Your debug print functions
    eZprint(payload, ['BROLL'], message='b_roll payload')

    headers = {'content-type': 'application/json'}
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=5000)) as session:
        async with session.post(os.getenv('MEDIA_URL') + 'handle_generate_b_roll', data=json.dumps(payload), headers=headers) as response:
            eZprint(response, ['BROLL'], message='b_roll response')
            response_text = await response.text()
            response_json = json.loads(response_text)

    # Your debug print functions
    eZprint_anything(response_json, ['BROLL'], message='b_roll response')
    return response_json

async def get_media_from_request(payload):
    # Your debug print functions
    eZprint(payload, ['MEDIA'], message='media payload')

    headers = {'content-type': 'application/json'}
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=5000)) as session:
        async with session.post(os.getenv('MEDIA_URL') + 'transform', data=json.dumps(payload), headers=headers) as response:
            response_text = await response.text()
            response_json = json.loads(response_text)

    # Your debug print functions
    eZprint_anything(response_json, ['MEDIA'], message='media response')
    return response_json