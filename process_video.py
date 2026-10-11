import cv2
import argparse
import time
import os
from detector import HeadGenderYOLODetector

def process_video_file(input_path, output_path="output_classified.mp4", yolo_conf=0.35, gender_conf=0.40):
    if not os.path.exists(input_path):
        print(f"Error: Input video path '{input_path}' does not exist.")
        return

    print(f"Loading detector models...")
    detector = HeadGenderYOLODetector(yolo_conf=yolo_conf, gender_conf=gender_conf)

    cap = cv2.VideoCapture(input_path)
    if not cap.isOpened():
        print(f"Error opening video file '{input_path}'")
        return

    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = cap.get(cv2.CAP_PROP_FPS) or 25
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

    print(f"Processing Video: {input_path}")
    print(f"Resolution: {width}x{height} | FPS: {fps:.1f} | Total Frames: {total_frames}")

    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    out = cv2.VideoWriter(output_path, fourcc, fps, (width, height))

    frame_count = 0
    start_total_time = time.time()

    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break

        frame_count += 1
        annotated_frame, stats = detector.process_frame(frame)
        out.write(annotated_frame)

        if frame_count % 10 == 0 or frame_count == total_frames:
            elapsed = time.time() - start_total_time
            avg_fps = frame_count / max(elapsed, 0.001)
            pct = (frame_count / max(total_frames, 1)) * 100
            print(f"Frame {frame_count}/{total_frames} ({pct:.1f}%) | "
                  f"Male: {stats['male_count']} | Female: {stats['female_count']} | "
                  f"Objects: {stats['total_objects']} | Speed: {avg_fps:.1f} FPS")

    cap.release()
    out.release()
    print(f"\nProcessing complete! Classified video saved to: {output_path}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Classify heads (Male/Female) and detect objects in video.")
    parser.add_argument("--input", "-i", type=str, required=True, help="Path to input video file")
    parser.add_argument("--output", "-o", type=str, default="classified_video.mp4", help="Path to output annotated video file")
    parser.add_argument("--yolo_conf", type=float, default=0.35, help="YOLO confidence threshold")
    parser.add_argument("--gender_conf", type=float, default=0.40, help="Gender confidence threshold")
    
    args = parser.parse_args()
    process_video_file(args.input, args.output, args.yolo_conf, args.gender_conf)
