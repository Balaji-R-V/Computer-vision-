"""
Background RTSP stream workers (one per camera).

Detection runs in a worker thread that is independent of any browser connection, so switching pages,
refreshing, or closing the tab does not interrupt tracking or occupant time logging. The MJPEG
endpoint only *serves* the latest annotated frame; it never drives detection.

Each worker owns its own CameraState (tracker, roster, caches). The detector, its models and the
identity gallery are shared, so one person keeps the same identity across cameras. Frame processing is
serialized by the detector lock, so total throughput is shared between cameras.
"""
import os
import threading
import time
import urllib.parse

import cv2
import numpy as np

import alerts
import app_settings
import database
from detector import CameraState

# TCP transport is far more reliable than UDP for CCTV over Wi-Fi/VPN. Must be set before the first capture opens.
os.environ.setdefault('OPENCV_FFMPEG_CAPTURE_OPTIONS', 'rtsp_transport;tcp')

OCCUPANT_FLUSH_SECONDS = 10.0
PRESENCE_SAMPLE_SECONDS = 60.0   # reports assume one presence sample per minute
MAX_FRAME_GAP_SECONDS = 1.0      # cap dt so a stall never credits a person with minutes of presence
MAX_CONSECUTIVE_READ_FAILURES = 5
MAX_BACKOFF_SECONDS = 15.0
HEAT_COLS, HEAT_ROWS = 32, 18
MAX_CAMERAS = int(os.environ.get('AEGIS_MAX_CAMERAS', 4))


def camera_label(rtsp_url):
    """host:port/path without credentials - safe to show in the UI and alerts."""
    try:
        p = urllib.parse.urlparse(rtsp_url or '')
        return f"{p.hostname}{':' + str(p.port) if p.port else ''}{p.path}"
    except Exception:
        return rtsp_url or 'camera'


def _offline_frame(message, sub=''):
    frame = np.zeros((540, 960, 3), dtype=np.uint8)
    for y in range(0, 540, 40):
        cv2.line(frame, (0, y), (960, y), (18, 26, 44), 1)
    for x in range(0, 960, 40):
        cv2.line(frame, (x, 0), (x, 540), (18, 26, 44), 1)
    cv2.putText(frame, "CAMERA OFFLINE", (40, 240), cv2.FONT_HERSHEY_SIMPLEX, 1.4, (60, 60, 230), 3)
    cv2.putText(frame, message, (40, 290), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (200, 200, 200), 2)
    if sub:
        cv2.putText(frame, sub, (40, 325), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (140, 140, 140), 1)
    return frame


def _encode(frame):
    ok, buf = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 82])
    return buf.tobytes() if ok else None


