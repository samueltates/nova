from moviepy.editor import VideoFileClip, concatenate_videoclips, concatenate_audioclips
import json
from moviepy.video.VideoClip import ColorClip
from datetime import datetime
from quart import websocket,  request
from appHandler import app, websocket
import tempfile


async def split_video(edit_plan, video_file):
    clip = VideoFileClip(video_file)
    final_audio = []
    final_video = []

    # main_cuts = []
    # if 'main_cuts' in edit_plan:
    #     for cut in edit_plan['main_cuts']:
            

    for seq in edit_plan['final_edit']['video']:
        cut_key = 'cut_' + str(seq['main_cut'])
        print(cut_key)
        start, end = edit_plan['main_cuts'][cut_key]['start'], edit_plan['main_cuts'][cut_key]['end']
        if seq['b_roll']:
            #split the main cut at 'cut_at'
            cut_at = seq['cut_at']
            clip1 = clip.subclip(start, cut_at)
            # clip2 = clip.subclip(cut_at, end)
            # Calculate B-roll duration
            ## get end and cut as datetime so can subtract
            end = datetime.strptime(end, '%H:%M:%S.%f')
            cut_at = datetime.strptime(cut_at, '%H:%M:%S.%f')


            b_roll_duration = end - cut_at
            b_roll_duration = b_roll_duration.total_seconds()
            # Create a blank color placeholder
            b_roll = ColorClip((clip.size), col=(0,0,0), duration=b_roll_duration)
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

