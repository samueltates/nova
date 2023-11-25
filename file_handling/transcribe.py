
import openai
import os
import tempfile
import asyncio
import json

from moviepy.editor import VideoFileClip
from pydub import AudioSegment
from pydub.silence import split_on_silence, detect_leading_silence, detect_nonsilent

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
    silence_thresh = avg_loudness + (avg_loudness * 0.2)
    min_silence_len = 500

    eZprint(f"silence thresh {silence_thresh} and min silence len {min_silence_len} from average loudness of {avg_loudness}", ['FILE_HANDLING', 'TRANSCRIBE'])


    chunks = split_on_silence(audio, min_silence_len=min_silence_len, silence_thresh=silence_thresh, keep_silence=True, seek_step=1)
    leading_silence = detect_leading_silence(audio, silence_threshold=silence_thresh, chunk_size=1)
    timestamps = detect_nonsilent(audio, min_silence_len=min_silence_len, silence_thresh=silence_thresh, seek_step=1)
    chunk_time_ms = 0
    transcript_text = f'\n{name} - Transcription: \n\n'
    # payload = {
    #     'sessionID': sessionID,
    #     'cartKey' : cartKey,
    #     'fields':
    #             {'text':transcript_text }
    #             }

    # await update_cartridge_field(payload, convoID, loadout, True)    
    chunk_time_ms = 0
    chunkID = 0
    tasks = []

    for chunk in chunks:
        timestamp = timestamps[chunkID]
        
        eZprint(f"chunk {chunkID} length {len(chunk)} and start time {timestamp[0]} and end time {timestamp[1] }", ['FILE_HANDLING', 'TRANSCRIBE'])
        #getting start and finish but adding a bit
        #this is with the actual start / finishes
        # task = asyncio.create_task(transcribe_chunk(chunk, timestamp[0], timestamp[1] , chunkID))

        if (os.getenv('DEBUG_TRANSCRIBE_NO_GAPS') == 'True'):
            start = chunk_time_ms
            end = chunk_time_ms + len(chunk)
            if chunkID == 0:
                start = int(leading_silence/ 2)
        elif (os.getenv('DEBUG_TRANSCRIBE_START_GAP') == 'True'):
            start = timestamp[0]
            end = chunk_time_ms + len(chunk)
        elif (os.getenv('DEBUG_TRANSCRIBE_START_END_GAP') == 'True'):
            start = timestamp[0]
            end = timestamp[1]
        else:
            ## currently my favourite, uses exact start, but clip end ...
            start = timestamp[0]
            end = chunk_time_ms + len(chunk)


        # if chunkID == len(chunks) - 1:
        task = asyncio.create_task(transcribe_chunk(chunk, start, end , chunkID))
        chunk_time_ms += len(chunk)
        
        tasks.append(task)
        chunkID += 1

    results = await asyncio.gather(*tasks)
    results.sort(key=lambda x: x['chunkID'])
    end = ''
    for result in results:
        eZprint(f"chunk {result['chunkID']} start {result['start']} end {result['end']} text {result['text']}", ['FILE_HANDLING', 'TRANSCRIBE'])
        start = result['start']
        end = result['end']
        transcript_text += f"{start} --> {end}\n{result['text']} \n\n"
    # transcript text end time stap
    transcript_text += f"[{end}] End of transcription"

    payload = {
            'sessionID': sessionID,
            'cartKey' : cartKey,
            'fields':
                {
                # 'text': transcript_text,
                'json' : json.dumps({
                    'transcript_text': {
                        'description' : 'Complete transcription  of ' + name,
                        'transcript_text' : transcript_text,
                        'minimised': False
                        },
                    'transcript_object':{
                        'description' : 'Transcription object lines ' + name,
                        'transcript_text' : transcript_text,
                        'lines' : results,
                        'minimised': True

                    } })
                }
            }
    await update_cartridge_field(payload,convoID, loadout, True)
    return transcript_text

async def transcribe_chunk(chunk, chunk_start, chunk_end, chunkID = 0):
        with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as chunk_file:
            chunk.export(chunk_file.name, format='mp3')


            eZprint(f'Saved to:{chunk_file.name} with start of {chunk_start} and length of {chunk_end, }', ['TRANSCRIBE_CHUNK']) # Confirm file path
            chunk_file.seek(0)  # Rewind the file pointer to the beginning of the file
            #write to local as audio file
            loop = asyncio.get_event_loop()
            transcript =  await loop.run_in_executor(None, lambda: openai.Audio.transcribe('whisper-1', chunk_file))
            start = await convert_ms_to_hh_mm_ss(chunk_start)
            end = await convert_ms_to_hh_mm_ss(chunk_end)
            transcription = {
                'chunkID': chunkID,
                'start': start,
                'end': end,
                'text': transcript['text']
            }
            eZprint(f"chunk {chunkID} start {start} end {end} text {transcript['text']}", ['FILE_HANDLING', 'TRANSCRIBE', 'DEBUG_TRANSCRIBE_CHUNK'])
            # write each audio chunk to temp folder as mp3 for analysis using time and transcript as title
            if os.getenv('DEBUG_TRANSCRIBE_CHUNK') == 'True':
                temp_chunk = tempfile.NamedTemporaryFile(suffix='.mp3', delete=False, prefix=f'{chunkID}_{start}_{end}_{transcript["text"]}')
                chunk.export(temp_chunk.name, format='mp3')
                temp_chunk.close()

            os.remove(chunk_file.name)
            return transcription


async def convert_ms_to_hh_mm_ss(ms):
    seconds, ms = divmod(ms, 1000)
    minutes, seconds = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    return ':'.join([str(hours).zfill(2), str(minutes).zfill(2), str(seconds).zfill(2)]) + '.' + str(ms).zfill(3) 