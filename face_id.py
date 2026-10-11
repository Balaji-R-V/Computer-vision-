"""
Face recognition for registered people (OpenCV YuNet detector + SFace embeddings, both ONNX, CPU).

Body ReID cannot recognise someone who changed clothes. A face match is far more reliable, but only
when the face is large enough: on high or distant CCTV most faces are smaller than MIN_FACE_PX and
are ignored, in which case body ReID remains the only signal.
"""
import os

import cv2
import numpy as np

MODELS = os.path.join(os.path.dirname(__file__), 'models')
DETECTOR_PATH = os.path.join(MODELS, 'face_detection_yunet_2023mar.onnx')
RECOGNIZER_PATH = os.path.join(MODELS, 'face_recognition_sface_2021dec.onnx')

MIN_FACE_PX = 40            # narrower faces are too low-resolution to compare reliably
MATCH_SIM = 0.40            # cosine; OpenCV's published same-identity threshold for SFace is 0.363


class FaceID:
    dim = 128

    def __init__(self):
        self.detector = None
        self.recognizer = None
        if not (os.path.exists(DETECTOR_PATH) and os.path.exists(RECOGNIZER_PATH)):
            print("⚠️ Face models not found in models/ - face recognition disabled.", flush=True)
            return
        try:
            self.detector = cv2.FaceDetectorYN.create(DETECTOR_PATH, '', (320, 320), 0.8, 0.3, 5000)
            self.recognizer = cv2.FaceRecognizerSF.create(RECOGNIZER_PATH, '')
            print("🙂 Face recognition loaded (YuNet + SFace).", flush=True)
        except Exception as e:
            self.detector = self.recognizer = None
            print(f"⚠️ Face recognition unavailable: {e}", flush=True)

    @property
    def available(self):
        return self.recognizer is not None

    def embed(self, img):
        """
        Returns (L2-normalised 128-d embedding, face_width_px) for the largest face in img,
        or (None, 0) if there is no face or it is smaller than MIN_FACE_PX.
        """
        if not self.available or img is None or img.size == 0:
            return None, 0
        h, w = img.shape[:2]
        try:
            self.detector.setInputSize((w, h))
            _, faces = self.detector.detect(img)
            if faces is None or len(faces) == 0:
                return None, 0
            face = max(faces, key=lambda f: f[2] * f[3])
            if face[2] < MIN_FACE_PX:
                return None, int(face[2])
            aligned = self.recognizer.alignCrop(img, face)
            feat = self.recognizer.feature(aligned).flatten().astype(np.float32)
            norm = np.linalg.norm(feat)
            return (feat / norm if norm > 0 else None), int(face[2])
        except Exception:
            return None, 0
