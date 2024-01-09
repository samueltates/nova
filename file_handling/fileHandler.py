

import base64
import openai
import os
from quart import send_file

from core.cartridges import addCartridge, update_cartridge_field
from file_handling.s3 import write_file
from file_handling.transcribe import transcribe_file
from tools.debug import eZprint, eZprint_anything
#named temporary
from tempfile import NamedTemporaryFile
from unstructured.staging.base import convert_to_dict

file_chunks = {}

from session.sessionHandler import novaSession

async def handle_file_start(data):
    eZprint('file start', ['FILE_HANDLING'], line_break=True)
    
    tempKey = data["tempKey"]
    file_chunks[tempKey] = {
    "metadata": data,   
    "chunks_received": 0,
    "content": [],
    }
    return True


async def handle_file_chunk(data):
    eZprint('file chunk',  ['FILE_HANDLING'], line_break=True)
    tempKey = data["tempKey"]
    file_chunks[tempKey]["chunks_received"] += 1
    # Decode the base64-encoded chunkContent
    decoded_chunk_content = base64.b64decode(data["chunkContent"])
    file_chunks[tempKey]["content"].append(decoded_chunk_content)
    return file_chunks[tempKey]["chunks_received"]
  # You could also process and store the chunk immediately in this step
  # instead of collecting all chunks in `file_chunks` and processing them later

async def handle_file_end(data):
    eZprint('file end', ['FILE_HANDLING'], line_break=True  )
    tempKey = data["tempKey"]
    file_metadata = file_chunks[tempKey]["metadata"]
    file_content = b''.join(file_chunks[tempKey]["content"])
    # Process the uploaded file
    # You might need to convert the content from a bytearray to the initial format (e.g., base64)
    # print(file_metadata)
    data = {
        'sessionID': file_metadata['sessionID'],
        'userID': file_metadata['userID'],
        'file_content': file_content,
        'file_name': file_metadata['file_name'],
        'file_type': file_metadata['file_type'],
        'sessionID': file_metadata['sessionID'],
        'convoID' : file_metadata['convoID'],
        'loadout': file_metadata['loadout'],
        'tempKey': file_metadata['tempKey'],
        'document_type': file_metadata['document_type'],
    }

    sessionID = data['sessionID']
    # client_loadout = None
    # if sessionID in current_loadout:
    #     client_loadout = current_loadout[sessionID]
        
    file_content = data['file_content']

    file_name = data['file_name']
    file_type = data['file_type']
    loadout = data['loadout']
    convoID = data['convoID']

    convoID = novaSession[sessionID]['convoID']
    cartVal = {
        'label' : file_name,
        # 'text' : str(transcriptions),
        'file' : file_name,
        'extension' : file_type,
        # 'media_url' : url,
        'type' : 'media',
        'enabled' : True,
    }

    if file_type:
        extension = file_type.split('/')[1]
    else:
        # split file name on period
        file_name_split = file_name.split('.')
        extension = file_name_split[len(file_name_split) - 1]
        cartVal['extension'] = extension
    elements = []

    if extension == 'quicktime':
        extension = 'mov'
    if extension == 'x-matroska':
        extension = 'mkv'
    if extension == 'mpeg':
        extension = 'mp3'
    if extension == 'plain':
        extension = 'txt'
        from unstructured.partition.text import partition_text
        with NamedTemporaryFile(suffix='.'+extension, delete=False) as stream_source:
            stream_source.write(file_content)
            stream_source.seek(0)
            elements = partition_text(filename=stream_source.name)
            elements = convert_to_dict(elements)
    if extension == 'pdf':
        #make named temporary file
        #write file content to it
        #pass to unstructured reader
        
        from unstructured.partition.pdf import partition_pdf
        
        with NamedTemporaryFile(suffix='.'+extension, delete=False) as stream_source:
            stream_source.write(file_content)
            stream_source.seek(0)

            elements = partition_pdf(filename=stream_source.name)
            elements = convert_to_dict(elements)

            # Wait for some data to be written before starting to chunk
            

        eZprint_anything(elements, ['FILE_HANDLING'], message='elements')

    cartKey = await addCartridge(cartVal, sessionID, loadout, convoID)
    file_name_to_write = cartKey + '.' + extension

    # transcript_text = await transcribe_file(file_content, cartKey, file_name, file_type, sessionID, convoID, loadout)
 
    url = await write_file(file_content, file_name_to_write) 

    eZprint(f'file {file_name_to_write} written to {url}', ['FILE_HANDLING'])

    await update_cartridge_field({'sessionID': sessionID, 'cartKey' : cartKey, 'fields': {
        'media_url': url,
        'aws_key': file_name_to_write,
        'elements': elements
        }}, convoID, loadout, True)
    
    del file_chunks[tempKey]
    return file_name + ' uploaded' 
    # return file_name + ' recieved' + ' ' + str(transcript_text)

async def get_file_download_link(filename):    
    return await send_file(filename, attachment_filename=filename, as_attachment=True)

