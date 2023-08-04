from moviepy.editor import VideoFileClip, concatenate_videoclips, concatenate_audioclips
import json

def split_video(main_cuts, audio_clips, b_roll, final_cuts, video_file):
    clip = VideoFileClip(video_file)
    final_audio = []
    final_video = []

    for cut in main_cuts:
        start, end = cut['start'], cut['end']
        final_video.append(clip.subclip(start, end))

    audio_clip = clip.audio

    for cut in final_cuts:
        start, end = cut['start'], cut['end']
        



    final_clip = concatenate_videoclips(final_video)
    final_clip.audio = concatenate_audioclips(final_audio)
    ## save final clip to disk
    final_clip.write_videofile("my_concatenation.mp4", fps=24, codec='libx264', audio_codec='aac')
    return final_clip

# example usage:
# main_cuts = [ {'start': '00:00:00', 'end': '00:01:00'}, {'start': '00:01:00', 'end': '00:03:00'} ]
# audio_cuts = [ {'start': '00:00:00', 'end': '00:01:00'}, {'start': '00:01:00', 'end': '00:03:00'} ]
# split_video(main_cuts, audio_cuts, 'my_video.mp4')
#'main_cuts': [{'cut_1': {'start': '0ms', 'end': '3313ms'}, 'cut_2': {'start': '3313ms', 'end': '7249ms'}, 'cut_3': {'start': '7249ms', 'end': '11515ms'}, 'cut_4': {'start': '11515ms', 'end': '14015ms'}, 'cut_5': {'start': '14015ms', 'end': '18924ms'}}], 'b_roll_needed': ['Close up of Bones', 'Footage from the wedding', 'B-roll of cat grooming', 'Outdoor footage of the bush'], 'final_edit': {'audio': [1, 2, 3, 4, 5], 'video': [{'main_cut': 1, 'cut_at': '1600ms', 'b_roll': 'Close up of Bones'}, {'main_cut': 2, 'cut_at': '5300ms', 'b_roll': 'Footage from the wedding'}, {'main_cut': 3, 'cut_at': '8400ms', 'b_roll': 'B-roll of cat grooming'}, {'main_cut': 4, 'cut_at': '13000ms', 'b_roll': 'Outdoor footage of the bush'}, {'main_cut': 5, 'cut_at': '17000ms', 'b_roll': ''}]}}

def parse_and_edit(edit_plan_json, video_file):
    edit_plan = json.loads(edit_plan_json)
    main_cuts = edit_plan['main_cuts']
    audio_cuts = edit_plan['audio_cuts']

    return split_video(main_cuts, audio_cuts, video_file)


# updated usage:
# edit_plan_json = '<edit_plan_stringified_json_here>'
# parse_and_edit(edit_plan_json, 'my_video.mp4')