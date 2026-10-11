"""
Dual Engine Manager for Aegis-OS.

Coordinates between:
1. Local GPU-Accelerated Engine (Ultralytics YOLO + OpenCV + Caffe/PyTorch)
2. AWS Rekognition Cloud Engine (Amazon Rekognition Vision APIs via Boto3)

Provides unified polymorphic interface for server.py, stream_manager.py, and routes_extra.py.
"""
import os
import threading
from detector import HeadGenderYOLODetector
from aws_rekognition import AWSRekognitionDetector

ENGINE_GPU = 'gpu_local'
ENGINE_AWS = 'aws_rekognition'

class EngineManager:
    """
    Polymorphic Dual Engine Manager and Router.
    Routes detection requests to either the Local GPU YOLO Engine or AWS Rekognition Engine.
    """

    def __init__(self, default_mode=None):
        self._lock = threading.RLock()
        
        # Determine initial active engine mode from environment or default
        env_mode = os.environ.get('AEGIS_ENGINE_MODE', ENGINE_GPU).lower()
        if 'aws' in env_mode or 'rekognition' in env_mode:
            self.active_mode = ENGINE_AWS
        else:
            self.active_mode = ENGINE_GPU

        if default_mode in (ENGINE_GPU, ENGINE_AWS):
            self.active_mode = default_mode

        print(f"🔀 [EngineManager] Initializing Dual Engine Architecture (Active: {self.active_mode.upper()})...", flush=True)

        # 1. Instantiate AWS Rekognition Engine
        print("  🔹 Initializing AWS Rekognition Cloud Engine...", flush=True)
        try:
            self.aws_detector = AWSRekognitionDetector(
                region=os.environ.get('AWS_DEFAULT_REGION', 'us-east-1'),
                collection_id=os.environ.get('AWS_REKOGNITION_COLLECTION', 'aegis-rekognition-collection')
            )
        except Exception as e:
            print(f"⚠️ Warning initializing AWS detector: {e}", flush=True)
            self.aws_detector = None

        # 2. Local GPU Engine (eager only if active_mode == ENGINE_GPU, otherwise lazy on-demand)
        self.gpu_detector = None
        if self.active_mode == ENGINE_GPU:
            self._ensure_gpu_detector()
        else:
            print("  ⚡ [EngineManager] Standalone AWS Rekognition Mode: Local GPU YOLO models bypassed.", flush=True)

        print(f"✅ [EngineManager] Engine Ready! Active Engine: {self.active_mode.upper()}", flush=True)

    def _ensure_gpu_detector(self):
        """Lazily instantiates the Local GPU YOLO Engine on demand."""
        if self.gpu_detector is not None:
            return self.gpu_detector
        print("  🔹 Loading Local GPU Engine (Ultralytics YOLO + OpenCV)...", flush=True)
        try:
            self.gpu_detector = HeadGenderYOLODetector(
                yolo_model_name='yolo11m.pt',
                yolo_conf=0.30,
                gender_conf=0.40,
                imgsz=1280
            )
        except Exception as e:
            print(f"⚠️ Warning initializing GPU detector: {e}. Fallback to CPU/yolov8n.", flush=True)
            try:
                self.gpu_detector = HeadGenderYOLODetector(
                    yolo_model_name='yolov8n.pt',
                    yolo_conf=0.35,
                    gender_conf=0.40,
                    imgsz=640
                )
            except Exception as e2:
                print(f"Fatal error initializing GPU detector: {e2}", flush=True)
                self.gpu_detector = None
        return self.gpu_detector

    @property
    def current_engine(self):
        """Returns the currently active detector instance."""
        if self.active_mode == ENGINE_AWS and self.aws_detector:
            return self.aws_detector
        return self.gpu_detector or self.aws_detector

    @property
    def device(self):
        eng = self.current_engine
        return eng.device if eng else 'None'

    @property
    def yolo_conf(self):
        eng = self.current_engine
        return eng.yolo_conf if eng else 0.35

    @yolo_conf.setter
    def yolo_conf(self, val):
        if self.gpu_detector:
            self.gpu_detector.yolo_conf = val
        if self.aws_detector:
            self.aws_detector.yolo_conf = val

    @property
    def gender_conf(self):
        eng = self.current_engine
        return eng.gender_conf if eng else 0.40

    @gender_conf.setter
    def gender_conf(self, val):
        if self.gpu_detector:
            self.gpu_detector.gender_conf = val
        if self.aws_detector:
            self.aws_detector.gender_conf = val

    @property
    def obj_conf(self):
        eng = self.current_engine
        return eng.obj_conf if eng else 0.10

    @obj_conf.setter
    def obj_conf(self, val):
        if self.gpu_detector:
            self.gpu_detector.obj_conf = val
        if self.aws_detector:
            self.aws_detector.obj_conf = val

    @property
    def blur_faces(self):
        eng = self.current_engine
        return eng.blur_faces if eng else False

    @blur_faces.setter
    def blur_faces(self, val):
        if self.gpu_detector:
            self.gpu_detector.blur_faces = val
        if self.aws_detector:
            self.aws_detector.blur_faces = val

    @property
    def db_peoples(self):
        eng = self.current_engine
        return eng.db_peoples if eng else {}

    @property
    def DB_MATCH_SIM(self):
        return getattr(self.current_engine, 'DB_MATCH_SIM', 0.72)

    @DB_MATCH_SIM.setter
    def DB_MATCH_SIM(self, val):
        if self.gpu_detector and hasattr(self.gpu_detector, 'DB_MATCH_SIM'):
            self.gpu_detector.DB_MATCH_SIM = val

    @property
    def face_match_sim(self):
        return getattr(self.current_engine, 'face_match_sim', 0.40)

    @face_match_sim.setter
    def face_match_sim(self, val):
        if self.gpu_detector and hasattr(self.gpu_detector, 'face_match_sim'):
            self.gpu_detector.face_match_sim = val
        if self.aws_detector and hasattr(self.aws_detector, 'face_match_sim'):
            self.aws_detector.face_match_sim = val

    @property
    def auto_learn(self):
        return getattr(self.current_engine, 'auto_learn', True)

    @auto_learn.setter
    def auto_learn(self, val):
        if self.gpu_detector and hasattr(self.gpu_detector, 'auto_learn'):
            self.gpu_detector.auto_learn = val
        if self.aws_detector and hasattr(self.aws_detector, 'auto_learn'):
            self.aws_detector.auto_learn = val

    def switch_engine(self, mode):
        """Switches the active vision engine (ENGINE_GPU or ENGINE_AWS)."""
        with self._lock:
            mode = mode.lower()
            if mode not in (ENGINE_GPU, ENGINE_AWS):
                raise ValueError(f"Invalid engine mode '{mode}'. Choose '{ENGINE_GPU}' or '{ENGINE_AWS}'.")
            
            if mode == ENGINE_AWS and not self.aws_detector:
                raise RuntimeError("AWS Rekognition Engine is not available.")
            if mode == ENGINE_GPU and not self.gpu_detector:
                self._ensure_gpu_detector()
                if not self.gpu_detector:
                    raise RuntimeError("Local GPU Engine failed to initialize.")

            self.active_mode = mode
            print(f"🔄 [EngineManager] Switched active engine to: {self.active_mode.upper()} ({self.get_active_label()})", flush=True)
            return self.get_status()

    def get_status(self):
        """Returns comprehensive status of both engines."""
        return {
            'active_mode': self.active_mode,
            'active_label': self.get_active_label(),
            'gpu_engine': {
                'available': self.gpu_detector is not None,
                'device': self.gpu_detector.device if self.gpu_detector else 'Unavailable',
                'models': 'YOLO11m + YOLOv8n-pose + Caffe Gender + OSNet Re-ID'
            },
            'aws_engine': {
                'available': self.aws_detector is not None,
                'region': self.aws_detector.region if self.aws_detector else 'us-east-1',
                'connected': self.aws_detector.is_connected if self.aws_detector else False,
                'collection_id': self.aws_detector.collection_id if self.aws_detector else 'aegis-rekognition-collection',
                'last_error': self.aws_detector.last_error if self.aws_detector else ''
            }
        }

    def get_active_label(self):
        if self.active_mode == ENGINE_AWS:
            region = self.aws_detector.region if self.aws_detector else 'us-east-1'
            return f"AWS Rekognition Cloud ({region})"
        else:
            dev = self.gpu_detector.device.upper() if self.gpu_detector else 'GPU'
            return f"Local {dev} Accelerated (YOLO + OpenCV)"

    def process_frame(self, frame, *args, **kwargs):
        """Delegates frame processing to active engine."""
        eng = self.current_engine
        if not eng:
            raise RuntimeError("No vision engine available.")
        return eng.process_frame(frame, *args, **kwargs)

    def reset_tracks(self, *args, **kwargs):
        if self.gpu_detector:
            try: self.gpu_detector.reset_tracks(*args, **kwargs)
            except Exception: pass
        if self.aws_detector:
            try: self.aws_detector.reset_tracks(*args, **kwargs)
            except Exception: pass

    def get_occupant_roster(self, *args, **kwargs):
        eng = self.current_engine
        return eng.get_occupant_roster(*args, **kwargs) if eng else []

    def load_db_peoples(self):
        if self.gpu_detector:
            try: self.gpu_detector.load_db_peoples()
            except Exception: pass
        if self.aws_detector:
            try: self.aws_detector.load_db_peoples()
            except Exception: pass

    def add_person_photo(self, person_id, photo_b64, *args, **kwargs):
        """Syncs photo exemplar across active engines."""
        eng = self.current_engine
        report = eng.add_person_photo(person_id, photo_b64, *args, **kwargs)
        # Also sync to the other engine
        other = self.aws_detector if eng == self.gpu_detector else self.gpu_detector
        if other:
            try:
                other.load_db_peoples()
            except Exception:
                pass
        return report

    def analyze_photo(self, img):
        eng = self.current_engine
        return eng.analyze_photo(img) if eng else {}

    def prepare_photo(self, img):
        eng = self.current_engine
        return eng.prepare_photo(img) if eng else img

    def public_report(self, report):
        eng = self.current_engine
        return eng.public_report(report) if eng else report

    def _decode_photo(self, photo_b64):
        eng = self.current_engine
        return eng._decode_photo(photo_b64) if eng else None

    def learn_live_identity(self, db_id, identity, thumb_b64=''):
        if self.gpu_detector and hasattr(self.gpu_detector, 'learn_live_identity'):
            return self.gpu_detector.learn_live_identity(db_id, identity, thumb_b64)
        return None

    def run_diagnostic_test(self):
        """Runs diagnostics for active engine and returns combined health data."""
        gpu_diag = {}
        if self.gpu_detector and hasattr(self.gpu_detector, 'run_diagnostic_test'):
            try:
                gpu_diag = self.gpu_detector.run_diagnostic_test()
            except Exception as e:
                gpu_diag = {'error': str(e)}

        aws_diag = {}
        if self.aws_detector and hasattr(self.aws_detector, 'run_diagnostic_test'):
            try:
                aws_diag = self.aws_detector.run_diagnostic_test()
            except Exception as e:
                aws_diag = {'error': str(e)}

        active_diag = aws_diag if self.active_mode == ENGINE_AWS else gpu_diag

        # Combined diagnostics
        return {
            **active_diag,
            'active_mode': self.active_mode,
            'active_label': self.get_active_label(),
            'gpu_diagnostics': gpu_diag,
            'aws_diagnostics': aws_diag,
        }