class RtspWorker(threading.Thread):
    def __init__(self, stream_id, config, detector, stats_store, probe):
        super().__init__(daemon=True, name=f"rtsp-{stream_id}")
        self.stream_id = stream_id
        self.config = config            # live dict shared with the server, edited by UI controls
        self.detector = detector
        self.stats_store = stats_store
        self.probe = probe              # callable(rtsp_url) -> bool, fast reachability check
        self.camera = CameraState()     # this camera's tracker/roster/caches inside the shared detector
        self.label = camera_label(config.get('rtsp_url'))
        self.status = 'connecting'      # connecting | live | offline | stopped
        self.last_error = ''
        self.frame_id = 0
        self.jpeg = None
        self._cond = threading.Condition()
        self._stop_evt = threading.Event()
        self._last_flush = 0.0
        self._last_presence = 0.0
        self._heat = [0.0] * (HEAT_COLS * HEAT_ROWS)
        self._ref_saved = False
        self._last_error_log = {}
        self.recorder = alerts.ClipRecorder()
        self.alerts = alerts.AlertEngine(stream_id, self.label, self.recorder)

    # ---- viewer API -------------------------------------------------------------------------
    def wait_frame(self, last_id, timeout=5.0):
        """Blocks until a newer frame than last_id exists (or the worker stops). Returns (frame_id, jpeg)."""
        with self._cond:
            self._cond.wait_for(
                lambda: (self.jpeg is not None and self.frame_id != last_id) or self._stop_evt.is_set(), timeout)
            return self.frame_id, self.jpeg

    @property
    def stopped(self):
        return self._stop_evt.is_set()

    def stop(self):
        self._stop_evt.set()
        with self._cond:
            self._cond.notify_all()
        if self.is_alive() and threading.current_thread() is not self:
            self.join(timeout=8)

    # ---- internals --------------------------------------------------------------------------
    def _publish(self, frame, stats):
        jpeg = _encode(frame)
        if stats is not None:
            stats['camera_status'] = self.status
            stats['stream_id'] = self.stream_id
            stats['camera_label'] = self.label
            stats['is_rtsp'] = True
            stats['pct'] = 100.0
            self.stats_store[self.stream_id] = stats
        with self._cond:
            self.jpeg = jpeg
            self.frame_id += 1
            self._cond.notify_all()

    def _publish_offline(self, message):
        self.status = 'offline'
        self.last_error = message
        self._publish(_offline_frame(message, self.label), {
            'male_count': 0, 'female_count': 0, 'sitting_count': 0, 'standing_count': 0,
            'person_count': 0, 'total_objects': 0, 'object_counts': {}, 'fps': 0.0,
            'current_person_crops': [], 'status_message': message,
        })

    def _open(self):
        if not self.probe(self.config.get('rtsp_url', '')):
            return None
        url = self.config.get('formatted_url') or self.config.get('rtsp_url')
        cap = cv2.VideoCapture(url, cv2.CAP_FFMPEG)
        if not cap.isOpened():
            cap.release()
            return None
        try:
            cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        except Exception:
            pass
        return cap

    def _flush(self, force=False):
        now = time.time()
        if not force and now - self._last_flush < OCCUPANT_FLUSH_SECONDS:
            return
        self._last_flush = now
        try:
            privacy = app_settings.get('privacy')
            database.save_occupants(self.stream_id, self.detector.get_occupant_roster(camera=self.camera),
                                    store_faces=privacy['store_faces'])
            ref = f"/static/clips/ref_{self.stream_id}.jpg" if self._ref_saved else ''
            database.save_heatmap(self.stream_id, self.label, HEAT_COLS, HEAT_ROWS,
                                  [round(v, 1) for v in self._heat], ref)
        except Exception as e:
            print(f"Log flush failed for {self.stream_id}: {e}", flush=True)

    def _record_analytics(self, annotated, stats, now, dt):
        """Heatmap accumulation, once-a-minute presence samples and the reference image for reports."""
        people = stats.get('current_person_crops') or []
        fw, fh = stats.get('frame_w') or 1, stats.get('frame_h') or 1
        for p in people:
            bb = p.get('bbox')
            if bb:
                cx = min(HEAT_COLS - 1, max(0, int(((bb[0] + bb[2]) / 2) / fw * HEAT_COLS)))
                cy = min(HEAT_ROWS - 1, max(0, int(bb[3] / fh * HEAT_ROWS)))      # feet position
                self._heat[cy * HEAT_COLS + cx] += dt
        if now - self._last_presence >= PRESENCE_SAMPLE_SECONDS:
            self._last_presence = now
            counts = {'*': len(people)}
            for p in people:
                z = p.get('zone') or alerts.UNASSIGNED
                counts[z] = counts.get(z, 0) + 1
            try:
                database.add_presence_samples(self.stream_id, self.label, counts)
            except Exception as e:
                print(f"Presence sample failed: {e}", flush=True)
        if not self._ref_saved:
            try:
                h, w = annotated.shape[:2]
                small = cv2.resize(annotated, (640, int(h * 640 / w))) if w > 640 else annotated
                cv2.imwrite(os.path.join(alerts.CLIPS_DIR, f"ref_{self.stream_id}.jpg"), small)
                self._ref_saved = True
            except Exception:
                pass

    def _safe(self, fn, *args, **kwargs):
        """Runs a bookkeeping call (database, alerts) so a failure there can never stop the camera."""
        try:
            return fn(*args, **kwargs)
        except Exception as e:
            name = getattr(fn, '__name__', 'call')
            last = self._last_error_log.get(name, 0.0)
            if time.time() - last > 30:          # a persistent fault must not flood the log (once per 30 s per call)
                self._last_error_log[name] = time.time()
                print(f"[{self.stream_id}] {name} failed: {e}", flush=True)
            return None

    def run(self):
        """Supervisor: keeps the camera loop alive through any unexpected error until stop() is called."""
        self._safe(database.start_session, self.stream_id, source=self.label)
        print(f"[{self.stream_id}] worker started ({self.label})", flush=True)
        try:
            while not self._stop_evt.is_set():
                try:
                    self._loop()
                    break
                except Exception as e:
                    import traceback
                    traceback.print_exc()
                    print(f"[{self.stream_id}] worker error, restarting loop in 3 s: {e}", flush=True)
                    self.status = 'offline'
                    self._stop_evt.wait(3)
        finally:
            self.status = 'stopped'
            self._flush(force=True)
            self._safe(database.end_session, self.stream_id)
            with self._cond:
                self._cond.notify_all()
            print(f"[{self.stream_id}] worker stopped", flush=True)

    def _loop(self):
        cap = None
        backoff = 1.0
        failures = 0
        last_t = None
        try:
            while not self._stop_evt.is_set():
                now = time.time()
                self._safe(self.recorder.tick, now)

                if cap is None:
                    self.status = 'connecting'
                    cap = self._open()
                    if cap is None:
                        self._publish_offline('Camera unreachable - retrying')
                        self._safe(self.alerts.on_offline, time.time())
                        if self._stop_evt.wait(backoff):
                            break
                        backoff = min(backoff * 2, MAX_BACKOFF_SECONDS)
                        continue
                    backoff = 1.0
                    failures = 0
                    last_t = None
                    print(f"[{self.stream_id}] camera connected", flush=True)

                ok, frame = cap.read()
                if not ok or frame is None:
                    failures += 1
                    if failures >= MAX_CONSECUTIVE_READ_FAILURES:
                        print(f"[{self.stream_id}] stream lost, reconnecting", flush=True)
                        if self.alerts.current_frame is not None:
                            self._safe(self.alerts.remember_frame, self.alerts.current_frame)    # snapshot for a camera-offline alert
                        cap.release()
                        cap = None
                        self._publish_offline('Stream lost - reconnecting')
                        self._safe(self.alerts.on_offline, time.time())
                        self._flush(force=True)
                    else:
                        time.sleep(0.05)
                    continue
                failures = 0

                now = time.time()
                dt = min(now - last_t, MAX_FRAME_GAP_SECONDS) if last_t else 0.04
                last_t = now

                cfg = self.config
                try:
                    with self.detector._lock:
                        self.detector.yolo_conf = cfg.get('yolo_conf', 0.35)
                        self.detector.gender_conf = cfg.get('gender_conf', 0.40)
                        self.detector.obj_conf = cfg.get('obj_conf', 0.10)
                        annotated, stats = self.detector.process_frame(
                            frame,
                            camera=self.camera,
                            draw_yolo_objects=cfg.get('draw_objects', True),
                            draw_heads=cfg.get('draw_heads', True),
                            zones=cfg.get('zones', []),
                            target_person_id=cfg.get('target_person_id'),
                            draw_trails=cfg.get('draw_trails', False),
                            draw_zones=cfg.get('draw_zones', False),
                            frame_dt=dt,
                        )
                except Exception as e:
                    print(f"[{self.stream_id}] frame processing error: {e}", flush=True)
                    time.sleep(0.05)
                    continue

                if self.status != 'live':
                    self._safe(self.alerts.on_online, now)
                self.status = 'live'
                self.last_error = ''
                stats['current_frame'] = self.frame_id
                self._publish(annotated, stats)

                self.alerts.current_frame = annotated
                self._safe(self.recorder.add, now, annotated)
                self._safe(self.alerts.on_frame, stats.get('current_person_crops') or [], now)
                self._safe(self._record_analytics, annotated, stats, now, dt)
                self._flush()
        finally:
            if cap is not None:
                cap.release()


