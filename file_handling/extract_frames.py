import argparse
import cv2

def extract_frames(video_path, output_dir, target_frames=None):
    # Open the video file
    cap = cv2.VideoCapture(video_path)

    # Check if the video file was opened successfully
    if not cap.isOpened():
        print("Error opening video file")
        return

    # Get the total number of frames in the video
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    print(f"Total number of frames: {total_frames}")

    # Calculate the frame interval if target_frames is specified
    if target_frames is not None:
        frame_interval = int(total_frames / target_frames)
        print(f"Extracting every {frame_interval} frames")
    else:
        frame_interval = 1

    print(f"Frame interval: {frame_interval}")

    # Initialize a counter for the frames
    frame_count = 0

    # Loop through the frames of the video
    while True:
        # Read a frame from the video
        ret, frame = cap.read()

        # If there are no more frames, break out of the loop
        if not ret:
            break

        # Increment the frame counter
        frame_count += 1
        # print(f"checking {frame_count} frame")
        # If target_frames is specified, only extract every nth frame
        if target_frames is not None and frame_count % frame_interval != 0:
            # print(f"Skipping frame {frame_count}")
            continue

        # Save the frame as an image file
        frame_path = f"{output_dir}/frame{frame_count:04d}.jpg"
        cv2.imwrite(frame_path, frame)

        print(f"Saved {frame_path}")


    # Release the video file
    cap.release()

    print(f"Extracted {frame_count} frames to {output_dir}")

if __name__ == "__main__":
    # Create a command-line parser
    parser = argparse.ArgumentParser(description="Extract frames from a video file")

    # Add arguments for the video file path, output directory, and target frames
    parser.add_argument("video_path", help="Path to the video file")
    parser.add_argument("output_dir", help="Path to the output directory")
    parser.add_argument("--target_frames", type=int, help="Number of frames to extract")

    # Parse the command-line arguments
    args = parser.parse_args()
    print(f"Target frames: {args.target_frames}")
    # Call the extract_frames function with the command-line arguments
    extract_frames(args.video_path, args.output_dir, args.target_frames)