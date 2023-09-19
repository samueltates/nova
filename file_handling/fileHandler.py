

import base64
import json
import tempfile
import openai
import os
import asyncio
from moviepy.editor import VideoFileClip, concatenate_videoclips, concatenate_audioclips
from pydub import AudioSegment
from pydub.silence import split_on_silence
from datetime import datetime
from quart import send_file
# from chat import handle_message, return_to_GPT
from core.cartridges import addCartridge
from core.cartridges import addCartridge, update_cartridge_field
from file_handling.s3 import write_file, read_file
from tools.debug import eZprint

openai.api_key = os.getenv('OPENAI_API_KEY', default=None)

file_chunks = {}

from session.sessionHandler import novaSession, novaConvo,current_loadout, current_config



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
    print('file chunk')
    tempKey = data["tempKey"]
    file_chunks[tempKey]["chunks_received"] += 1
    # Decode the base64-encoded chunkContent
    decoded_chunk_content = base64.b64decode(data["chunkContent"])
    file_chunks[tempKey]["content"].append(decoded_chunk_content)
    return file_chunks[tempKey]["chunks_received"]
  # You could also process and store the chunk immediately in this step
  # instead of collecting all chunks in `file_chunks` and processing them later

async def handle_file_end(data):
    print('file end')
    tempKey = data["tempKey"]
    file_metadata = file_chunks[tempKey]["metadata"]
    file_content = b''.join(file_chunks[tempKey]["content"])
    # Process the uploaded file
    # You might need to convert the content from a bytearray to the initial format (e.g., base64)
    print(file_metadata)
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

    extension = file_type.split('/')[1]
    if extension == 'quicktime':
        extension = 'mov'
    if extension == 'x-matroska':
        extension = 'mkv'
    if extension == 'mpeg':
        extension = 'mp3'
    if extension == 'plain':
        extension = 'txt'


    cartKey = await addCartridge(cartVal, sessionID, loadout, convoID)
    file_name_to_write = cartKey + '.' + extension

    transcript_text = await transcribe_file(file_content, file_name_to_write, file_name, file_type, sessionID, convoID, loadout)
 
    url = await write_file(file_content, file_name_to_write) 

    eZprint(f'file {file_name_to_write} written to {url}', ['FILE_HANDLING'])

    await update_cartridge_field({'sessionID': sessionID, 'cartKey' : cartKey, 'fields': {
        'media_url': url,
        'aws_key': file_name_to_write
        }}, convoID, loadout, True)
    
    del file_chunks[tempKey]
    return file_name + ' recieved' + ' ' + str(transcript_text)



async def transcribe_file(file_content, file_key, file_name, file_type, sessionID, convoID, loadout):
    if not file_content:
        file_content = await read_file(file_key)
    processed_file = tempfile.NamedTemporaryFile(suffix=".mp4", delete=False)
    processed_file.write(file_content)
    processed_file.close()
    transcript_text = ''
    if file_type == 'video/mp4':
        transcript_text = await transcribe_video_file(processed_file, file_name, sessionID,convoID,  loadout, file_key)
    elif file_type == 'video/quicktime':
        print('video requested')
        transcript_text = await transcribe_video_file(processed_file, file_name, sessionID, convoID, loadout, file_key )
    elif file_type == 'video/x-matroska':
        print('video requested')
        transcript_text = await transcribe_video_file(processed_file, file_name, sessionID,convoID,  loadout, file_key )
    elif file_type == 'audio/mpeg':
        print('audio requested')
        transcript_text = await transcribe_audio_file(processed_file, file_name, sessionID,convoID,  loadout, file_key)

    return transcript_text


async def transcribe_video_file(file, name, sessionID, convoID, loadout, cartKey):
    clip = VideoFileClip(file.name)
    audio_temp = tempfile.NamedTemporaryFile(delete=True, suffix=".mp3")
    clip.audio.write_audiofile(audio_temp.name)

    transcript_text = await transcribe_audio_file(audio_temp, name, sessionID, convoID, loadout, cartKey)
    audio_temp.close()
    return transcript_text

async def transcribe_audio_file(file, name, sessionID, convoID, loadout, cartKey):
    eZprint(f"file to transcribe {file.name}", ['FILE_HANDLING', 'TRANSCRIBE'])
    audio = AudioSegment.from_mp3(file.name)
    avg_loudness = audio.dBFS
    
    # Try reducing these values to create smaller clips
    silence_thresh = avg_loudness + (avg_loudness * 0.15)
    min_silence_len = 1000

    chunks = split_on_silence(audio, min_silence_len=min_silence_len, silence_thresh=silence_thresh, keep_silence=True, seek_step=1)

    # Add print statements for debugging
    # print('Average loudness:', avg_loudness)
    # print('Number of audio chunks:', len(chunks))
    chunk_time_ms = 0  # initial start time  
    transcript_text = 'Transcription of ' + name + '\n\n'
    payload = {
        'sessionID': sessionID,
        'cartKey' : cartKey,
        'fields':
                {'text':transcript_text }
                }
    loadout = current_loadout[sessionID]
    await update_cartridge_field(payload, convoID, loadout, True)    

    chunkID = 0
    tasks = []
    for chunk in chunks:
        chunk_time_ms += len(chunk)  # increment by the length of the chunk
        task = asyncio.create_task(transcribe_chunk(chunk, chunk_time_ms, chunkID))
        tasks.append(task)
        chunkID += 1
    

    results = await asyncio.gather(*tasks)
    results.sort(key=lambda x: x['chunkID'])

    for result in results:
        start_time = await convert_ms_to_hh_mm_ss(result['start_time'])
        length = await convert_ms_to_hh_mm_ss(result['end_time'] - result['start_time'])
        transcript_text +=  str(start_time) + ': ' + result['transcript']['text'] + '\n' + 'Length: ' + str(length) + '\n\n'
    
    payload = {
        'sessionID': sessionID,
        'cartKey' : cartKey,
        'fields':
                {'text': transcript_text
                }
                }
    await update_cartridge_field(payload,convoID, loadout, True)
    return transcript_text

async def transcribe_chunk(chunk, chunk_file, chunk_time_ms, chunkID = 0):
        with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as chunk_file:
            chunk.export(chunk_file.name, format='mp3')
            eZprint(f'Saved to:{chunk_file.name}', ['TRANSCRIBE_CHUNK']) # Confirm file path
            chunk_file.seek(0)  # Rewind the file pointer to the beginning of the file
            #write to local as audio file
            transcript =  openai.Audio.transcribe('whisper-1', chunk_file)
            transcription = {
                'chunkID': chunkID,
                'start_time': chunk_time_ms,
                'end_time': chunk_time_ms + len(chunk),
                'transcript': transcript
            }
            os.remove(chunk_file.name)
            return transcription

async def get_file_download_link(filename):    
    return await send_file(filename, attachment_filename=filename, as_attachment=True)


async def convert_ms_to_hh_mm_ss(ms):
    seconds, ms = divmod(ms, 1000)
    minutes, seconds = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    return ':'.join([str(hours).zfill(2), str(minutes).zfill(2), str(seconds).zfill(2)]) + '.' + str(ms).zfill(3)