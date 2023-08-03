

import base64
import json
import tempfile
from moviepy.editor import VideoFileClip
import openai
import os
from pydub import AudioSegment
from pydub.silence import split_on_silence
from cartridges import addCartridge
import asyncio
from cartridges import addCartridge, update_cartridge_field
from chat import handle_message
from datetime import datetime

openai.api_key = os.getenv('OPENAI_API_KEY', default=None)


file_chunks = {}

from sessionHandler import novaSession, novaConvo,current_loadout, current_config


async def handle_file_start(data):
  tempKey = data["tempKey"]
  file_chunks[tempKey] = {
    "metadata": data,   
    "chunks_received": 0,
    "content": [],
  }

async def handle_file_chunk(data):
  tempKey = data["tempKey"]
  file_chunks[tempKey]["chunks_received"] += 1
  # Decode the base64-encoded chunkContent
  decoded_chunk_content = base64.b64decode(data["chunkContent"])
  file_chunks[tempKey]["content"].append(decoded_chunk_content)

  # You could also process and store the chunk immediately in this step
  # instead of collecting all chunks in `file_chunks` and processing them later

async def handle_file_end(data):
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
        'loadout': file_metadata['loadout'],
        'tempKey': file_metadata['tempKey'],
        'document_type': file_metadata['document_type'],
    }

    sessionID = data['sessionID']
    client_loadout = None
    if sessionID in current_loadout:
        client_loadout = current_loadout[sessionID]
        
    file_content = data['file_content']

    file_name = data['file_name']
    file_type = data['file_type']
    loadout = data['loadout']

    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=file_name)
    temp_file.write(file_content)

    convoID = novaSession[sessionID]['convoID']
    await handle_message(convoID, 'file recieved', 'system', 'system', None,0, meta = 'terminal')


    if file_type == 'application/pdf':
       print('pdf found')
    #    // await handlePDF(data, client_loadout)
    elif file_type == 'text/plain':
        print('text found')
       # await handleText(data, client_loadout)
    elif file_type == 'application/vnd.openxmlformats-officedocument.wordprocessingml.document':
        print('docx found')
    elif file_type == 'video/mp4':
       await handle_video_file(temp_file, file_metadata['file_name'], sessionID, loadout)
    elif file_type == 'video/quicktime':
        print('video found')
        await handle_video_file(temp_file, file_metadata['file_name'], sessionID, loadout)
    elif file_type == 'audio/mpeg':
        print('audio found')
        await handle_audio_file(temp_file, file_metadata['file_name'], sessionID, loadout)
    # temp_file.close()

    del file_chunks[tempKey]

async def handle_video_file(file, name, sessionID, loadout):
    clip = VideoFileClip(file.name)
    audio_temp = tempfile.NamedTemporaryFile(delete=True, suffix=".mp3")
    clip.audio.write_audiofile(audio_temp.name)
    await handle_audio_file(audio_temp, name, sessionID, loadout)
    audio_temp.close()

async def handle_audio_file(file, name, sessionID, loadout):
    print(file.name)
    audio = AudioSegment.from_mp3(file.name)

    avg_loudness = audio.dBFS
    silence_thresh = avg_loudness  # Consider adjusting this if needed

    chunks = split_on_silence(audio, min_silence_len=1000, silence_thresh=silence_thresh, keep_silence=1000, seek_step=1)
    transcriptions = []
    chunk_time_ms = 0  # initial start time

    cartVal = {
        'label' : name + ' transcript',
        # 'text' : str(transcriptions),
        'type' : 'note',
        'enabled' : True,
    }

    convoID = novaSession[sessionID]['convoID']
    await handle_message(convoID, name + ' transcript created', 'system', 'system', None,0, meta = 'terminal')
    cartKey = await addCartridge(cartVal, sessionID, loadout )
    transcript_text = ''

    for chunk in chunks:
        with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as chunk_file:
            chunk.export(chunk_file.name, format='mp3')
            chunk_file.seek(0)  # Rewind the file pointer to the beginning of the file
            transcript =  openai.Audio.transcribe('whisper-1', chunk_file)
            
            print(transcript)
            transcript_text +=  str(chunk_time_ms) + 'ms:  ' + transcript['text'] + '\n' + 'Length: ' + str(len(chunk)) +'ms'+ '\n\n'
            await handle_message(convoID, str(chunk_time_ms) + 'ms:  ' + transcript['text'] + '\n' + 'Length: ' + str(len(chunk)) +'ms', 'system', 'system',  None,0, meta = 'terminal')

            transcriptions.append({
                'start_time': chunk_time_ms,
                'end_time': chunk_time_ms + len(chunk),
                'transcript': transcript
            })

            payload = {
                'sessionID': sessionID,
                'cartKey' : cartKey,
                'fields':
                        {'text': transcript_text}
                        }
            loadout = current_loadout[sessionID]
            await update_cartridge_field(payload, loadout, True)      
            chunk_time_ms += len(chunk)  # increment by the length of the chunk
            # os.unlink(chunk_file.name)  # Remove the temporary file
            

    # print(transcriptions)
    print('transcriptions complete')
    return transcriptions