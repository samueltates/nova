from moviepy.editor import VideoFileClip, concatenate_videoclips, concatenate_audioclips, ImageClip
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

openai.api_key = os.getenv('OPENAI_API_KEY', default=None)


async def  split_video(edit_plan, video_file):
    print('splitting video' + video_file + 'with edit plan' + str(edit_plan)) 
    file = read_file(video_file)
    processed_file = tempfile.NamedTemporaryFile(suffix=".mp4", delete=False)
    processed_file.write(file)
    processed_file.close()

    clip = VideoFileClip(processed_file.name)
    final_audio = []
    final_video = []

    # main_cuts = []
    # if 'main_cuts' in edit_plan:
    #     for cut in edit_plan['main_cuts']:
            

    for seq in edit_plan['final_edit']['video']:
        cut_key = 'cut_' + str(seq['main_cut'])
        print(f'Processing {cut_key}')
        start, end = edit_plan['main_cuts'][cut_key]['start'], edit_plan['main_cuts'][cut_key]['end']
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

            # image = cv2.resize(image, (int(clip1.size[0]*image.shape[0]/clip1.size[1]), image.shape[0]))

            resized_image = cv2.resize(image, (image.shape[1] * clip_dimensions[0]//image.shape[0], clip_dimensions[0]))
            print(f'Resized image size: {resized_image.shape}')

            start_x = (resized_image.shape[1] - clip_dimensions[1]) // 2
            print(f'Start x-value for cropping: {start_x}')

            resized_cropped_image = resized_image[:, start_x:start_x+clip_dimensions[1]]
            cv2.imwrite(temp_image.name, image)

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
        audio_clip = clip.audio

    for seq in edit_plan['final_edit']['audio']:
        cut_key = 'cut_' + str(seq)
        start, end = edit_plan['main_cuts'][cut_key]['start'], edit_plan['main_cuts'][cut_key]['end']
        final_audio.append(audio_clip.subclip(start, end))

    
    final_clip = concatenate_videoclips(final_video)
    final_clip.audio = concatenate_audioclips(final_audio)
    file_to_send =  tempfile.NamedTemporaryFile(suffix=".mp4", delete=False)
    final_clip.write_videofile(file_to_send.name, fps=24, codec='libx264', audio_codec='aac')
    # final_clip.write_videofile("my_concatenation.mp4", fps=24, codec='libx264', audio_codec='aac')
    await websocket.send(json.dumps({'event': 'video_ready', 'payload': {'video_name': file_to_send.name}}))
    return final_clip   

