import requests
import tempfile
import asyncio

from session.appHandler import openai_client
from core.cartridges import addCartridge, update_cartridge_field
from file_handling.s3 import write_file, read_file
from tools.debug import eZprint



async def generate_temp_image(prompt):
    DEBUG_KEYS = ['FILE_HANDLING', 'IMAGE_GENERATION']
    eZprint(f'Generating image with prompt: {prompt}', DEBUG_KEYS)
    try:
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(None, lambda: openai_client.images.generate(prompt=prompt,
                                                                                        model='dall-e-3',
        n=1,
        size='1024x1024'))
    except Exception as e:
        eZprint(f'Error generating image: {e}', DEBUG_KEYS)
        return None
    
    image_url = response.data[0].url
    response = requests.get(image_url)
    eZprint(f'Image URL: {image_url}', DEBUG_KEYS)
    processed_media = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
    processed_media.write(response.content)
    processed_media.close()
    return processed_media
    

async def generate_images(prompts, sessionID, convoID, loadout):

    tasks = [generate_image(prompt, sessionID, convoID, loadout) for prompt in prompts]
    images = await asyncio.gather(*tasks)
    images_str = ', '.join(images)
    return images_str


async def generate_image(prompt, sessionID, convoID, loadout):

    loop = asyncio.get_event_loop()
    response = await loop.run_in_executor(None, lambda: client.images.generate(prompt=prompt,
    n=1,
    size='1024x1024'))
    
    image_url = response['data'][0]['url']
    print(f'Image URL: {image_url}')
    response = requests.get(image_url)
    
    name = prompt + '.png'
    cartVal = {
        'label' : name,
        # 'text' : str(transcriptions),
        'description' : 'Image generated by openAI with prompt: ' + prompt,
        'file' : name,
        'extension' : 'image/png',
        # 'media_url' : url,
        'type' : 'media',
        'enabled' : True,
    }

    cartKey = await addCartridge(cartVal, sessionID, loadout, convoID )
    url = await write_file(response.content, cartKey) 
    print(url)
    await update_cartridge_field({'sessionID': sessionID, 'cartKey' : cartKey, 'fields': {'media_url': url}}, convoID, loadout, True)

    return name
