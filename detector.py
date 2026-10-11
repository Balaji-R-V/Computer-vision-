import cv2
import numpy as np
import time
import base64
import json
import threading
import torch
from ultralytics import YOLO
from model_utils import load_gender_net, classify_gender
from reid import PersonReID
from face_id import FaceID, MATCH_SIM as FACE_MATCH_SIM
import database

class CameraState:
    """Everything the detector remembers about ONE camera: tracks, roster, posture/gender caches, locked target.
    The identity gallery and registered people are deliberately NOT here - they are shared so that a person
    seen on camera A keeps the same identity on camera B."""

    def __init__(self):
        self.tracker = None                  # per-camera ByteTrack instance (IDs must not mix between cameras)
        self.track_history = {}
        self.occupant_roster = {}
        self.active_track_to_person_id = {}
        self.active_track_to_db_person = {}
        self.gender_cache = {}
        self.posture_history = {}
        self._embed_frame = {}
        self.db_state = {}                   # per track: recent registered-person candidates, how it was named
        self.locked_target_id = None
        self.locked_target_track_id = None
        self.locked_target_embedding = None
        self.locked_target_gender = None
        self.locked_target_last_zone = None
        self.locked_target_face_b64 = None
        self.locked_target_last_seen = 0
        self.locked_target_lost_frames = 0