class StreamManager:
    """Owns the RTSP workers, one per camera (up to AEGIS_MAX_CAMERAS)."""

    def __init__(self, detector, stats_store, probe):
        self.detector = detector
        self.stats_store = stats_store
        self.probe = probe
        self._lock = threading.Lock()
        self._workers = {}

    def get(self, stream_id):
        with self._lock:
            return self._workers.get(stream_id)

    def all_active(self):
        """[(stream_id, worker)] for running workers, oldest first."""
        with self._lock:
            return [(sid, w) for sid, w in self._workers.items() if not w.stopped and w.is_alive()]

    def active(self):
        """The most recently started running worker (kept for single-camera callers)."""
        running = self.all_active()
        return running[-1] if running else (None, None)

    def ensure(self, stream_id, config):
        """Starts the worker for stream_id if it is not already running. Raises RuntimeError past the camera limit."""
        with self._lock:
            existing = self._workers.get(stream_id)
            if existing and existing.is_alive() and not existing.stopped:
                return existing
            running = [sid for sid, w in self._workers.items() if not w.stopped and w.is_alive() and sid != stream_id]
            if len(running) >= MAX_CAMERAS:
                raise RuntimeError(f"Camera limit reached ({MAX_CAMERAS}). Disconnect a camera first.")
            worker = RtspWorker(stream_id, config, self.detector, self.stats_store, self.probe)
            self._workers[stream_id] = worker
        worker.start()
        return worker

    def stop(self, stream_id=None):
        with self._lock:
            targets = [w for sid, w in self._workers.items() if stream_id in (None, sid)]
        for w in targets:
            w.stop()

    def stop_all(self):
        self.stop(None)
