from moviepy.editor import VideoFileClip, concatenate_videoclips, concatenate_audioclips, ImageClip, vfx, CompositeVideoClip, TextClip
import json
from moviepy.video.VideoClip import ColorClip
from datetime import datetime
from quart import websocket,  request
import tempfile
import openai
import os
import requests
import cv2
import ffmpeg
import asyncio

import subprocess
import shlex
import json

from session.appHandler import app, websocket
from core.cartridges import addCartridge, update_cartridge_field
from file_handling.s3 import write_file, read_file
from file_handling.image_handling import generate_temp_image
from tools.debug import eZprint, eZprint_anything


openai.api_key = os.getenv('OPENAI_API_KEY', default=None)




async def overlay_b_roll(main_video_cartridge, b_roll_to_overlay, sessionID, convoID, loadout):
    DEBUG_KEYS = ['OVERLAY']
    eZprint_anything(['Overlaying video',main_video_cartridge], ['OVERLAY'], line_break=True)
    main_video_key = main_video_cartridge['aws_key']
    video_file = await read_file(main_video_key)

    processed_file = tempfile.NamedTemporaryFile(suffix=".mp4", delete=False)
    processed_file.write(video_file)
    processed_file.close()
    composites = []



    clip = VideoFileClip(processed_file.name)
    rotated = await is_rotated(processed_file.name)

    if rotated:
        clip = clip.resize(clip.size[::-1])

    clip_dimensions = clip.get_frame(0).shape
    layout = await determine_orientation(clip_dimensions)

    composites.append(clip)
    
    tasks = []
    for b_roll in b_roll_to_overlay:
        prompt = b_roll['prompt']        
        task = asyncio.create_task(generate_temp_image(prompt))
        tasks.append(task)
    images = await asyncio.gather(*tasks)
    print('images', images)
    counter = 0
    for b_roll in b_roll_to_overlay:
        processed_image = images[counter]
        counter += 1
        if processed_image :

            start, end = b_roll['start'], b_roll['end']
            start = datetime.strptime(start, '%H:%M:%S.%f')
            end = datetime.strptime(end, '%H:%M:%S.%f')
            #get as  time delta
            duration = end - start
            duration = duration.total_seconds()
            start_delta = start - datetime.strptime('00:00:00.000', '%H:%M:%S.%f')
            start = start_delta.total_seconds()
            
            image = cv2.imread(processed_image.name)

            if layout == 'horizontal':
                # Resize image based on orientation of clip
                resized_image = cv2.resize(image, (clip_dimensions[1], clip_dimensions[1]*image.shape[0]//image.shape[1]))
            else:
                resized_image = cv2.resize(image, (clip_dimensions[0]*image.shape[1]//image.shape[0], clip_dimensions[0]))

            # print('Resized image size:', resized_image.shape)
            # print('Resized image size:', resized_image.shape)
            # # Crop excess width/height if necessary
            start_x = max(0, (resized_image.shape[1] - clip_dimensions[1]) // 2)
            start_y = max(0, (resized_image.shape[0] - clip_dimensions[0]) // 2)
            # resized_cropped_image = resized_image[start_y:start_y+clip_dimensions[0], start_x:start_x+clip_dimensions[1]]


            resized_image = cv2.cvtColor(resized_image, cv2.COLOR_BGR2RGB)

            cv2.imwrite(processed_image.name, resized_image)

            image_clip = ImageClip(resized_image)
            image_clip = image_clip.set_duration(duration)
            image_clip = image_clip.set_start(start)
            #set default position
            image_clip = image_clip.set_position('center')

            # if 'zoom' in media:
            #     start_zoom = float(media['zoom'].get('start_size', 1))
            #     end_zoom = float(media['zoom'].get('end_size', start_zoom))
            #     image_clip = image_clip.resize(lambda t: start_zoom + ((t / duration) * (end_zoom - start_zoom)))


            if 'position' in b_roll:
                eZprint('position found', DEBUG_KEYS)
                image_clip = image_clip.set_position(b_roll['position'])

            if 'fade' in b_roll:
                fadein_duration = float(b_roll['fade'].get('fadein', 0))
                fadeout_duration = float(b_roll['fade'].get('fadeout', 0))
                if fadein_duration:
                    image_clip = image_clip.crossfadein(fadein_duration)
                if fadeout_duration:
                    image_clip = image_clip.crossfadeout(fadeout_duration)
            # if 'position' in media:
            #     start_pos = float(media['position'].get('start', 'center'))
            #     end_pos = float(media['position'].get('end', start_pos))
            #     image_clip = image_clip.set_position(lambda t: ((1-t)*start_pos[0] + t*end_pos[0], (1-t)*start_pos[1] + t*end_pos[1]))

            if 'pan' in b_roll:
                # pan_from = float(media['pan'].get('pan_from', 0)) * (start_x)
                # pan_to = float(media['pan'].get('pan_to', 0)) * (start_x)
                direction = b_roll['pan']
                if direction == 'left':
                    image_clip = image_clip.set_position(lambda t: (0 + ((t / duration) * (-start_x)), 'center'))
                elif direction == 'right':
                    image_clip = image_clip.set_position(lambda t: ((-start_x*2) + ((t / duration) * (start_x)), 'center'))


                # image_clip = image_clip.set_position(lambda t: (pan_from + ((t / duration) * (pan_from - pan_to)), 'center'))
                # print('panning from', pan_from, 'to', pan_to)

            composites.append(image_clip)
    
    json_object = None
    transcript_object = None
    transcript_lines = None

    if main_video_cartridge.get('json', None):
        json_object = json.loads(main_video_cartridge['json'])

    if json_object:
        transcript_object = json_object.get('transcript', None)        
        eZprint_anything([transcript_object], ['OVERLAY'])

    if transcript_object:
        transcript_lines = transcript_object.get('lines', None)

    if transcript_lines:
        transcript_lines.sort(key=lambda x: x['chunkID'])
        for line in transcript_lines:
            eZprint_anything([line], ['OVERLAY'])
            start = line['start']
            end = line['end']

            start = datetime.strptime(start, '%H:%M:%S.%f')
            end = datetime.strptime(end, '%H:%M:%S.%f')
            #get as  time delta
            duration = end - start
            duration = duration.total_seconds()
            text = line.get('text', '')

            ## splits lines up by appostrophe or and divides timestamp and time between them based on sections
    
            eZprint_anything([text], ['OVERLAY', 'TRANSCRIBE'])
            ## checks if any line has more than 5 words and if so splits it up into sections

            # lines_split_by_apostophe = []
            
            # for new_line in lines_split_by_word_count:
            #     eZprint('checking for apostrophe', ['OVERLAY', 'TRANSCRIBE'])
            #     new_line_sections = new_line.split(',')
            #     eZprint_anything([new_line_sections], ['OVERLAY'], line_break=True)
            #     if len(new_line_sections) > 1:
            #         eZprint('found apostrophe', ['OVERLAY', 'TRANSCRIBE'])
            #         for new_line_section in new_line_sections:
            #             if new_line_section != '':
            #                 lines_split_by_apostophe.append(new_line_section)
            #     else:
            #         lines_split_by_apostophe.append(new_line)
            
            # eZprint('running line list', ['OVERLAY', 'TRANSCRIBE'])
            # eZprint_anything([lines_split_by_apostophe], ['OVERLAY'], line_break=True)
                        
            # get total characters in line by finding how many newlines were added, 
            lines_split_by_word_count = []
            total_lines = 0
            if len(text.split(' ')) > 2:
                eZprint('splitting line as over 2', ['OVERLAY', 'TRANSCRIBE'])
                split_text = text.split(' ')
                word_count = len(split_text)
                lines_needed = word_count / 2
                # round up to int
                lines_needed = int(lines_needed) 

                eZprint(f'lines needed {lines_needed}', ['OVERLAY', 'TRANSCRIBE'])
                if lines_needed > 1:    
                    wpl = int(len(split_text) / lines_needed)
                    eZprint(f'words per line {wpl}', ['OVERLAY', 'TRANSCRIBE'])
                    for i in range(lines_needed):
                        new_line = ' '.join(split_text[i * wpl:(i * wpl)+wpl])
                        # lines_split_by_word_count.append(new_line)
                        ## if last line add the rest of the words
                        if i == lines_needed - 1:
                            new_line += " "
                            new_line += ' '.join(split_text[(i * wpl)+wpl:])
                        lines_split_by_word_count.append(new_line)
                        total_lines += 1
                else:
                    lines_split_by_word_count.append(text)
                    total_lines += 1
            else:
                lines_split_by_word_count.append(text)
                total_lines += 1
          
            eZprint_anything([lines_split_by_word_count], ['OVERLAY', 'TRANSCRIBE'], line_break=True)

            
            line_characters = len(text) - (len(lines_split_by_word_count) - len(lines_split_by_word_count) ) + 1
            start_delta = start - datetime.strptime('00:00:00.000', '%H:%M:%S.%f')
            start = start_delta.total_seconds()
            running_progress = start

            eZprint(f'line characters {line_characters}', ['OVERLAY', 'TRANSCRIBE'])

            # for line in lines_split_by_apostophe:
            #     eZprint_anything([line], ['OVERLAY'], line_break=True)
            #     # line_section_duration = duration / len(line_sections)

            #     if line != '':

            if os.getenv('DEBUG_SPLIT_BY_WORDS', default=None) == 'True':
                line_percent = 1/total_lines

            for line in lines_split_by_word_count:
                if line != '':
                    if not os.getenv('DEBUG_SPLIT_BY_WORDS', default=None) == 'True':
                        line_percent = len(line) / line_characters
                    line_duration = duration * line_percent
                    line_start = running_progress
                    line_end = line_start + line_duration
                    # duration_modifier = line_duration * .1
                    running_progress = line_end
                    text = line.strip()
                    size = clip_dimensions[1]* .8, None
                    # if os.getenv('DEBUG_LABEL', default=None) == 'True':
                    #     text_clip = TextClip(text.upper(), size = size, fontsize=50, color='white', kerning = 5, method='label', align='west', font = 'Oswald-SemiBold', stroke_color='black', stroke_width=1)
                    # else:

                    ## set font size dynamically based on screen resolution

                    screen_mod = (size[0] + size[0]) / (1920+1080)
                    font_size = int(os.getenv('DEBUG_FONT_SIZE', default=50))
                    font_size = font_size * screen_mod
                    stroke_width = 4 * screen_mod
                    interline = -20 * screen_mod
                    kerning = 4 * screen_mod

                    text_clip = TextClip(text.upper(), size = size, fontsize=font_size, color='white', kerning = kerning, method='caption', align='west', font = 'Oswald-Bold', stroke_color='black', stroke_width=stroke_width, interline=interline)
                    text_clip = text_clip.set_duration(line_duration )
                    text_clip = text_clip.set_start(line_start )
                    # set position so its centered on x and 80% down on y
                    text_clip = text_clip.set_position((.1, 0.7), relative=True)
                    eZprint(f'line start {line_start} line end {line_end} line duration {line_duration} line percent {line_percent}', ['OVERLAY', 'TRANSCRIBE'])
                    composites.append(text_clip)
   
    compositeClip = CompositeVideoClip(composites, size=clip.size)
    compositeClip.audio = clip.audio
    file_to_send =  tempfile.NamedTemporaryFile(suffix=".mp4", delete=False)
    write_loop = asyncio.get_event_loop()
    await write_loop.run_in_executor(None, lambda: compositeClip.write_videofile(file_to_send.name,  remove_temp=True, codec='libx264', audio_codec='aac'))
    # compositeClip.write_videofile(file_to_send.name,  remove_temp=True, codec='libx264', audio_codec='aac')
    await websocket.send(json.dumps({'event': 'video_ready', 'payload': {'video_name': file_to_send.name}}))
    # final_clip.write_videofile("my_concatenation.mp4", fps=24, codec='libx264', audio_codec='aac')
       
    name = main_video_cartridge['label'] + '_overlayed.mp4'
    cartVal = {
        'label' : name,
        # 'text' : str(transcriptions),
        # 'description' : 'Image generated by openAI with prompt: ' + prompt,
        'fileName' : file_to_send.name,
        'extension' : 'video/mp4',
        # 'media_url' : url,
        'type' : 'media',
        'enabled' : True,
    }

    cartKey = await addCartridge(cartVal, sessionID, loadout, convoID )
    aws_key = cartKey + '.mp4'
    url = await write_file(file_to_send.file, aws_key) 

    await update_cartridge_field(
        {   
            'sessionID': sessionID, 
            'cartKey' : cartKey, 
            'fields': {
                'media_url': url, 
                'aws_key': aws_key
            }
        }, convoID, loadout, True )
    

    eZprint(f'file {name} written to {url}', ['OVERLAY'])
    # file_to_send.close()
    compositeClip.close()
    return name


async def overlay_video(main_video_cartridge, media_to_overlay, text_to_overlay, sessionID, convoID, loadout):

    eZprint_anything(['Overlaying video',main_video_cartridge], ['OVERLAY'], line_break=True)
    main_video_key = main_video_cartridge['aws_key']
    video_file = await read_file(main_video_key)
    
    processed_file = tempfile.NamedTemporaryFile(suffix=".mp4", delete=False)
    processed_file.write(video_file)
    processed_file.close()
    composites = []
    clip = VideoFileClip(processed_file.name)
    rotated = await is_rotated(processed_file.name)

    if rotated:
        clip = clip.resize(clip.size[::-1])

    clip_dimensions = clip.get_frame(0).shape
    layout = await determine_orientation(clip_dimensions)

    composites.append(clip)
    
    # if 'transcript' in main_video_cartridge:
    #     for line in 

    for media in media_to_overlay:
        print('Processing media:', media)
        media_key = media.get('aws_key', None)
        if media_key is None:
            continue    
        media_file = await read_file(media_key)
        processed_media = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
        processed_media.write(media_file)
        processed_media.close()

        start, end = media['start'], media['end']
        start = datetime.strptime(start, '%H:%M:%S.%f')
        end = datetime.strptime(end, '%H:%M:%S.%f')
        #get as  time delta
        duration = end - start
        duration = duration.total_seconds()
        start_delta = start - datetime.strptime('00:00:00.000', '%H:%M:%S.%f')
        start = start_delta.total_seconds()
        
        image = cv2.imread(processed_media.name)
        print(f'Initial image size: {image.shape}')

        if layout == 'horizontal':
            # Resize image based on orientation of clip
            resized_image = cv2.resize(image, (clip_dimensions[1], clip_dimensions[1]*image.shape[0]//image.shape[1]))
        else:
            resized_image = cv2.resize(image, (clip_dimensions[0]*image.shape[1]//image.shape[0], clip_dimensions[0]))

        # print('Resized image size:', resized_image.shape)
        # print('Resized image size:', resized_image.shape)
        # # Crop excess width/height if necessary
        start_x = max(0, (resized_image.shape[1] - clip_dimensions[1]) // 2)
        start_y = max(0, (resized_image.shape[0] - clip_dimensions[0]) // 2)
        # resized_cropped_image = resized_image[start_y:start_y+clip_dimensions[0], start_x:start_x+clip_dimensions[1]]

        print('Start x-value for cropping:', start_x)
        print('Start y-value for cropping:', start_y)

        # # Writing image
        # print('Writing temporary image')
        # resized_cropped_image = cv2.cvtColor(resized_cropped_image, cv2.COLOR_BGR2RGB)

        resized_image = cv2.cvtColor(resized_image, cv2.COLOR_BGR2RGB)

        cv2.imwrite(processed_media.name, resized_image)

        image_clip = ImageClip(resized_image)
        image_clip = image_clip.set_duration(duration)
        image_clip = image_clip.set_start(start)
        #set default position
        image_clip = image_clip.set_position('center')

        # if 'zoom' in media:
        #     start_zoom = float(media['zoom'].get('start_size', 1))
        #     end_zoom = float(media['zoom'].get('end_size', start_zoom))
        #     image_clip = image_clip.resize(lambda t: start_zoom + ((t / duration) * (end_zoom - start_zoom)))


        if 'position' in media:
            print('position found')
            image_clip = image_clip.set_position(media['position'])

        if 'fade' in media:
            fadein_duration = float(media['fade'].get('fadein', 0))
            fadeout_duration = float(media['fade'].get('fadeout', 0))
            if fadein_duration:
                image_clip = image_clip.crossfadein(fadein_duration)
            if fadeout_duration:
                image_clip = image_clip.crossfadeout(fadeout_duration)
        # if 'position' in media:
        #     start_pos = float(media['position'].get('start', 'center'))
        #     end_pos = float(media['position'].get('end', start_pos))
        #     image_clip = image_clip.set_position(lambda t: ((1-t)*start_pos[0] + t*end_pos[0], (1-t)*start_pos[1] + t*end_pos[1]))

        if 'pan' in media:
            # pan_from = float(media['pan'].get('pan_from', 0)) * (start_x)
            # pan_to = float(media['pan'].get('pan_to', 0)) * (start_x)
            direction = media['pan']
            if direction == 'left':
                image_clip = image_clip.set_position(lambda t: (0 + ((t / duration) * (-start_x)), 'center'))
            elif direction == 'right':
                image_clip = image_clip.set_position(lambda t: ((-start_x*2) + ((t / duration) * (start_x)), 'center'))


            # image_clip = image_clip.set_position(lambda t: (pan_from + ((t / duration) * (pan_from - pan_to)), 'center'))
            # print('panning from', pan_from, 'to', pan_to)

        composites.append(image_clip)
    

    if text_to_overlay:
        for text in text_to_overlay:

            start, end = text.get('start',0), text.get('end',0)
            size = text.get('size', (1,.5))
            size_x = float(size[0])
            # size_y = float(size[1])
            font_size = int(text.get('font_size', 70))
            text_value = text.get('text', '')
            font = text.get('font', 'Arial-Bold')
            position = text.get('position', 'bottom')

            start = datetime.strptime(start, '%H:%M:%S.%f')
            end = datetime.strptime(end, '%H:%M:%S.%f')
            #get as  time delta
            duration = end - start
            duration = duration.total_seconds()
            start_delta = start - datetime.strptime('00:00:00.000', '%H:%M:%S.%f')
            start = start_delta.total_seconds()
            size = clip_dimensions[1], None
            text_clip = TextClip(text_value, size = size, fontsize=font_size, color='white', method='caption', align='center', font = 'DejaVu-Sans')

            text_clip = text_clip.set_duration(duration)
            text_clip = text_clip.set_start(start)
            text_clip = text_clip.set_position(position)
            composites.append(text_clip)

    compositeClip = CompositeVideoClip(composites, size=clip.size)
    file_to_send =  tempfile.NamedTemporaryFile(suffix=".mp4", delete=False)
    compositeClip.write_videofile(file_to_send.name, fps=24, codec='libx264', audio_codec='aac')
    # final_clip.write_videofile("my_concatenation.mp4", fps=24, codec='libx264', audio_codec='aac')
    await websocket.send(json.dumps({'event': 'video_ready', 'payload': {'video_name': file_to_send.name}}))
       
    name = main_video_cartridge['label'] + '_overlayed.mp4'
    cartVal = {
        'label' : name,
        # 'text' : str(transcriptions),
        # 'description' : 'Image generated by openAI with prompt: ' + prompt,
        'fileName' : file_to_send.name,
        'extension' : 'video/mp4',
        # 'media_url' : url,
        'type' : 'media',
        'enabled' : True,
    }

    cartKey = await addCartridge(cartVal, sessionID, loadout, convoID )
    aws_key = cartKey + '.mp4'
    url = await write_file(file_to_send.file, aws_key) 

    await update_cartridge_field(
        {   
            'sessionID': sessionID, 
            'cartKey' : cartKey, 
            'fields': {
                'media_url': url, 
                'aws_key': aws_key
            }
        }, convoID, loadout, True )
    

    eZprint(f'file {name} written to {url}', ['OVERLAY'])
    # file_to_send.close()
    compositeClip.close()
    return name

async def split_video(edit_plan, video_file):
    print('splitting video' + video_file + 'with edit plan' + str(edit_plan)) 
    file = await read_file(video_file)
    processed_file = tempfile.NamedTemporaryFile(suffix=".mp4", delete=False)
    processed_file.write(file)
    processed_file.close()

    clip = VideoFileClip(processed_file.name)
    rotated = await is_rotated(processed_file.name)
    if rotated:
        clip = clip.resize(clip.size[::-1])

    # clip.write_videofile('before-edit.mp4', fps=24, codec='libx264', audio_codec='aac')

    final_audio = []
    final_video = []

    # main_cuts = []
    # if 'main_cuts' in edit_plan:
    #     for cut in edit_plan['main_cuts']:
            
    audio_clip = clip.audio

    for seq in edit_plan['final_edit']['video']:
        cut_key = 'cut_' + str(seq['main_cut'])
        print(f'Processing {cut_key}')
        start, end = edit_plan['main_cuts'][cut_key]['start'], edit_plan['main_cuts'][cut_key]['end']
        final_audio.append(audio_clip.subclip(start, end))

        if seq['b_roll']:
            #split the main cut at 'cut_at'
            cut_at = seq['cut_at']
            clip1 = clip.subclip(start, cut_at)
            # clip2 = clip.subclip(cut_at, end)
            clip_dimensions = clip.get_frame(0).shape
    
            print(f'Clip 1 size: {clip1.size}')
            print(f'clip dimensions: {clip_dimensions}')
            
            # Calculate B-roll duration
            ## get end and cut as datetime so can subtract
            end = datetime.strptime(end, '%H:%M:%S.%f')
            cut_at = datetime.strptime(cut_at, '%H:%M:%S.%f')
            
            # clip_size = clip1.size
            response = openai.Image.create(
            prompt=seq['b_roll'],
            n=1,
            size='1024x1024'
            )
            image_url = response['data'][0]['url']
            print(f'Image URL: {image_url}')
            response = requests.get(image_url)

            #get image from URL
            temp_image = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
            temp_image.write(response.content)

            image = cv2.imread(temp_image.name)
            print(f'Initial image size: {image.shape}')

            # Determine orientation of clip


           # Resize image based on orientation of clip
            if await determine_orientation(clip_dimensions) == 'horizontal':
                print('Horizontal clip')
       # dimensions switched for horizontal clip
                # Aspect ratio of image should be clip_hight/clip_width to match with clip dimensions.
                resized_image = cv2.resize(image, (clip_dimensions[1], clip_dimensions[1]*image.shape[0]//image.shape[1]))
            else:
                print('Vertical clip')
                resized_image = cv2.resize(image, (clip_dimensions[0]*image.shape[1]//image.shape[0], clip_dimensions[0]))

            print('Resized image size:', resized_image.shape)
            # Crop excess width/height if necessary
            start_x = max(0, (resized_image.shape[1] - clip_dimensions[1]) // 2)
            start_y = max(0, (resized_image.shape[0] - clip_dimensions[0]) // 2)
            resized_cropped_image = resized_image[start_y:start_y+clip_dimensions[0], start_x:start_x+clip_dimensions[1]]

            print('Start x-value for cropping:', start_x)
            print('Start y-value for cropping:', start_y)

            # Writing image
            print('Writing temporary image')
            resized_cropped_image = cv2.cvtColor(resized_cropped_image, cv2.COLOR_BGR2RGB)

            cv2.imwrite(temp_image.name, resized_cropped_image)

            b_roll_duration = end - cut_at
            b_roll_duration = b_roll_duration.total_seconds()
#           #set image as video clip 
            # b_roll = VideoFileClip(temp_image.name, has_mask=True).set_duration(b_roll_duration)
            b_roll = ImageClip(resized_cropped_image, duration=b_roll_duration)
            b_roll = b_roll.resize(height=clip1.size[1])
            # b_roll = b_roll.resize(height=clip_size[1]) 
            # Create a blank color placeholder
            # b_roll = ColorClip((clip.size), col=(0,0,0), duration=b_roll_duration)
            #append main cut until 'cut_at', followed by B-roll and rest of the main cut
            final_video.append(concatenate_videoclips([clip1, b_roll]))
        else:
            final_video.append(clip.subclip(start, end))
    #     audio_clip = clip.audio

    # for seq in edit_plan['final_edit']['audio']:
    #     cut_key = 'cut_' + str(seq)
    #     start, end = edit_plan['main_cuts'][cut_key]['start'], edit_plan['main_cuts'][cut_key]['end']
    #     final_audio.append(audio_clip.subclip(start, end))

    
    final_clip = concatenate_videoclips(final_video)
    final_clip.audio = concatenate_audioclips(final_audio)
    file_to_send =  tempfile.NamedTemporaryFile(suffix=".mp4", delete=False)
    final_clip.write_videofile(file_to_send.name, fps=24, codec='libx264', audio_codec='aac')
    # final_clip.write_videofile("my_concatenation.mp4", fps=24, codec='libx264', audio_codec='aac')
    await websocket.send(json.dumps({'event': 'video_ready', 'payload': {'video_name': file_to_send.name}}))

    file_to_send.close()

    # return final_clip   


async def determine_orientation(clip_dimensions):
    
    # probe = ffmpeg.probe(video_file)
    # rotate_code = next((stream['tags']['rotate'] for stream in probe['streams'] if 'rotate' in stream['tags']), None)       
    # 

    print(f'clip dimensions: {clip_dimensions}')   

    if clip_dimensions[0] > clip_dimensions[1]:
        print('vertical clip' + str(clip_dimensions))
        return 'vertical'
    elif clip_dimensions[0] == clip_dimensions[1]:
        print('Square clip' + str(clip_dimensions))
        return 'square'
    else:
        print('Horizontal clip' + str(clip_dimensions))
        return 'horizontal'


async def is_rotated( file_path):
    rotation = await get_rotation(file_path)
    print('Rotation:', rotation)
    if rotation == 90:  # If video is in portrait
        return True
    elif rotation == -90:
        return True
    elif rotation == 270:  # Moviepy can only cope with 90, -90, and 180 degree turns
        return True
    elif rotation == -270:
        return True
    elif rotation == 180:
        return True
    elif rotation == -180:
        return True
    return False

async def get_rotation(source):
    # clip = VideoFileClip('IMG_3561.mov')
    cmd = "ffprobe -loglevel error -select_streams v:0 -show_entries side_data=rotation -of default=nw=1:nk=1 "
    args = shlex.split(cmd)
    args.append(source)
    print(args)
    ffprobe_output = subprocess.check_output(args).decode('utf-8')
    print(ffprobe_output)
    if len(ffprobe_output) > 0:  # Output of cmdis None if it should be 0
        ffprobe_output = json.loads(ffprobe_output)
        rotation = ffprobe_output
    else:
        rotation = 0

    print(rotation)
    return rotation