
import openai
import os
import tempfile
import asyncio
import json

from moviepy.editor import VideoFileClip
from pydub import AudioSegment
from pydub.silence import split_on_silence

from core.cartridges import  update_cartridge_field

from file_handling.s3 import read_file
from tools.debug import eZprint



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
    min_silence_len = 500

    chunks = split_on_silence(audio, min_silence_len=min_silence_len, silence_thresh=silence_thresh, keep_silence=True, seek_step=1)

    chunk_time_ms = 0  # initial start time  
    transcript_text = 'Transcription: \n\n'
    payload = {
        'sessionID': sessionID,
        'cartKey' : cartKey,
        'fields':
                {'text':transcript_text }
                }

    await update_cartridge_field(payload, convoID, loadout, True)    

    chunkID = 0
    tasks = []

    for chunk in chunks:
        eZprint(f"chunk {chunkID} length {len(chunk)} and start time {chunk_time_ms}", ['FILE_HANDLING', 'TRANSCRIBE'])
        task = asyncio.create_task(transcribe_chunk(chunk, chunk_time_ms, chunkID))
        chunk_time_ms += len(chunk)  # increment by the length of the chunk
        tasks.append(task)
        chunkID += 1

    results = await asyncio.gather(*tasks)
    results.sort(key=lambda x: x['chunkID'])
    end = ''
    for result in results:
        eZprint(f"chunk {result['chunkID']} start {result['start']} end {result['end']} text {result['transcript']['text']}", ['FILE_HANDLING', 'TRANSCRIBE'])
        start = result['start']
        end = result['end']
        transcript_text += f"[{start}] {result['transcript']['text']} \n\n"
    # transcript text end time stap
    transcript_text += f"[{end}] End of transcription"

    payload = {
            'sessionID': sessionID,
            'cartKey' : cartKey,
            'fields':
                {
                'text': transcript_text,
                'json' : json.dumps({'transcript': results})
                }
            }
    await update_cartridge_field(payload,convoID, loadout, True)
    return transcript_text

async def transcribe_chunk(chunk, chunk_time_ms, chunkID = 0):
        with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as chunk_file:
            chunk.export(chunk_file.name, format='mp3')
            eZprint(f'Saved to:{chunk_file.name} with start {chunk_time_ms} and length {len(chunk)}', ['TRANSCRIBE_CHUNK']) # Confirm file path
            chunk_file.seek(0)  # Rewind the file pointer to the beginning of the file
            #write to local as audio file
            # loop = asyncio.get_event_loop()
            # transcript =             
            transcript =  openai.Audio.transcribe('whisper-1', chunk_file)
            start = await convert_ms_to_hh_mm_ss(chunk_time_ms)
            end = await convert_ms_to_hh_mm_ss(chunk_time_ms + len(chunk))
            transcription = {
                'chunkID': chunkID,
                'start': start,
                'end': end,
                'transcript': transcript
            }
            os.remove(chunk_file.name)
            return transcription


async def convert_ms_to_hh_mm_ss(ms):
    seconds, ms = divmod(ms, 1000)
    minutes, seconds = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    return ':'.join([str(hours).zfill(2), str(minutes).zfill(2), str(seconds).zfill(2)]) + '.' + str(ms).zfill(3) 