import os
import subprocess

# Replace this with the path to the folder containing your .mkv files
your_folder_path = '/Users/sam/movies'

# Function to convert mkv to mp4
def convert_mkv_to_mp4(mkv_file, output_dir):
    mp4_file = os.path.splitext(mkv_file)[0] + '.mp4'  
    cmd = ['ffmpeg', '-i', os.path.join(output_dir, mkv_file), '-codec', 'copy', os.path.join(output_dir, mp4_file)]
    subprocess.run(cmd)

# Walking through the folder and converting files
for root, dirs, files in os.walk(your_folder_path):
    for file in files:
        if file.endswith('.mkv'):
            print(f'Converting {file} to mp4...')
            convert_mkv_to_mp4(file, root)
            print(f'{file} has been converted.')

print('Conversion complete.')