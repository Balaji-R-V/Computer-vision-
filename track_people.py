"""
YOLO Person Detection & ByteTrack Counter Script
Integrates YOLO11 / YOLOv8 ByteTrack tracking with real-time person counting.
"""
import sys
import os
import cv2
import argparse
from ultralytics import YOLO

def track_and_count_people(
    video_source="cctv.mp4",
    model_path="yolov8n.pt",
    conf=0.3,
    imgsz=1280,
    tracker="bytetrack.yaml",
    save_output=False,
    output_path="tracked_cctv.mp4"
):
    """
    Tracks and counts people in a video stream using Ultralytics YOLO & ByteTrack.
    """
    if isinstance(video_source, str) and not os.path.exists(video_source) and not video_source.isdigit():
        print(f"⚠️ Warning: Input video path '{video_source}' not found. Please specify a valid video file.")
        return

    print(f"🚀 Loading YOLO model: {model_path}...")
    model = YOLO(model_path)

    print(f"📹 Processing Video Source: {video_source}")
    print(f"⚙️ Settings: conf={conf}, imgsz={imgsz}, tracker={tracker}, classes=[0] (Person Only)")

    # Handle video output writer if requested
    writer = None
    if save_output and isinstance(video_source, str) and os.path.exists(video_source):
        cap_temp = cv2.VideoCapture(video_source)
        w = int(cap_temp.get(cv2.CAP_PROP_FRAME_WIDTH))
        h = int(cap_temp.get(cv2.CAP_PROP_FRAME_HEIGHT))
        fps = cap_temp.get(cv2.CAP_PROP_FPS) or 25
        cap_temp.release()
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        writer = cv2.VideoWriter(output_path, fourcc, fps, (w, h))
        print(f"🎬 Saving annotated output to: {output_path}")

    # Stream results through YOLO model.track
    results = model.track(
        source=video_source,
        classes=[0],           # 0: Person class only
        conf=conf,
        imgsz=imgsz,
        tracker=tracker,
        persist=True,
        stream=True
    )

    frame_index = 0
    for r in results:
        frame_index += 1
        people_count = len(r.boxes)
        
        # Get tracked IDs if present
        track_ids = []
        if r.boxes.id is not None:
            track_ids = r.boxes.id.cpu().numpy().astype(int).tolist()

        print(f"Frame #{frame_index:04d} | People in frame: {people_count} | Track IDs: {track_ids}")

        # Render frame visualization
        annotated_frame = r.plot()

        if writer is not None:
            writer.write(annotated_frame)

    if writer is not None:
        writer.release()
        print(f"✅ Video processing complete! File saved to {output_path}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="YOLO ByteTrack Person Counter")
    parser.add_argument("--source", "-i", type=str, default="cctv.mp4", help="Video file path or webcam index (0)")
    parser.add_argument("--model", "-m", type=str, default="yolov8n.pt", help="YOLO model path (.pt)")
    parser.add_argument("--conf", type=float, default=0.3, help="Confidence threshold")
    parser.add_argument("--imgsz", type=int, default=1280, help="Inference image resolution")
    parser.add_argument("--tracker", type=str, default="bytetrack.yaml", help="Tracker config (bytetrack.yaml or botsort.yaml)")
    parser.add_argument("--save", action="store_true", help="Save annotated output video")
    
    args = parser.parse_args()
    
    track_and_count_people(
        video_source=args.source,
        model_path=args.model,
        conf=args.conf,
        imgsz=args.imgsz,
        tracker=args.tracker,
        save_output=args.save
    )
