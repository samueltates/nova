from moviepy.editor import VideoFileClip, concatenate_videoclips, concatenate_audioclips, ImageClip, vfx
import json
from moviepy.video.VideoClip import ColorClip
from datetime import datetime
from quart import websocket,  request
from appHandler import app, websocket
import tempfile
from file_handling.s3 import write_file, read_file
import openai
import os
import requests
import cv2
import ffmpeg

import subprocess
import shlex
import json

openai.api_key = os.getenv('OPENAI_API_KEY', default=None)


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