class HeadGenderYOLODetector:
    """
    Full Person Pose, Gender & Zone Boundary Detection Engine:
    - Person Detection across full frame
    - Action Posture: Sitting vs Standing
    - Upper Body & Head Gender Classification: Male vs Female
    - Custom Named Boundary / Zone Location Assignment
    - SQLite Peoples Database Facial/Appearance Re-ID Matching
    - RTSP Live Network Camera Stream Processing
    """
    def __init__(self, yolo_model_name='yolo11m.pt', yolo_conf=0.3, gender_conf=0.4, obj_conf=0.10, imgsz=1280):
        self.yolo_conf = yolo_conf
        self.gender_conf = gender_conf
        self.obj_conf = obj_conf
        # Serializes frame processing and roster reads: the stream worker thread and Flask request threads share this engine
        self._lock = threading.RLock()
        self._cam = CameraState()          # the camera currently being processed (swapped per call)
        self.reid = PersonReID()
        self.face = FaceID()
        self._faces_registered = False
        self._bodies_registered = False
        self.blur_faces = False        # privacy mode: blur heads in the video and pixelate stored face crops
        self._frame_idx = 0
        self.posture_history = {}
        self._embed_frame = {}   # byte_track_id -> frame index of its last ReID embedding
        self.imgsz = imgsz  # 1280px = balanced high-accuracy for CCTV dense scenes with 10-20 FPS
        
        # Determine GPU CUDA Hardware Device & FP16 Half Precision Mode
        self.device = 'cuda' if torch.cuda.is_available() else 'cpu'
        self.half = (self.device == 'cuda')
        device_name = torch.cuda.get_device_name(0) if self.device == 'cuda' else 'CPU'
        print(f"[Detector] Hardware Acceleration: Device='{self.device.upper()}' ({device_name}) | FP16 Half Precision={self.half}", flush=True)
        
        # Load YOLO Models onto GPU
        print(f"Loading Ultralytics YOLO object model ({yolo_model_name}) on {self.device.upper()}...")
        self.yolo_model = YOLO(yolo_model_name)
        try:
            self.yolo_model.to(self.device)
            if self.device == 'cuda':
                self.yolo_model.model.half()
        except Exception as e:
            print(f"Warning moving YOLO model to device {self.device}: {e}")
        
        # Separate instance for non-person objects: model.track(classes=[0]) leaves a sticky person-only
        # filter and tracker hooks on the shared predictor, which made the object pass return only people.
        self.object_model = YOLO(yolo_model_name)
        try:
            self.object_model.to(self.device)
            if self.device == 'cuda':
                self.object_model.model.half()
        except Exception as e:
            print(f"Warning moving YOLO object model to device {self.device}: {e}")

        print("Loading Ultralytics YOLO Pose model on GPU for posture detection...")
        try:
            self.pose_model = YOLO('yolov8n-pose.pt')
            self.pose_model.to(self.device)
            if self.device == 'cuda':
                self.pose_model.model.half()
        except Exception as e:
            print(f"Pose model loading fallback: {e}")
            self.pose_model = None
        
        # Load Gender Classification Model with CUDA option
        print("Loading Gender Classifier...")
        self.gender_net = load_gender_net(use_gpu=(self.device == 'cuda'))
        
        # Tracking history map: track_id -> list of (x, y) centroids
        self.track_history = {}
        # Occupant Face & Space Time Roster: person_id -> occupant record
        self.occupant_roster = {}
        # Persistent Person Re-ID Gallery: person_id -> {'person_id': int, 'embedding': np.ndarray}
        self.known_person_gallery = {}
        self.active_track_to_person_id = {}
        
        # SQLite Database Peoples gallery: db_id -> person dict
        self.db_peoples = {}
        self.active_track_to_db_person = {}
        self.load_db_peoples()
        
        # Target Locking & Persistent Re-Acquisition Engine
        self.locked_target_id = None
        self.locked_target_track_id = None
        self.locked_target_embedding = None
        self.locked_target_gender = None
        self.locked_target_last_zone = None
        self.locked_target_face_b64 = None
        self.locked_target_last_seen = 0
        self.locked_target_lost_frames = 0
        
        # Gender cache per Track ID to eliminate CPU Caffe bottleneck
        self.gender_cache = {}
        self._fps_ema = None
        
        # Colors (BGR)
        self.COLOR_MALE = (255, 210, 0)      # Bright Cyan / Yellow-Blue
        self.COLOR_FEMALE = (180, 60, 255)   # Bright Pink / Magenta
        self.COLOR_OBJECT = (0, 200, 100)    # Emerald Green
        self.COLOR_TARGET = (0, 210, 255)    # Bright Cyan-Yellow Target Reticle
        self.ZONE_COLORS = [
            (255, 140, 0),   # Bright Orange
            (0, 255, 255),   # Bright Yellow
            (255, 0, 128),   # Magenta
            (128, 255, 0),   # Lime
            (0, 191, 255),   # Sky Blue
            (186, 85, 211)   # Purple
        ]

        # Warmup GPU on dummy frame so Frame 1 has no CUDA overhead
        if self.device == 'cuda':
            try:
                dummy = np.zeros((480, 640, 3), dtype=np.uint8)
                self.process_frame(dummy, draw_yolo_objects=False, draw_heads=False)
                self._fps_ema = None  # Reset EMA after warmup
                print("[Detector] GPU CUDA warmup complete.", flush=True)
            except Exception as e:
                print(f"CUDA warmup notice: {e}")
        
    # ---- Registered people: photos -> face + body exemplars ------------------------------------------
    MAX_PHOTO_SIDE = 720
    MIN_BODY_H, MIN_BODY_W = 110, 40
    FULL_BODY_ASPECT = 1.8         # height/width of a standing, full-length person
    CLOSEUP_FACE_RATIO = 0.40      # face width / person width at or above this = portrait close-up (face only)

    def load_db_peoples(self):
        """Loads every registered person with all of their face/body exemplars (one per photo / live example)."""
        self.db_peoples = {}
        try:
            exemplars = database.get_all_person_exemplars()
            for row in database.get_all_peoples():
                pid = row['id']
                if pid not in exemplars and row.get('photo_b64'):
                    # Registered before multi-photo support: analyse the saved photo once and keep it as an exemplar
                    try:
                        self.add_person_photo(pid, row['photo_b64'], kind='legacy', reload=False)
                        exemplars = database.get_all_person_exemplars()
                    except Exception as e:
                        print(f"Could not analyse the saved photo of {row['person_code']}: {e}", flush=True)
                faces, bodies = [], []
                for ex in exemplars.get(pid, []):
                    if ex['face'] and len(ex['face']) == self.face.dim:
                        faces.append(np.array(ex['face'], dtype=np.float32))
                    for b in ex['bodies']:
                        if len(b) == self.reid.dim:
                            bodies.append(np.array(b, dtype=np.float32))
                mean = None
                if bodies:
                    mean = np.mean(bodies, axis=0)
                    n = np.linalg.norm(mean)
                    mean = mean / n if n > 0 else None
                self.db_peoples[pid] = {
                    'id': pid, 'person_code': row['person_code'], 'name': row['name'], 'gender': row['gender'],
                    'department': row['department'], 'role': row['role'],
                    'faces': faces, 'bodies': bodies,
                    'face': faces[0] if faces else None,     # kept for older callers
                    'auto_count': sum(1 for ex in exemplars.get(pid, []) if ex['kind'] == 'auto'),
                    'embedding': mean,                        # mean body embedding (target lock re-acquisition)
                }
            self._faces_registered = any(p['faces'] for p in self.db_peoples.values())
            self._bodies_registered = any(p['bodies'] for p in self.db_peoples.values())
            print(f"Detector loaded {len(self.db_peoples)} registered people "
                  f"({sum(1 for p in self.db_peoples.values() if p['faces'])} with face exemplars, "
                  f"{sum(1 for p in self.db_peoples.values() if p['bodies'])} with body exemplars).", flush=True)
        except Exception as e:
            print(f"Error loading DB peoples in detector: {e}", flush=True)

    @staticmethod
    def _decode_photo(photo_b64):
        if not photo_b64 or not isinstance(photo_b64, str):
            return None
        try:
            if "," in photo_b64:
                photo_b64 = photo_b64.split(",", 1)[1]
            return cv2.imdecode(np.frombuffer(base64.b64decode(photo_b64), np.uint8), cv2.IMREAD_COLOR)
        except Exception:
            return None

    def prepare_photo(self, img):
        """Downscales large photos (keeps the database small; the embeddings need far less detail)."""
        h, w = img.shape[:2]
        if max(h, w) > self.MAX_PHOTO_SIDE:
            scale = self.MAX_PHOTO_SIDE / max(h, w)
            img = cv2.resize(img, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA)
        return img

    def analyze_photo(self, img):
        """
        Judges a photo for recognition and extracts what can be used from it.
        Returns a report dict; vectors are under '_face' and '_bodies' (not meant for the browser).
        - Face: needs a front-facing face at least MIN_FACE_PX wide.
        - Body: needs a detected person. Full-length photos give three views (as is, mirrored, upper body, which
          is how a seated person looks to a ceiling camera); half-body photos give two; close-ups give none.
        """
        notes = []
        report = {'face_found': False, 'face_px': 0, 'face_usable': False, 'body_found': False, 'body_kind': None,
                  'body_views': 0, 'usable': False, 'notes': notes, '_face': None, '_bodies': []}
        if img is None or img.size == 0:
            notes.append("The image could not be read.")
            return report

        if self.face.available:
            vec, width = self.face.embed(img)
            report['face_px'] = int(width)
            report['face_found'] = width > 0
            if vec is not None:
                report['face_usable'] = True
                report['_face'] = vec
            elif width > 0:
                notes.append(f"The face is only {width}px wide; at least 40px is needed. Use a closer, higher-resolution photo.")
            else:
                notes.append("No clear face found. For face recognition use a sharp, front-facing photo with the face fully visible.")
        else:
            notes.append("Face recognition models are not installed; body matching only.")

        if self.reid.available:
            with self._lock:
                res = self.yolo_model.predict(img, conf=0.3, classes=[0], imgsz=960, device=self.device, verbose=False)[0]
            boxes = res.boxes.xyxy.cpu().numpy().astype(int) if len(res.boxes) else []
            h_img, w_img = img.shape[:2]
            face_w = report['face_px']
            crop, views = None, []
            if len(boxes):
                x1, y1, x2, y2 = max(boxes, key=lambda b: (b[2] - b[0]) * (b[3] - b[1]))
                crop = img[max(0, y1):min(h_img, y2), max(0, x1):min(w_img, x2)]
                ref_width = max(x2 - x1, 1)
            else:
                ref_width = w_img
            h, w = (crop.shape[:2] if crop is not None else (h_img, w_img))

            # A portrait/ID-style close-up has a big face relative to the person; a body photo has a small one.
            closeup = face_w > 0 and face_w / ref_width >= self.CLOSEUP_FACE_RATIO
            if closeup:
                report['body_found'] = crop is not None
                report['body_kind'] = 'closeup'
                notes.append("This is a close-up, so it is used for face recognition only. "
                             "A photo showing the upper body or the whole person also enables recognition when the face is not visible.")
            elif crop is None:
                notes.append("No person was detected in this photo, so it is not used for body matching.")
            elif h < self.MIN_BODY_H or w < self.MIN_BODY_W:
                report['body_found'] = True
                notes.append("The person is too small in this photo to be useful for body matching.")
            else:
                report['body_found'] = True
                if h / max(w, 1) >= self.FULL_BODY_ASPECT:
                    report['body_kind'] = 'full'
                    views = [crop, cv2.flip(crop, 1), crop[:int(h * 0.62)]]    # + upper body: how a seated person looks
                else:
                    report['body_kind'] = 'half'                                 # upper body or seated
                    views = [crop, cv2.flip(crop, 1)]
            if views:
                report['_bodies'] = [v for v in self.reid.embed(views) if v is not None]
                report['body_views'] = len(report['_bodies'])

        report['usable'] = bool(report['face_usable'] or report['_bodies'])
        if not report['usable']:
            notes.append("This photo cannot be used for recognition. Add a clearer one.")
        elif report['face_usable'] and not report['_bodies']:
            notes.append("Face recognition only: needs the face to be visible to the camera (usually close to it).")
        return report

    @staticmethod
    def public_report(report):
        return {k: v for k, v in report.items() if not k.startswith('_')}

    def add_person_photo(self, person_id, photo_b64, kind='upload', note='', reload=True):
        """Analyses and stores a photo for a registered person. Returns the report plus the new photo id."""
        img = self._decode_photo(photo_b64)
        if img is None:
            raise ValueError("The image could not be read.")
        img = self.prepare_photo(img)
        report = self.analyze_photo(img)
        ok, buf = cv2.imencode('.jpg', img, [cv2.IMWRITE_JPEG_QUALITY, 88])
        stored = f"data:image/jpeg;base64,{base64.b64encode(buf).decode('utf-8')}"
        photo_id = database.add_person_photo(
            person_id, stored, report['_face'].tolist() if report['_face'] is not None else None,
            [v.tolist() for v in report['_bodies']], report['face_px'], kind, note)
        if reload:
            self.load_db_peoples()
        out = self.public_report(report)
        out['photo_id'] = photo_id
        return out

    def learn_live_identity(self, db_id, identity, thumb_b64=''):
        """
        Teaches a registered person what they look like on THIS camera: stores the body signature of a person
        currently tracked (identified so far only as 'Person #N') as an exemplar of the registered person.
        This is the most reliable exemplar, because it comes from the same camera and lighting.
        """
        with self._lock:
            ident = int(identity) if str(identity).isdigit() else identity
            feat = self.known_person_gallery.get(ident, {}).get('embedding') if isinstance(ident, int) else None
            if feat is None:
                raise ValueError("That occupant is not being tracked right now (or is already a registered person).")
            if db_id not in self.db_peoples:
                raise ValueError("No such registered person.")
            photo_id = database.add_person_photo(db_id, thumb_b64 or '', None, [feat.tolist()], 0, 'live',
                                                 f"learned from live tracking (Person #{ident})")
            self.load_db_peoples()
            p = self.db_peoples[db_id]
            self.known_person_gallery[ident]['alias'] = self._label(p)
            return photo_id

    # ---- Person identity (ReID) ------------------------------------------------------------------
    # Thresholds on cosine similarity of OSNet embeddings. Measured on real frames: different people
    # peaked at ~0.55 and the same person stayed above ~0.85, so these sit in the gap with margin.
    GALLERY_MATCH_SIM = 0.70
    DB_MATCH_SIM = 0.72            # body similarity to a registered person's exemplar
    DB_MARGIN = 0.04               # ...and it must beat the next-best registered person by this much
    DB_MIN_SAMPLES = 3             # a body name needs this many samples; the AVERAGE of the last 5 is what is compared
    face_match_sim = FACE_MATCH_SIM  # settings can change these at runtime
    auto_learn = True              # after a confident face match, remember how the person looks on this camera
    AUTO_LEARN_FACE_SIM = 0.50     # ...only when the face match is this strong
    AUTO_LEARN_MAX = 3             # ...and keep at most this many such examples per person
    AUTO_LEARN_NEW_VIEW_SIM = 0.88 # ...and only if it differs enough from what is already stored to add information
    DB_DOUBT_SIM = 0.55            # a name that stops matching this well is withdrawn after repeated misses
    GALLERY_UPDATE_SIM = 0.75      # only blend a new view into a stored identity when clearly the same person
    REACQUIRE_SIM = 0.68           # re-link a locked target to a new track (above the ~0.55 different-people ceiling)
    REFRESH_EVERY_FRAMES = 30      # re-embed already-identified tracks this often (cheap; keeps the gallery current)
    REGISTERED_PROBE_FRAMES = 8    # tracks not yet named keep being checked this often against registered people

    @staticmethod
    def _label(person):
        return f"{person['person_code']} {person['name']}"

    def _assign_identities(self, person_boxes, frame):
        """
        Resolves a persistent identity for every person in the frame in one batched ReID call.
        - Identities already bound to a ByteTrack ID are kept (stable) and re-checked periodically.
        - A visible face matching a registered person names the track at once.
        - A body match to a registered person must repeat across several samples before the name appears; until
          then the track carries an anonymous 'Person #N' identity.
        - A person already held by another track in this frame can never be assigned twice.
        """
        self._frame_idx += 1
        if not self.reid.available:
            return
        img_h, img_w = frame.shape[:2]
        probing = self._bodies_registered

        refresh, fresh = [], []
        for (x1, y1, x2, y2, _conf, btid) in person_boxes:
            current = self.active_track_to_person_id.get(btid)
            interval = self.REFRESH_EVERY_FRAMES
            if probing and isinstance(current, int) and (self.db_state.get(btid) or {}).get('kind') is None:
                interval = self.REGISTERED_PROBE_FRAMES
            if current is not None and self._frame_idx - self._embed_frame.get(btid, 0) < interval:
                continue
            crop = frame[max(0, y1):min(img_h, y2), max(0, x1):min(img_w, x2)]
            if not self.reid.usable(crop):
                continue
            (refresh if current is not None else fresh).append((btid, crop, (x2 - x1) * (y2 - y1)))

        fresh.sort(key=lambda t: -t[2])      # clearest (largest) new people claim identities first
        batch = refresh + fresh
        feats = self.reid.embed([c for _, c, _ in batch])
        faces = {}
        if self._faces_registered:
            for btid, crop, _area in batch:
                faces[btid] = self._face_feature(crop)

        labels = {btid: self.active_track_to_person_id[btid] for (*_r, btid) in person_boxes
                  if btid in self.active_track_to_person_id}

        for (btid, _crop, _area), feat in zip(refresh, feats[:len(refresh)]):
            self._embed_frame[btid] = self._frame_idx
            pid = self.active_track_to_person_id.get(btid)
            stored = self.known_person_gallery.get(pid, {}).get('embedding') if isinstance(pid, int) else None
            if feat is not None and stored is not None and float(feat @ stored) >= self.GALLERY_UPDATE_SIM:
                self._blend_gallery(pid, feat)
            others = {l for b, l in labels.items() if b != btid}
            self._consider_registered(btid, feat, faces.get(btid), others)
            if btid in self.active_track_to_person_id:
                labels[btid] = self.active_track_to_person_id[btid]
            else:
                labels.pop(btid, None)

        for (btid, _crop, _area), feat in zip(fresh, feats[len(refresh):]):
            self._embed_frame[btid] = self._frame_idx
            if feat is None:
                continue
            labels[btid] = self._match_or_register_person(feat, btid, set(labels.values()), face_feat=faces.get(btid))

    def _face_feature(self, body_crop):
        """Face embedding from the head/shoulders part of a person crop (None if no large-enough face)."""
        h = body_crop.shape[0]
        feat, _w = self.face.embed(body_crop[:max(int(h * 0.45), 35)])
        return feat

    def _match_face(self, face_feat, exclude=()):
        """Registered person whose face exemplar matches face_feat, as (label, db_id, similarity)."""
        best, best_sim = None, self.face_match_sim
        for db_id, p in self.db_peoples.items():
            if not p['faces'] or self._label(p) in exclude:
                continue
            sim = max(float(face_feat @ f) for f in p['faces'])
            if sim >= best_sim:
                best, best_sim = (self._label(p), db_id, sim), sim
        return best

    def _body_candidate(self, feat, exclude=()):
        """(db_id, similarity) of the registered person this body most resembles, if clearly better than the rest."""
        scores = []
        for db_id, p in self.db_peoples.items():
            if not p['bodies'] or self._label(p) in exclude:
                continue
            scores.append((max(float(feat @ b) for b in p['bodies']), db_id))
        if not scores:
            return None
        scores.sort(reverse=True)
        best_sim, best_id = scores[0]
        runner_up = scores[1][0] if len(scores) > 1 else 0.0
        if best_sim >= self.DB_MATCH_SIM and best_sim - runner_up >= self.DB_MARGIN:
            return best_id, best_sim
        return None

    def _new_state(self):
        return {'feats': [], 'kind': None, 'doubt': 0, 'learned': False}

    def _consider_registered(self, btid, feat, face_feat, others):
        """One piece of evidence about whether this track is a registered person; binds, keeps or withdraws a name."""
        st = self.db_state.setdefault(btid, self._new_state())
        if feat is not None:
            st['feats'] = (st['feats'] + [feat])[-5:]
        centroid = None
        if st['feats']:
            centroid = np.mean(st['feats'], axis=0)
            n = np.linalg.norm(centroid)
            centroid = centroid / n if n > 0 else None
        current = self.active_track_to_person_id.get(btid)

        if face_feat is not None:
            hit = self._match_face(face_feat, exclude=others)
            if hit:
                if hit[0] != current:
                    self._bind_registered(btid, hit[1], 'face')
                st['kind'], st['doubt'] = 'face', 0
                self._maybe_auto_learn(hit[1], hit[2], centroid, st)
                return

        if isinstance(current, str):                      # already named: verify a body-based name still fits
            if st['kind'] == 'face' or centroid is None:
                return
            person = next((p for p in self.db_peoples.values() if self._label(p) == current), None)
            fits = person and person['bodies'] and max(float(centroid @ b) for b in person['bodies']) >= self.DB_DOUBT_SIM
            st['doubt'] = 0 if fits else st['doubt'] + 1
            if st['doubt'] >= 3:
                print(f"Withdrawing name '{current}' from track #{btid}: it no longer matches.", flush=True)
                self.active_track_to_person_id.pop(btid, None)
                self.active_track_to_db_person.pop(btid, None)
                self.db_state.pop(btid, None)
            return

        if centroid is None or len(st['feats']) < self.DB_MIN_SAMPLES:
            return
        cand = self._body_candidate(centroid, exclude=others)
        if cand:
            self._bind_registered(btid, cand[0], 'body')
            st['kind'] = 'body'

    def _maybe_auto_learn(self, db_id, face_sim, centroid, st):
        """A confident face match is the moment we KNOW who this body is: keep how they look on this camera."""
        person = self.db_peoples.get(db_id)
        if not (self.auto_learn and person and centroid is not None and not st['learned'] and len(st['feats']) >= 3
                and face_sim >= self.AUTO_LEARN_FACE_SIM and person.get('auto_count', 0) < self.AUTO_LEARN_MAX):
            return
        if person['bodies'] and max(float(centroid @ b) for b in person['bodies']) >= self.AUTO_LEARN_NEW_VIEW_SIM:
            st['learned'] = True            # we already have this look
            return
        try:
            database.add_person_photo(db_id, '', None, [centroid.tolist()], 0, 'auto', 'learned after a face match on camera')
            person['bodies'].append(centroid)
            person['auto_count'] = person.get('auto_count', 0) + 1
            st['learned'] = True
            print(f"Learned how {person['name']} looks on camera (face match {face_sim:.2f}).", flush=True)
        except Exception as e:
            print(f"Auto-learn failed: {e}", flush=True)

    def _bind_registered(self, btid, db_id, kind):
        """Names a track after a registered person, carrying over any time already logged under its anonymous identity."""
        person = self.db_peoples[db_id]
        label = self._label(person)
        old = self.active_track_to_person_id.get(btid)
        self.active_track_to_person_id[btid] = label
        self.active_track_to_db_person[btid] = person
        if old is not None and old != label:
            self._rename_identity(old, label)
            if isinstance(old, int) and old in self.known_person_gallery:
                self.known_person_gallery[old]['alias'] = label       # the same person re-appearing is named at once
        try:
            database.update_person_last_seen(db_id)
        except Exception:
            pass
        print(f"Recognized {person['name']} ({person['person_code']}) on track #{btid} by {kind}.", flush=True)

    def _rename_identity(self, old, new):
        """Moves everything logged for identity `old` over to `new` (merging if `new` already has a record)."""
        rec = self.occupant_roster.pop(old, None)
        if rec is not None:
            rec['track_id'] = new
            target = self.occupant_roster.get(new)
            if target is None:
                self.occupant_roster[new] = rec
            else:
                target['total_seconds'] = round(target['total_seconds'] + rec['total_seconds'], 1)
                for zone, secs in rec['time_per_zone'].items():
                    target['time_per_zone'][zone] = round(target['time_per_zone'].get(zone, 0.0) + secs, 1)
                target['timeline'] = sorted(target['timeline'] + rec['timeline'], key=lambda e: e['timestamp'])
                if not target.get('face_b64'):
                    target['face_b64'] = rec.get('face_b64', '')
        trail = self.track_history.pop(old, None)
        if trail and new not in self.track_history:
            self.track_history[new] = trail

    def _identity_feature(self, identity):
        """The stored ReID embedding for an identity (gallery person or registered person), if any."""
        if isinstance(identity, int):
            return self.known_person_gallery.get(identity, {}).get('embedding')
        for person in self.db_peoples.values():
            if self._label(person) == identity:
                return person.get('embedding')
        return None

    def _blend_gallery(self, pid, feat):
        old = self.known_person_gallery[pid]['embedding']
        blended = 0.9 * old + 0.1 * feat
        norm = np.linalg.norm(blended)
        self.known_person_gallery[pid]['embedding'] = blended / norm if norm > 0 else old

    def _match_or_register_person(self, feat, byte_track_id, claimed=(), face_feat=None):
        """
        First sighting of a track. A clear face match names it at once; otherwise it joins the gallery of
        previously seen people (or becomes a new anonymous 'Person #N'), and the body is also checked against
        registered people as the first of the samples needed to confirm a name.
        """
        st = self.db_state.setdefault(byte_track_id, self._new_state())
        if face_feat is not None:
            hit = self._match_face(face_feat, exclude=claimed)
            if hit:
                self._bind_registered(byte_track_id, hit[1], 'face')
                st['kind'] = 'face'
                return self.active_track_to_person_id[byte_track_id]

        best_pid, best_sim = None, -1.0
        for pid, data in self.known_person_gallery.items():
            if pid in claimed:
                continue
            sim = float(feat @ data['embedding'])
            if sim > best_sim:
                best_pid, best_sim = pid, sim

        if best_pid is not None and best_sim >= self.GALLERY_MATCH_SIM:
            alias = self.known_person_gallery[best_pid].get('alias')
            if alias and alias not in claimed:        # this person was already linked to a registered name
                db_id = next((i for i, p in self.db_peoples.items() if self._label(p) == alias), None)
                if db_id is not None:
                    self._bind_registered(byte_track_id, db_id, 'body')
                    st['kind'] = 'body'
                    return alias
            self.active_track_to_person_id[byte_track_id] = best_pid
            if best_sim >= self.GALLERY_UPDATE_SIM:
                self._blend_gallery(best_pid, feat)
            pid = best_pid
        else:
            pid = max(self.known_person_gallery, default=0) + 1
            self.known_person_gallery[pid] = {'person_id': pid, 'embedding': feat}
            self.active_track_to_person_id[byte_track_id] = pid

        if self._bodies_registered:
            self._consider_registered(byte_track_id, feat, None, claimed)
        return self.active_track_to_person_id[byte_track_id]

    def _draw_target_reticle(self, img, bbox, color=(0, 210, 255), thickness=3, l=18):
        """Draws a futuristic 4-corner target lock reticle on bounding box."""
        x1, y1, x2, y2 = bbox
        # Top-Left
        cv2.line(img, (x1, y1), (x1 + l, y1), color, thickness)
        cv2.line(img, (x1, y1), (x1, y1 + l), color, thickness)
        # Top-Right
        cv2.line(img, (x2, y1), (x2 - l, y1), color, thickness)
        cv2.line(img, (x2, y1), (x2, y1 + l), color, thickness)
        # Bottom-Left
        cv2.line(img, (x1, y2), (x1 + l, y2), color, thickness)
        cv2.line(img, (x1, y2), (x1, y2 - l), color, thickness)
        # Bottom-Right
        cv2.line(img, (x2, y2), (x2 - l, y2), color, thickness)
        cv2.line(img, (x2, y2), (x2, y2 - l), color, thickness)
        # Center Target Crosshair Dot
        cx, cy = (x1 + x2) // 2, (y1 + y2) // 2
        cv2.circle(img, (cx, cy), 4, color, -1)

    def _new_tracker(self):
        from ultralytics.trackers.byte_tracker import BYTETracker
        from ultralytics.utils import YAML, IterableSimpleNamespace
        from ultralytics.utils.checks import check_yaml
        return BYTETracker(args=IterableSimpleNamespace(**YAML.load(check_yaml("bytetrack.yaml"))))

    def _track_persons(self, frame):
        """Detects people and updates this camera's tracker. Returns [(x1, y1, x2, y2, conf, track_id), ...]."""
        res = self.yolo_model.predict(frame, conf=self.yolo_conf, classes=[0], imgsz=self.imgsz,
                                      device=self.device, verbose=False)[0]
        if len(res.boxes) == 0:
            return []
        if self.tracker is None:
            self.tracker = self._new_tracker()
        tracks = self.tracker.update(res.boxes.cpu().numpy(), frame)
        out = []
        for t in tracks:
            x1, y1, x2, y2 = (int(v) for v in t[:4])
            out.append((x1, y1, x2, y2, float(t[5]), int(t[4])))
        return out

    @staticmethod
    def _iou(a, b):
        ix1, iy1, ix2, iy2 = max(a[0], b[0]), max(a[1], b[1]), min(a[2], b[2]), min(a[3], b[3])
        inter = max(0, ix2 - ix1) * max(0, iy2 - iy1)
        union = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter
        return inter / union if union > 0 else 0.0

    def _match_keypoints_to_persons(self, person_boxes, pose_boxes, pose_kps, min_iou=0.3):
        """
        Pairs each tracked person with the pose detection that overlaps it most (greedy, one-to-one).
        The pose model and the tracker return detections in unrelated orders, so matching by list
        position gave people someone else's skeleton.
        Returns a list aligned with person_boxes (None where no pose overlaps).
        """
        pairs = []
        for pi, pb in enumerate(person_boxes):
            for qi, qb in enumerate(pose_boxes):
                iou = self._iou(pb[:4], qb)
                if iou >= min_iou:
                    pairs.append((iou, pi, qi))
        pairs.sort(reverse=True)
        out, used_p, used_q = [None] * len(person_boxes), set(), set()
        for _iou, pi, qi in pairs:
            if pi in used_p or qi in used_q:
                continue
            out[pi] = pose_kps[qi]
            used_p.add(pi)
            used_q.add(qi)
        return out

    POSTURE_WINDOW = 9

    def _smooth_posture(self, byte_track_id, raw):
        """Majority vote over the last few frames so posture does not flicker between Sitting and Standing."""
        hist = self.posture_history.setdefault(byte_track_id, [])
        hist.append(raw)
        if len(hist) > self.POSTURE_WINDOW:
            hist.pop(0)
        return max(set(hist), key=hist.count) if len(hist) >= 3 else raw

    def _determine_posture(self, px1, py1, px2, py2, keypoints=None):
        w = px2 - px1
        h = py2 - py1
        aspect_ratio = float(h) / max(float(w), 1.0)
        
        if keypoints is not None and len(keypoints) > 0:
            try:
                lhip = keypoints[11]
                rhip = keypoints[12]
                lknee = keypoints[13]
                rknee = keypoints[14]
                
                if lhip[2] > 0.3 and lknee[2] > 0.3:
                    hip_knee_dist_y = abs(lknee[1] - lhip[1])
                    if hip_knee_dist_y < h * 0.22:
                        return "Sitting"
                if rhip[2] > 0.3 and rknee[2] > 0.3:
                    hip_knee_dist_y = abs(rknee[1] - rhip[1])
                    if hip_knee_dist_y < h * 0.22:
                        return "Sitting"
            except Exception:
                pass
                
        if aspect_ratio < 1.95:
            return "Sitting"
        else:
            return "Standing"

    def reset_tracks(self, clear_target=False, camera=None, clear_gallery=True):
        """Resets one camera's tracking state. clear_gallery=False keeps shared identities (other cameras are live)."""
        with self._lock:
            previous = self._cam
            if camera is not None:
                self._cam = camera
            try:
                self._reset_tracks_unlocked(clear_target, clear_gallery)
            finally:
                self._cam = previous

    def _reset_tracks_unlocked(self, clear_target=False, clear_gallery=True):
        """Resets tracking history dictionary and occupant roster, and reloads DB peoples."""
        self.track_history.clear()
        self.occupant_roster.clear()
        self._embed_frame.clear()
        self.db_state.clear()
        self.posture_history.clear()
        self.tracker = None
        if clear_gallery:
            self.known_person_gallery.clear()
        self.active_track_to_person_id.clear()
        self.active_track_to_db_person.clear()
        self.gender_cache.clear()
        self.load_db_peoples()
        if clear_target:
            self.locked_target_id = None
            self.locked_target_track_id = None
            self.locked_target_embedding = None
            self.locked_target_gender = None
            self.locked_target_last_zone = None
            self.locked_target_face_b64 = None
            self.locked_target_lost_frames = 0

    def get_occupant_roster(self, camera=None):
        """Returns occupant roster records sorted by Track ID with per-space time breakdown."""
        with self._lock:
            previous = self._cam
            if camera is not None:
                self._cam = camera
            try:
                return self._build_occupant_roster()
            finally:
                self._cam = previous

    def _build_occupant_roster(self):
        roster_list = []
        import base64
        for tid, occ in sorted(self.occupant_roster.items(), key=lambda x: (isinstance(x[0], str), str(x[0]) if isinstance(x[0], str) else x[0])):
            tot_sec = max(occ['total_seconds'], 0.1)
            zone_percentages = {}
            for z, sec in occ['time_per_zone'].items():
                zone_percentages[z] = round((sec / tot_sec) * 100, 1)
                
            roster_list.append({
                'track_id': occ['track_id'],
                'face_b64': occ['face_b64'],
                'gender': occ['gender'],
                'gender_conf': occ['gender_conf'],
                'posture': occ['posture'],
                'total_seconds': round(occ['total_seconds'], 1),
                'time_per_zone': occ['time_per_zone'],
                'zone_percentages': zone_percentages,
                'current_zone': occ['last_zone'],
                'timeline': list(occ['timeline'])
            })
        return roster_list

    def process_frame(self, *args, camera=None, **kwargs):
        """Processes one frame for `camera` (a CameraState); the default camera is used when omitted."""
        with self._lock:
            previous = self._cam
            if camera is not None:
                self._cam = camera
            try:
                return self._process_frame_unlocked(*args, **kwargs)
            finally:
                self._cam = previous

    def _process_frame_unlocked(self, frame, draw_yolo_objects=True, draw_heads=True, zones=None, target_person_id=None, draw_trails=False, draw_zones=False, frame_dt=0.08):
        """
        Process frame with optional defined virtual project zones/boundaries, persistent tracking,
        Face Re-ID matching for returning persons, motion trajectory trails, target lock highlights, and occupant space-time logging.
        """
        import base64
        start_time = time.time()
        annotated_frame = frame.copy()
        img_h, img_w, _ = frame.shape
        
        male_count = 0
        female_count = 0
        sitting_count = 0
        standing_count = 0
        person_count = 0
        unassigned_count = 0
        object_counts = {}
        total_objects = 0
        zone_stats = {}
        active_person_ids = []
        target_info = None

        # Format target_person_id string comparison
        target_id_str = str(target_person_id).strip() if target_person_id not in [None, '', 'none', 'null', 'All'] else None
        
        # Initialize zone stats dictionary and draw defined project zones
        parsed_zones = []
        if zones:
            for idx, z in enumerate(zones):
                zname = z.get('name') or z.get('project_name') or f"Project Zone {idx+1}"
                pcode = z.get('project_code', '')
                
                pts = z.get('points') or z.get('polygon')
                if not pts and 'box' in z:
                    b = z['box']
                    pts = [[b[0], b[1]], [b[2], b[1]], [b[2], b[3]], [b[0], b[3]]]
                elif not pts:
                    pts = [[0.1, 0.1], [0.5, 0.1], [0.5, 0.5], [0.1, 0.5]]
                
                abs_pts = []
                for pt in pts:
                    abs_pts.append([int(pt[0] * img_w), int(pt[1] * img_h)])
                pts_np = np.array(abs_pts, dtype=np.int32)
                
                if 'color' in z and isinstance(z['color'], (list, tuple)) and len(z['color']) == 3:
                    color = tuple(z['color'])
                else:
                    color = self.ZONE_COLORS[idx % len(self.ZONE_COLORS)]
                
                parsed_zones.append({
                    'name': zname,
                    'project_code': pcode,
                    'pts_np': pts_np,
                    'abs_pts': abs_pts,
                    'color': color
                })
                zone_stats[zname] = {
                    'project_code': pcode,
                    'male': 0, 
                    'female': 0, 
                    'sitting': 0, 
                    'standing': 0, 
                    'total': 0
                }
                
                # Draw boundary on live feed ONLY if draw_zones is True (clean feed by default)
                if draw_zones:
                    cv2.polylines(annotated_frame, [pts_np], isClosed=True, color=color, thickness=2)
                    for p_idx, pt in enumerate(abs_pts):
                        cv2.circle(annotated_frame, tuple(pt), 6, color, -1)
                        cv2.circle(annotated_frame, tuple(pt), 7, (255, 255, 255), 1)
                    
                    p1 = abs_pts[0]
                    z_label = f"{zname}" + (f" ({pcode})" if pcode else "")
                    (tw, th), _ = cv2.getTextSize(z_label, cv2.FONT_HERSHEY_SIMPLEX, 0.55, 2)
                    banner_top = max(0, p1[1] - 26)
                    cv2.rectangle(annotated_frame, (p1[0], banner_top), (p1[0] + tw + 12, p1[1]), color, -1)
                    cv2.putText(annotated_frame, z_label, (p1[0] + 6, max(16, p1[1] - 7)),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 0, 0), 2)
        
        # 1a. Person detection + per-camera ByteTrack (own tracker per camera so IDs never mix between cameras)
        person_boxes = self._track_persons(frame)

        # 1b. Object Detection — executed if draw_yolo_objects is requested
        object_detect_results = None
        if draw_yolo_objects:
            try:
                # Use dedicated object confidence threshold (default 0.10) for small/medium CCTV office items (laptops, chairs, monitors, phones)
                obj_conf_thresh = getattr(self, 'obj_conf', 0.10)
                object_detect_results = self.object_model(
                    frame,
                    conf=obj_conf_thresh,
                    imgsz=self.imgsz,
                    device=self.device,
                    verbose=False
                )[0]
            except Exception:
                object_detect_results = None

        # --- Process Non-Person Object Detection Boxes ---
        if object_detect_results is not None:
            for i, box in enumerate(object_detect_results.boxes):
                cls_id = int(box.cls[0])
                conf_val = float(box.conf[0])
                class_name = self.object_model.names[cls_id]
                if class_name == 'person':
                    continue  # Skip persons — handled by ByteTrack above
                xyxy = box.xyxy[0].cpu().numpy().astype(int)
                x1, y1, x2, y2 = xyxy
                object_counts[class_name] = object_counts.get(class_name, 0) + 1
                total_objects += 1

                if draw_yolo_objects:
                    cv2.rectangle(annotated_frame, (x1, y1), (x2, y2), self.COLOR_OBJECT, 2)
                    label = f"{class_name.capitalize()} {conf_val*100:.0f}%"
                    (tw_obj, th_obj), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.45, 1)
                    
                    if y1 >= 24:
                        banner_top, banner_bot = y1 - 22, y1
                        text_y = y1 - 6
                    else:
                        banner_top, banner_bot = y1, y1 + 22
                        text_y = y1 + 16

                    cv2.rectangle(annotated_frame, (x1, banner_top), (x1 + tw_obj + 8, banner_bot), self.COLOR_OBJECT, -1)
                    cv2.putText(annotated_frame, label, (x1 + 4, text_y),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 0, 0), 1)
        
        # 2. Extract Keypoints with YOLO Pose on GPU (640px = 3x faster, identical posture accuracy)
        pose_keypoints_list = []
        if self.pose_model is not None and len(person_boxes) > 0:
            try:
                pose_results = self.pose_model(frame, conf=self.yolo_conf, imgsz=640, device=self.device, verbose=False)[0]
                if pose_results.keypoints is not None and len(pose_results.keypoints) > 0:
                    pose_keypoints_list = self._match_keypoints_to_persons(
                        person_boxes, pose_results.boxes.xyxy.cpu().numpy(), pose_results.keypoints.data.cpu().numpy())
            except Exception:
                pass

        # 3. Process Persons, Perform Face/Appearance Re-ID Matching & Track Time per Space
        current_person_crops = []  # Per-frame list of ALL detected persons by ByteTrack ID
        detected_persons = []

        self._assign_identities(person_boxes, frame)
        if self.blur_faces:
            for (bx1, by1, bx2, by2, _c, _t) in person_boxes:
                hy2 = by1 + max(int((by2 - by1) * 0.22), 12)
                region = annotated_frame[max(0, by1):min(img_h, hy2), max(0, bx1):min(img_w, bx2)]
                if region.size:
                    k = max(15, (region.shape[1] // 3) | 1)
                    annotated_frame[max(0, by1):min(img_h, hy2), max(0, bx1):min(img_w, bx2)] = cv2.GaussianBlur(region, (k, k), 0)

        for i, (px1, py1, px2, py2, pconf, byte_track_id) in enumerate(person_boxes):
            person_count += 1
            pw = px2 - px1
            ph = py2 - py1
            
            # Extract Upper Body & Head Crop for Gender Classification & Face Re-ID Embedding
            uy1 = max(0, py1)
            uy2 = min(img_h, py1 + max(int(ph * 0.45), 35))
            ux1 = max(0, px1)
            ux2 = min(img_w, px2)
            
            upper_body_crop = frame[uy1:uy2, ux1:ux2]
            
            # Fast Gender Cache: avoid running CPU Caffe Net 16x every single frame
            if byte_track_id in self.gender_cache and self.gender_cache[byte_track_id][1] >= 0.55:
                gender, g_conf = self.gender_cache[byte_track_id]
            else:
                gender, g_conf = classify_gender(self.gender_net, upper_body_crop)
                self.gender_cache[byte_track_id] = (gender, g_conf)
            
            # Identity was resolved for the whole frame above (batched ReID); unresolved tiny/partial
            # detections keep a track-scoped label so they can never collide with a real identity.
            track_id = self.active_track_to_person_id.get(byte_track_id, f"T{byte_track_id}")
            active_person_ids.append(track_id)

            # Person Center Point for Trajectory Trail
            pcx = (px1 + px2) // 2
            pcy = (py1 + py2) // 2
            
            # Save Trajectory Points in Track History
            if track_id not in self.track_history:
                self.track_history[track_id] = []
            self.track_history[track_id].append((pcx, pcy))
            if len(self.track_history[track_id]) > 30:
                self.track_history[track_id].pop(0)

            # Check Custom 4-Point Polygon Boundary Membership (Calculated in background even if draw_zones is False)
            assigned_zone_name = None
            assigned_zone_color = None
            for z in parsed_zones:
                dist = cv2.pointPolygonTest(z['pts_np'], (float(pcx), float(pcy)), False)
                if dist >= 0:
                    assigned_zone_name = z['name']
                    assigned_zone_color = z['color']
                    break
            
            zone_key = assigned_zone_name if assigned_zone_name else 'Floating / Unassigned'
            if not assigned_zone_name:
                unassigned_count += 1

            # Posture Determination
            kps = pose_keypoints_list[i] if i < len(pose_keypoints_list) else None
            posture = self._smooth_posture(byte_track_id, self._determine_posture(px1, py1, px2, py2, keypoints=kps))
            
            if posture == "Sitting":
                sitting_count += 1
            else:
                standing_count += 1
                
            # Convert upper body crop to base64 JPEG
            face_b64 = ""
            if upper_body_crop.size > 0:
                try:
                    shown = upper_body_crop
                    if self.blur_faces:      # privacy: coarse pixelation, identity stays unreadable
                        small = cv2.resize(shown, (max(4, shown.shape[1] // 14), max(4, shown.shape[0] // 14)))
                        shown = cv2.resize(small, (shown.shape[1], shown.shape[0]), interpolation=cv2.INTER_NEAREST)
                    _, buf = cv2.imencode('.jpg', shown)
                    face_b64 = f"data:image/jpeg;base64,{base64.b64encode(buf).decode('utf-8')}"
                except Exception:
                    pass

            # Maintain Occupant Roster Face & Time Spent Data (Accumulates for Returning Persons under SAME ID!)
            if track_id not in self.occupant_roster:
                self.occupant_roster[track_id] = {
                    'track_id': track_id,
                    'face_b64': face_b64,
                    'gender': gender,
                    'gender_conf': round(float(g_conf), 2),
                    'posture': posture,
                    'total_seconds': 0.0,
                    'time_per_zone': {},
                    'last_zone': None,
                    'timeline': []
                }
            
            occ = self.occupant_roster[track_id]
            if face_b64 and (not occ.get('face_b64') or g_conf >= occ.get('gender_conf', 0)):
                occ['face_b64'] = face_b64
                occ['gender'] = gender
                occ['gender_conf'] = round(float(g_conf), 2)
            
            occ['posture'] = posture
            occ['total_seconds'] = round(occ['total_seconds'] + frame_dt, 1)
            occ['time_per_zone'][zone_key] = round(occ['time_per_zone'].get(zone_key, 0.0) + frame_dt, 1)
            
            if occ['last_zone'] != zone_key:
                time_str = time.strftime('%H:%M:%S', time.localtime())
                occ['timeline'].append({
                    'timestamp': time_str,
                    'zone': zone_key,
                    'event': f"Entered {zone_key}"
                })
                occ['last_zone'] = zone_key

            if gender == 'Male':
                male_count += 1
                box_color = self.COLOR_MALE
            elif gender == 'Female':
                female_count += 1
                box_color = self.COLOR_FEMALE
            else:
                box_color = (200, 200, 200)
                
            # Record per-project metrics
            if assigned_zone_name and assigned_zone_name in zone_stats:
                zone_stats[assigned_zone_name]['total'] += 1
                if gender == 'Male':
                    zone_stats[assigned_zone_name]['male'] += 1
                elif gender == 'Female':
                    zone_stats[assigned_zone_name]['female'] += 1
                if posture == 'Sitting':
                    zone_stats[assigned_zone_name]['sitting'] += 1
                else:
                    zone_stats[assigned_zone_name]['standing'] += 1

            detected_persons.append({
                'idx': i,
                'bbox': (px1, py1, px2, py2),
                'pconf': pconf,
                'byte_track_id': byte_track_id,
                'track_id': track_id,
                'gender': gender,
                'g_conf': g_conf,
                'feat': self._identity_feature(track_id),
                'assigned_zone_name': assigned_zone_name,
                'assigned_zone_color': assigned_zone_color,
                'zone_key': zone_key,
                'posture': posture,
                'face_b64': face_b64,
                'box_color': box_color
            })

        # -------------------------------------------------------------
        # TARGET LOCK & AUTOMATIC RE-ACQUISITION ENGINE
        # -------------------------------------------------------------
        locked_person_idx = None
        reacquired = False

        if target_id_str is None:
            self.locked_target_id = None
            self.locked_target_track_id = None
            self.locked_target_embedding = None
            self.locked_target_gender = None
            self.locked_target_lost_frames = 0
        else:
            if self.locked_target_id != target_id_str:
                self.locked_target_id = target_id_str
                self.locked_target_track_id = None
                self.locked_target_embedding = None
                self.locked_target_gender = None
                self.locked_target_lost_frames = 0
                
                # Check if target is a registered DB person
                for db_id, db_p in self.db_peoples.items():
                    if db_p['person_code'] == target_id_str or target_id_str in db_p['name']:
                        if db_p['embedding'] is not None:
                            self.locked_target_embedding = db_p['embedding'].copy()
                            self.locked_target_gender = db_p['gender']
                        break

            # 1. Attempt direct match with current active detections
            for idx, p in enumerate(detected_persons):
                bt_id_str = str(p['byte_track_id'])
                trk_id_str = str(p['track_id'])
                
                if (self.locked_target_track_id is not None and p['byte_track_id'] == self.locked_target_track_id) or \
                   (bt_id_str == self.locked_target_id) or \
                   (trk_id_str == self.locked_target_id) or \
                   (self.locked_target_id in trk_id_str):
                    locked_person_idx = idx
                    break

            # 2. If direct track match lost (ByteTrack ID swap, occlusion, connection drop), RE-ACQUIRE VIA RE-ID!
            if locked_person_idx is None and self.locked_target_embedding is not None and len(detected_persons) > 0:
                best_sim = -1.0
                best_idx = None
                for idx, p in enumerate(detected_persons):
                    if p['feat'] is not None:
                        sim = float(np.dot(p['feat'], self.locked_target_embedding))
                        if self.locked_target_gender and p['gender'] and p['gender'] != 'Unknown':
                            if p['gender'] != self.locked_target_gender:
                                sim -= 0.15
                        if sim > best_sim:
                            best_sim = sim
                            best_idx = idx

                if best_sim >= self.REACQUIRE_SIM and best_idx is not None:
                    locked_person_idx = best_idx
                    reacquired = True
                    old_tid = self.locked_target_track_id
                    cand = detected_persons[best_idx]
                    print(f"[Target Lock] Re-Acquired! Target #{self.locked_target_id} re-linked from Track #{old_tid} -> Track #{cand['byte_track_id']} (Sim: {best_sim:.2f})", flush=True)

            # 3. Update persistent target memory & state
            if locked_person_idx is not None:
                tp = detected_persons[locked_person_idx]
                self.locked_target_track_id = tp['byte_track_id']
                self.locked_target_gender = tp['gender']
                self.locked_target_last_zone = tp['assigned_zone_name']
                self.locked_target_last_seen = time.time()
                self.locked_target_lost_frames = 0
                self.locked_target_face_b64 = tp['face_b64']
                
                if tp['feat'] is not None:
                    if self.locked_target_embedding is None:
                        self.locked_target_embedding = tp['feat'].copy()
                    else:
                        updated_emb = 0.82 * self.locked_target_embedding + 0.18 * tp['feat']
                        norm = np.linalg.norm(updated_emb)
                        if norm > 0:
                            self.locked_target_embedding = updated_emb / norm

                target_info = {
                    'track_id': tp['byte_track_id'],
                    'target_id': self.locked_target_id,
                    'gender': tp['gender'],
                    'posture': tp['posture'],
                    'zone': tp['assigned_zone_name'] or 'Floating / Unassigned',
                    'found': True,
                    'reacquired': reacquired,
                    'status': 'RE-ACQUIRED (AUTO-LINKED)' if reacquired else 'ACTIVE TRACKING'
                }
            else:
                self.locked_target_lost_frames += 1
                target_info = {
                    'track_id': self.locked_target_id,
                    'target_id': self.locked_target_id,
                    'found': False,
                    'reacquired': False,
                    'status': f'SEARCHING / RE-ACQUIRING (Lost {self.locked_target_lost_frames}f)',
                    'zone': self.locked_target_last_zone or 'Last seen in frame',
                    'gender': self.locked_target_gender or 'Unknown',
                    'posture': 'Unknown'
                }

        # 4. Render Overlays and Build Person Crops
        for p in detected_persons:
            is_target_locked = (locked_person_idx is not None and p['idx'] == detected_persons[locked_person_idx]['idx'])
            px1, py1, px2, py2 = p['bbox']

            # Append to current frame crop list
            current_person_crops.append({
                'track_id': p['byte_track_id'],
                'person_id': str(p['track_id']),
                'face_b64': p.get('face_b64') or self.occupant_roster.get(p['track_id'], {}).get('face_b64', ''),
                'gender': p['gender'],
                'gender_conf': round(float(p['g_conf']), 2),
                'posture': p['posture'],
                'zone': p['zone_key'],
                'conf': round(float(p['pconf']), 2),
                'bbox': [int(px1), int(py1), int(px2), int(py2)],
                'is_target': is_target_locked
            })

            # Optional Trajectory Path Trails
            if draw_trails and p['track_id'] in self.track_history and len(self.track_history[p['track_id']]) > 1:
                trail_pts = np.array(self.track_history[p['track_id']], dtype=np.int32).reshape((-1, 1, 2))
                trail_color = (0, 255, 255) if is_target_locked else (180, 180, 180)
                thickness = 4 if is_target_locked else 2
                cv2.polylines(annotated_frame, [trail_pts], isClosed=False, color=trail_color, thickness=thickness)

            # Render Person Bounding Boxes & Target Lock Reticle
            if draw_heads:
                if is_target_locked:
                    self._draw_target_reticle(annotated_frame, (px1, py1, px2, py2), color=(0, 210, 255), thickness=3)
                    
                    status_lbl = "TARGET RE-ACQUIRED" if reacquired else "TARGET LOCKED"
                    tag = f"[{status_lbl}] [ID #{p['byte_track_id']}] | {p['gender']} ({p['g_conf']*100:.0f}%) | {p['posture']}"
                    (tw, th), _ = cv2.getTextSize(tag, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 2)
                    
                    if py1 >= 28:
                        banner_top, banner_bot = py1 - 26, py1
                        text_y = py1 - 7
                    else:
                        banner_top, banner_bot = py1, py1 + 26
                        text_y = py1 + 19

                    cv2.rectangle(annotated_frame, (px1, banner_top), (px1 + tw + 10, banner_bot), (0, 210, 255), -1)
                    cv2.putText(annotated_frame, tag, (px1 + 5, text_y),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 2)
                elif target_id_str is None:
                    # When no target is selected (All mode), display all person bounding boxes
                    border_color = p['assigned_zone_color'] if (draw_zones and p['assigned_zone_color']) else p['box_color']
                    cv2.rectangle(annotated_frame, (px1, py1), (px2, py2), border_color, 2)
                    
                    tag = f"ID #{p['byte_track_id']} | {p['gender']} ({p['g_conf']*100:.0f}%) | {p['posture']}"
                    (tw, th), _ = cv2.getTextSize(tag, cv2.FONT_HERSHEY_SIMPLEX, 0.45, 2)
                    
                    if py1 >= 26:
                        banner_top, banner_bot = py1 - 24, py1
                        text_y = py1 - 6
                    else:
                        banner_top, banner_bot = py1, py1 + 24
                        text_y = py1 + 17

                    cv2.rectangle(annotated_frame, (px1, banner_top), (px1 + tw + 8, banner_bot), border_color, -1)
                    cv2.putText(annotated_frame, tag, (px1 + 4, text_y),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 0, 0), 2)
                # If target_id_str is selected and this is NOT the target, box is completely hidden for focus

        elapsed = time.time() - start_time
        instant_fps = 1.0 / max(elapsed, 0.001)
        if self._fps_ema is None:
            self._fps_ema = instant_fps
        else:
            self._fps_ema = 0.75 * self._fps_ema + 0.25 * instant_fps
        fps = round(self._fps_ema, 1)

        stats = {
            'male_count': male_count,
            'female_count': female_count,
            'person_count': person_count,
            'unassigned_count': unassigned_count,
            'head_count': person_count,
            'sitting_count': sitting_count,
            'standing_count': standing_count,
            'object_counts': object_counts,
            'total_objects': total_objects,
            'zone_stats': zone_stats,
            'active_person_ids': active_person_ids,
            'current_person_crops': current_person_crops,
            'target_info': target_info,
            'frame_w': int(img_w),
            'frame_h': int(img_h),
            'fps': fps
        }

        return annotated_frame, stats

    def run_diagnostic_test(self):
        """Runs a quick diagnostic benchmark test on dummy frame to verify model connections & inference latency."""
        import time
        dummy_frame = np.zeros((480, 640, 3), dtype=np.uint8)
        cv2.rectangle(dummy_frame, (100, 100), (300, 400), (120, 120, 120), -1)
        
        t0 = time.time()
        annotated, stats = self.process_frame(dummy_frame)
        latency_ms = round((time.time() - t0) * 1000, 1)
        
        return {
            'device': self.device.upper(),
            'cuda_available': (self.device == 'cuda'),
            'gpu_name': torch.cuda.get_device_name(0) if self.device == 'cuda' else 'CPU',
            'half_precision': self.half,
            'yolo_status': 'ONLINE' if self.yolo_model is not None else 'OFFLINE',
            'pose_status': 'ONLINE' if self.pose_model is not None else 'OFFLINE',
            'gender_status': 'ONLINE' if self.gender_net is not None else 'OFFLINE',
            'db_peoples_count': len(self.db_peoples),
            'inference_latency_ms': latency_ms,
            'fps_capacity': stats.get('fps', 0.0)
        }


def _delegate_to_camera(name):
    return property(lambda self: getattr(self._cam, name), lambda self, value: setattr(self._cam, name, value))


# Per-camera attributes read/write the currently selected CameraState, so the existing detector code is unchanged.
for _name in ('tracker', 'track_history', 'occupant_roster', 'active_track_to_person_id', 'active_track_to_db_person',
              'gender_cache', 'posture_history', '_embed_frame', 'db_state', 'locked_target_id', 'locked_target_track_id',
              'locked_target_embedding', 'locked_target_gender', 'locked_target_last_zone',
              'locked_target_face_b64', 'locked_target_last_seen', 'locked_target_lost_frames'):
    setattr(HeadGenderYOLODetector, _name, _delegate_to_camera(_name))
