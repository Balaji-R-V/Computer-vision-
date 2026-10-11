import sys

# Log lines contain emoji; on a legacy Windows console (cp1252) a print() would raise and could kill a worker thread.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

import os
import io
import csv
import hmac
import cv2
import json
import tempfile
import base64
import time
import urllib.parse
import numpy as np
from flask import Flask, render_template, request, jsonify, send_from_directory, Response
from engine_manager import EngineManager
from stream_manager import StreamManager, MAX_CAMERAS
import app_settings
import auth
import database
import routes_extra
import secrets_store

START_TIME = time.time()
app = Flask(__name__, template_folder='templates', static_folder='static')
app.config['TEMPLATES_AUTO_RELOAD'] = True

# Ensure uploads and outputs directory exists
UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), 'static', 'uploads')
OUTPUT_FOLDER = os.path.join(os.path.dirname(__file__), 'static', 'outputs')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

# Instantiate Dual Engine Architecture (Local GPU Engine + AWS Rekognition Engine)
print("Initializing Dual Vision Engine (GPU + AWS Rekognition)...")
engine_manager = EngineManager()
detector = engine_manager
app.config['engine_manager'] = engine_manager


def bgr_to_base64(bgr_img):
    """Converts a BGR OpenCV image array to base64 JPEG string."""
    _, buffer = cv2.imencode('.jpg', bgr_img)
    encoded = base64.b64encode(buffer).decode('utf-8')
    return f"data:image/jpeg;base64,{encoded}"


def format_rtsp_url(rtsp_url, username=None, password=None):
    """
    Formats RTSP stream URL with URL-encoded username & password.
    Example: rtsp://192.168.1.2:554/Streaming/Channels/401, username="admin", password="in22labs@2026"
    Result: rtsp://admin:in22labs%402026@192.168.1.2:554/Streaming/Channels/401
    """
    if not rtsp_url:
        return ""
    rtsp_url = rtsp_url.strip()
    if username and password and "@" not in rtsp_url.replace("rtsp://", ""):
        encoded_user = urllib.parse.quote(username, safe="")
        encoded_pass = urllib.parse.quote(password, safe="")
        if rtsp_url.startswith("rtsp://"):
            rest = rtsp_url[7:]
            return f"rtsp://{encoded_user}:{encoded_pass}@{rest}"
    return rtsp_url


# Accounts, roles and login (turns on automatically once an account exists or AEGIS_PASSWORD is set)
auth.init_auth(app)


@app.route('/health')
def health():
    """Liveness/readiness probe for uptime monitors. Never requires login."""
    cams = [{'stream_id': sid, 'label': w.label, 'camera_status': w.status} for sid, w in stream_manager.all_active()]
    try:
        database.get_state('health_probe')
        db_ok = True
    except Exception:
        db_ok = False
    return jsonify({
        'status': 'ok' if db_ok else 'degraded',
        'device': detector.device,
        'database': db_ok,
        'cameras': cams,
        'live_stream': cams[0] if cams else None,
        'uptime_seconds': int(time.time() - START_TIME),
    })


@app.route('/')
def index():
    """Serves the main web application UI."""
    return render_template('index.html')


@app.route('/occupants')
def occupants_page():
    """Serves the Occupant Face Roster & Space Time Log Gallery Page."""
    return render_template('occupants.html')


@app.route('/peoples')
def peoples_page():
    """Serves the Registered People & Re-ID Database Management Page."""
    return render_template('peoples.html')


@app.route('/test_connection')
def test_connection_page():
    """Serves the Model & RTSP Stream Connection Test Panel Page."""
    return render_template('test_connection.html')


@app.route('/api/test_model_connection', methods=['GET', 'POST'])
def test_model_connection():
    """Runs AI model connection health checks and diagnostic benchmark test."""
    try:
        diag = detector.run_diagnostic_test()
        return jsonify({
            'success': True,
            'models': diag,
            'timestamp': time.strftime('%Y-%m-%d %H:%M:%S')
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


def _resolve_roster(requested):
    """(session_id, roster, is_live, camera_status) for a live camera, a saved session, or the best default."""
    live = dict(stream_manager.all_active())
    if requested and requested in live:
        w = live[requested]
        return requested, detector.get_occupant_roster(camera=w.camera), True, w.status
    if requested:
        return requested, database.get_occupants(requested), False, None
    if live:
        sid, w = next(iter(live.items()))
        return sid, detector.get_occupant_roster(camera=w.camera), True, w.status
    latest = database.get_latest_session_id()
    return latest, (database.get_occupants(latest) if latest else []), False, None


@app.route('/api/occupants_data')
@app.route('/api/occupants_data/<filename>')
def get_occupants_data(filename=None):
    """
    Returns the occupant roster with time spent per workspace zone.
    Live camera -> in-memory roster; otherwise the saved log of the requested (or latest) session,
    so the page is never empty just because nothing is streaming right now.
    """
    session_id, roster, live, camera_status = _resolve_roster(request.args.get('session'))
    live_ids = {sid for sid, _ in stream_manager.all_active()}
    sessions = database.list_sessions(30)
    for sess in sessions:
        sess['live'] = sess['session_id'] in live_ids
    return jsonify({
        'success': True,
        'filename': filename,
        'session_id': session_id,
        'live': live,
        'camera_status': camera_status,
        'sessions': sessions,
        'occupant_count': len(roster),
        'occupants': roster
    })


@app.route('/api/occupants_export.csv')
def export_occupants_csv():
    """Downloads the occupant time log (live or a saved session) as CSV, one row per occupant per space."""
    session_id, roster, _live, _status = _resolve_roster(request.args.get('session'))

    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(['session', 'track_id', 'gender', 'gender_confidence', 'posture', 'space',
                     'seconds_in_space', 'percent_of_time', 'total_seconds'])
    for o in roster:
        for space, secs in (o.get('time_per_zone') or {'-': 0}).items():
            writer.writerow([session_id, o['track_id'], o['gender'], o['gender_conf'], o['posture'], space,
                             secs, (o.get('zone_percentages') or {}).get(space, 0), o['total_seconds']])
    safe_name = ''.join(c for c in str(session_id) if c.isalnum() or c in '-_') or 'occupants'
    return Response(out.getvalue(), mimetype='text/csv',
                    headers={'Content-Disposition': f'attachment; filename=occupants_{safe_name}.csv'})


# -------------------------------------------------------------------
# PEOPLE DATABASE API ENDPOINTS
# -------------------------------------------------------------------

@app.route('/api/peoples', methods=['GET'])
def get_peoples_list():
    """Returns list of all registered people in the SQLite database."""
    peoples = database.get_all_peoples()
    return jsonify({
        'success': True,
        'count': len(peoples),
        'peoples': peoples
    })


@app.route('/api/peoples/<person_id>', methods=['GET'])
def get_person(person_id):
    """Returns details for a single person by ID or person_code."""
    person = database.get_person_by_id(person_id)
    if not person:
        return jsonify({'error': 'Person not found'}), 404
    return jsonify({'success': True, 'person': person})


def _photos_from(data):
    """All photos sent with a request: `photos` (list) and/or the single legacy `photo_b64`."""
    photos = [p for p in (data.get('photos') or []) if isinstance(p, str) and p]
    if data.get('photo_b64') and data['photo_b64'] not in photos:
        photos.insert(0, data['photo_b64'])
    return photos


def _store_photos(person_id, photos):
    """Analyses and saves each photo; returns one report per photo (errors reported, never fatal)."""
    reports = []
    for photo in photos:
        try:
            reports.append(detector.add_person_photo(person_id, photo, reload=False))
        except Exception as e:
            reports.append({'usable': False, 'notes': [str(e)]})
    detector.load_db_peoples()
    return reports


@app.route('/api/peoples', methods=['POST'])
def add_new_person():
    """Registers a person. Every photo is analysed for face and body recognition and stored as an exemplar."""
    try:
        data = request.json or {}
        name = data.get('name', '').strip()
        if not name:
            return jsonify({'error': 'Name is required'}), 400

        photos = _photos_from(data)
        new_person = database.add_person(name, data.get('gender', 'Unspecified'), data.get('department', 'General'),
                                         data.get('role', 'Occupant'), photos[0] if photos else '', '[]', data.get('notes', ''))
        reports = _store_photos(new_person['id'], photos)

        return jsonify({
            'success': True,
            'message': f"Registered person {name} ({new_person['person_code']})",
            'person': new_person,
            'photo_reports': reports,
        })
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/api/peoples/<person_id>', methods=['PUT'])
def update_person_record(person_id):
    """Updates a person's details. Any new photos sent are analysed and added to their recognition photos."""
    try:
        data = request.json or {}
        name = data.get('name', '').strip()
        if not name:
            return jsonify({'error': 'Name is required'}), 400

        existing = database.get_person_by_id(person_id)
        if not existing:
            return jsonify({'error': 'Person not found'}), 404
        updated_person = database.update_person(person_id, name, data.get('gender', 'Unspecified'),
                                                data.get('department', 'General'), data.get('role', 'Occupant'),
                                                data.get('notes', ''))
        photos = _photos_from(data)
        reports = _store_photos(existing['id'], photos) if photos else []
        if photos and not existing.get('photo_b64'):
            database.set_primary_photo(existing['id'], photos[0])
        return jsonify({
            'success': True,
            'message': f"Updated person #{person_id}",
            'person': database.get_person_by_id(person_id) or updated_person,
            'photo_reports': reports,
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/peoples/<person_id>', methods=['DELETE'])
def delete_person_record(person_id):
    """Deletes a person record from SQLite DB."""
    try:
        database.delete_person(person_id)
        detector.load_db_peoples()
        return jsonify({
            'success': True,
            'message': f"Deleted person #{person_id}"
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/upload', methods=['POST'])
def upload_file():
    """Uploads video or image file and extracts reference first frame."""
    if 'file' not in request.files:
        return jsonify({'error': 'No file uploaded'}), 400
        
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'Empty filename'}), 400
        
    filename = f"upload_{int(time.time())}_{file.filename}"
    filepath = os.path.join(UPLOAD_FOLDER, filename)
    file.save(filepath)
    
    file_type = 'image' if file.content_type.startswith('image') else 'video'
    
    if file_type == 'image':
        frame = cv2.imread(filepath)
        if frame is None:
            return jsonify({'error': 'Could not decode image'}), 400
        h, w, _ = frame.shape
        first_frame_b64 = bgr_to_base64(frame)
        total_frames = 1
        fps = 0
    else:
        cap = cv2.VideoCapture(filepath)
        ret, frame = cap.read()
        if not ret:
            cap.release()
            return jsonify({'error': 'Could not read video frame'}), 400
        h, w, _ = frame.shape
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        fps = float(cap.get(cv2.CAP_PROP_FPS)) or 25.0
        cap.release()
        first_frame_b64 = bgr_to_base64(frame)
        
    return jsonify({
        'success': True,
        'filename': filename,
        'filepath': filepath,
        'file_type': file_type,
        'width': w,
        'height': h,
        'total_frames': total_frames,
        'fps': round(fps, 1),
        'first_frame': first_frame_b64
    })


# Global dictionaries for video processing and live streaming
processing_jobs = {}
live_stream_stats = {}
active_stream_configs = {}


@app.route('/api/init_stream', methods=['POST'])
def init_stream():
    """Initializes a live stream configuration for a video filename."""
    data = request.json or {}
    filename = data.get('filename')
    if not filename:
        return jsonify({'error': 'Filename missing'}), 400
        
    filepath = os.path.join(UPLOAD_FOLDER, filename)
    if not os.path.exists(filepath):
        return jsonify({'error': f'Video file {filename} not found on server'}), 404
        
    zones = data.get('zones', [])
    active_stream_configs[filename] = {
        'zones': zones,
        'yolo_conf': float(data.get('yolo_conf', 0.35)),
        'gender_conf': float(data.get('gender_conf', 0.40)),
        'draw_heads': bool(data.get('draw_heads', True)),
        'draw_objects': bool(data.get('draw_objects', True)),
        'target_person_id': data.get('target_person_id'),
        'draw_trails': bool(data.get('draw_trails', False)),
        'draw_zones': bool(data.get('draw_zones', False))
    }
    
    detector.reset_tracks(clear_gallery=not stream_manager.all_active())
    
    print(f"\n[Stream] Init stream received for {filename}: {len(zones)} project shapes, Target Lock ID: {data.get('target_person_id')}", flush=True)
    
    stream_url = f"/api/video_feed/{filename}"
    return jsonify({
        'success': True,
        'stream_url': stream_url,
        'filename': filename
    })


import socket

def check_rtsp_reachable(rtsp_url, timeout_sec=1.0):
    """
    Performs a fast socket probe to check if the RTSP camera host and port (e.g. 192.168.1.2:554) are online.
    Returns (is_reachable, host, port).
    """
    try:
        clean_url = rtsp_url.replace("rtsp://", "")
        if "@" in clean_url:
            clean_url = clean_url.split("@")[1]
        host_port = clean_url.split("/")[0]
        if ":" in host_port:
            host, port_str = host_port.split(":")
            port = int(port_str)
        else:
            host = host_port
            port = 554
            
        with socket.create_connection((host, port), timeout=timeout_sec):
            return True, host, port
    except Exception:
        return False, None, None


# -------------------------------------------------------------------
# RTSP LIVE NETWORK STREAM API ENDPOINTS (multi-camera)
# -------------------------------------------------------------------

stream_manager = StreamManager(detector, live_stream_stats,
                               lambda url: check_rtsp_reachable(url, timeout_sec=1.5)[0])

RTSP_STATE_KEY = 'rtsp_sessions'            # {stream_id: config} for every connected camera
RTSP_PERSISTED_FIELDS = ('rtsp_url', 'username', 'password', 'zones', 'yolo_conf',
                         'gender_conf', 'obj_conf', 'draw_heads', 'draw_objects', 'target_person_id',
                         'draw_trails', 'draw_zones', 'is_rtsp', 'width', 'height', 'first_frame')


def _mask_url(url):
    """Hides credentials embedded in an RTSP URL for log output."""
    if url and '@' in url:
        scheme, _, rest = url.partition('://')
        return f"{scheme}://***@{rest.split('@', 1)[1]}"
    return url


def persist_rtsp_sessions():
    """Saves every connected camera's config so live sessions survive page changes and server restarts."""
    saved = {}
    for sid, cfg in active_stream_configs.items():
        if not cfg.get('is_rtsp'):
            continue
        entry = {k: cfg.get(k) for k in RTSP_PERSISTED_FIELDS}
        entry['password'] = secrets_store.encrypt(entry.get('password') or '')      # never stored in plain text
        saved[sid] = entry
    try:
        database.set_state(RTSP_STATE_KEY, saved)
    except Exception as e:
        print(f"Could not persist RTSP sessions: {e}", flush=True)


def persist_rtsp_session(stream_id=None):
    persist_rtsp_sessions()


def resume_saved_rtsp_sessions():
    """On server start, reconnects every camera that was connected before shutdown."""
    saved = database.get_state(RTSP_STATE_KEY) or {}
    if not saved:                                         # migrate the single-camera format used earlier
        old = database.get_state('rtsp_session')
        if old and old.get('stream_id') and old.get('config'):
            saved = {old['stream_id']: old['config']}
            database.delete_state('rtsp_session')
    for stream_id, cfg in saved.items():
        cfg['password'] = secrets_store.decrypt(cfg.get('password') or '')
        cfg['formatted_url'] = format_rtsp_url(cfg.get('rtsp_url'), cfg.get('username'), cfg['password'])
        active_stream_configs[stream_id] = cfg
        try:
            stream_manager.ensure(stream_id, cfg)
            print(f"Resumed camera {stream_id} ({_mask_url(cfg.get('rtsp_url', ''))})", flush=True)
        except RuntimeError as e:
            print(f"Not resuming {stream_id}: {e}", flush=True)
    persist_rtsp_sessions()     # re-save so a legacy plain-text password is encrypted right away


def _camera_summary(stream_id):
    cfg = active_stream_configs.get(stream_id, {})
    worker = stream_manager.get(stream_id)
    return {
        'stream_id': stream_id,
        'rtsp_url': cfg.get('rtsp_url'),
        'label': worker.label if worker else _mask_url(cfg.get('rtsp_url', '')),
        'camera_status': worker.status if worker else 'stopped',
    }


@app.route('/api/connect_rtsp', methods=['POST'])
def connect_rtsp():
    """Adds a network camera and captures a first reference frame for boundary mapping."""
    data = request.json or {}
    rtsp_url = (data.get('rtsp_url') or '').strip()
    if not rtsp_url.lower().startswith('rtsp://'):
        return jsonify({'error': 'A valid rtsp:// URL is required'}), 400
    username = data.get('username', '')
    password = data.get('password', '')

    # Connecting the same camera again reuses its session instead of starting a duplicate
    for sid, cfg in active_stream_configs.items():
        if cfg.get('is_rtsp') and cfg.get('rtsp_url') == rtsp_url:
            return jsonify({
                'success': True, 'stream_id': sid, 'stream_url': f"/api/rtsp_feed/{sid}", 'rtsp_url': rtsp_url,
                'camera_online': True, 'width': cfg.get('width', 960), 'height': cfg.get('height', 540),
                'first_frame': cfg.get('first_frame'), 'already_connected': True})

    if len(stream_manager.all_active()) >= MAX_CAMERAS:
        return jsonify({'error': f'Camera limit reached ({MAX_CAMERAS}). Disconnect a camera first.'}), 409

    formatted_url = format_rtsp_url(rtsp_url, username, password)
    stream_id = f"rtsp_{int(time.time() * 1000)}"

    zones = data.get('zones', [])
    active_stream_configs[stream_id] = {
        'rtsp_url': rtsp_url,
        'formatted_url': formatted_url,
        'username': username,
        'password': password,
        'zones': zones,
        'yolo_conf': float(data.get('yolo_conf', 0.35)),
        'gender_conf': float(data.get('gender_conf', 0.40)),
        'obj_conf': float(data.get('obj_conf', 0.10)),
        'draw_heads': bool(data.get('draw_heads', True)),
        'draw_objects': bool(data.get('draw_objects', True)),
        'target_person_id': data.get('target_person_id'),
        'draw_trails': bool(data.get('draw_trails', False)),
        'draw_zones': bool(data.get('draw_zones', False)),
        'is_rtsp': True
    }

    # A fresh identity gallery per monitoring session, but never wipe identities another live camera is using
    if not stream_manager.all_active():
        detector.reset_tracks()

    # Check if RTSP camera host is online and grab first frame snapshot
    is_online, _, _ = check_rtsp_reachable(rtsp_url, timeout_sec=1.5)
    first_frame_b64 = None
    w, h = 960, 540

    if is_online:
        try:
            cap = cv2.VideoCapture(formatted_url, cv2.CAP_FFMPEG)
            if not cap.isOpened():
                cap = cv2.VideoCapture(formatted_url)
            if cap.isOpened():
                ret, frame = cap.read()
                if ret and frame is not None:
                    h, w, _ = frame.shape
                    first_frame_b64 = bgr_to_base64(frame)
                cap.release()
        except Exception as e:
            print(f"RTSP first frame grab exception: {e}")

    if not first_frame_b64:
        # Reference frame for polygon mapping when the camera cannot be reached yet
        frame = np.zeros((h, w, 3), dtype=np.uint8)
        for y in range(0, h, 40):
            cv2.line(frame, (0, y), (w, y), (15, 25, 45), 1)
        for x in range(0, w, 40):
            cv2.line(frame, (x, 0), (x, h), (15, 25, 45), 1)
        cv2.putText(frame, "CAMERA NOT REACHABLE YET - REFERENCE FRAME", (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 255, 255), 2)
        cv2.putText(frame, f"STREAM: {_mask_url(rtsp_url)}", (20, 75), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 1)
        first_frame_b64 = bgr_to_base64(frame)

    active_stream_configs[stream_id].update({'width': w, 'height': h, 'first_frame': first_frame_b64})
    persist_rtsp_sessions()

    print(f"\nRTSP camera added: {_mask_url(rtsp_url)} (online: {is_online})", flush=True)

    return jsonify({
        'success': True,
        'stream_id': stream_id,
        'stream_url': f"/api/rtsp_feed/{stream_id}",
        'rtsp_url': rtsp_url,
        'camera_online': is_online,
        'width': w,
        'height': h,
        'first_frame': first_frame_b64
    })


@app.route('/api/update_rtsp_zones/<stream_id>', methods=['POST'])
def update_rtsp_zones(stream_id):
    """Applies zones and settings to a camera and starts its background detection worker."""
    data = request.json or {}
    cfg = active_stream_configs.get(stream_id)
    if cfg is None:
        return jsonify({'error': 'RTSP stream config not found'}), 404

    zones = data.get('zones', [])
    cfg['zones'] = zones
    cfg['yolo_conf'] = float(data.get('yolo_conf', 0.35))
    cfg['gender_conf'] = float(data.get('gender_conf', 0.40))
    cfg['obj_conf'] = float(data.get('obj_conf', cfg.get('obj_conf', 0.10)))
    cfg['draw_heads'] = bool(data.get('draw_heads', True))
    cfg['draw_objects'] = bool(data.get('draw_objects', True))
    cfg['draw_trails'] = bool(data.get('draw_trails', False))
    cfg['draw_zones'] = bool(data.get('draw_zones', False))
    cfg['target_person_id'] = data.get('target_person_id')
    persist_rtsp_sessions()
    try:
        stream_manager.ensure(stream_id, cfg)
    except RuntimeError as e:
        return jsonify({'error': str(e)}), 409

    print(f"{len(zones)} boundary zones applied to {stream_id}; detection worker running", flush=True)
    return jsonify({'success': True, 'zones_count': len(zones)})


@app.route('/api/rtsp_feed/<stream_id>')
def rtsp_feed(stream_id):
    """MJPEG viewer for a camera. Only serves frames from the background worker; closing the page never stops detection."""
    cfg = active_stream_configs.get(stream_id)
    if cfg is None:
        return jsonify({'error': 'Unknown or disconnected stream'}), 404
    try:
        worker = stream_manager.ensure(stream_id, cfg)
    except RuntimeError as e:
        return jsonify({'error': str(e)}), 409

    def generate():
        last_id = -1
        while not worker.stopped:
            frame_id, jpeg = worker.wait_frame(last_id, timeout=5.0)
            if jpeg is None or frame_id == last_id:
                continue
            last_id = frame_id
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + jpeg + b'\r\n')

    resp = Response(generate(), mimetype='multipart/x-mixed-replace; boundary=frame')
    resp.headers['Cache-Control'] = 'no-store'
    return resp


@app.route('/api/disconnect_rtsp/<stream_id>', methods=['POST'])
def disconnect_rtsp(stream_id):
    """Explicitly stops one camera. Occupant logs recorded so far stay saved."""
    stream_manager.stop(stream_id)
    active_stream_configs.pop(stream_id, None)
    live_stream_stats.pop(stream_id, None)
    persist_rtsp_sessions()
    return jsonify({'success': True})


@app.route('/api/update_target/<filename>', methods=['POST'])
def update_target(filename):
    """Updates target_person_id, draw_trails, draw_zones, draw_objects, draw_heads, obj_conf for active video stream dynamically."""
    data = request.json or {}
    target_person_id = data.get('target_person_id')
    draw_trails = bool(data.get('draw_trails', False))
    
    if filename in active_stream_configs:
        active_stream_configs[filename]['target_person_id'] = target_person_id
        active_stream_configs[filename]['draw_trails'] = draw_trails
        if 'draw_zones' in data:
            active_stream_configs[filename]['draw_zones'] = bool(data['draw_zones'])
        if 'draw_objects' in data:
            active_stream_configs[filename]['draw_objects'] = bool(data['draw_objects'])
        if 'draw_heads' in data:
            active_stream_configs[filename]['draw_heads'] = bool(data['draw_heads'])
        if 'obj_conf' in data:
            active_stream_configs[filename]['obj_conf'] = float(data['obj_conf'])
        if 'yolo_conf' in data:
            active_stream_configs[filename]['yolo_conf'] = float(data['yolo_conf'])
        if active_stream_configs[filename].get('is_rtsp'):
            persist_rtsp_session(filename)
        print(f"[Stream] Controls updated dynamically for {filename}: objects={active_stream_configs[filename].get('draw_objects')}, obj_conf={active_stream_configs[filename].get('obj_conf')}", flush=True)
        return jsonify({'success': True, 'target_person_id': target_person_id})
    return jsonify({'error': 'Stream config not found'}), 404


@app.route('/api/video_feed/<filename>')
def video_feed(filename):
    """Live MJPEG Video Stream endpoint - streams annotated video frames directly to browser in real time."""
    config = active_stream_configs.get(filename, {})
    filepath = os.path.join(UPLOAD_FOLDER, filename)
    if not os.path.exists(filepath):
        print(f"[Error] video_feed: File {filename} not found at {filepath}", flush=True)
        return "Video file not found", 404

    def generate_mjpeg():
        cap = cv2.VideoCapture(filepath)
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        
        # Check if resuming from previously saved position
        latest_cfg = active_stream_configs.setdefault(filename, config)
        start_frame = latest_cfg.get('last_frame', 0)
        if 0 < start_frame < total_frames - 2:
            cap.set(cv2.CAP_PROP_POS_FRAMES, start_frame)
            frame_cnt = start_frame
            print(f"\n[Video Feed] Resuming Live MJPEG Video Feed: {filename} from Frame {start_frame}/{total_frames}", flush=True)
        else:
            frame_cnt = 0
            print(f"\n[Video Feed] Live MJPEG Video Feed Running: {filename} ({total_frames} frames)", flush=True)

        last_annotated_frame = None
        last_flush = time.time()
        database.start_session(filename, source='video file')

        while cap.isOpened():
            latest_cfg = active_stream_configs.get(filename, config)

            # Handle Seek request from UI scrubber
            if 'seek_frame' in latest_cfg and latest_cfg['seek_frame'] is not None:
                target_frame = max(0, min(total_frames - 1, int(latest_cfg.pop('seek_frame'))))
                cap.set(cv2.CAP_PROP_POS_FRAMES, target_frame)
                frame_cnt = target_frame
                last_annotated_frame = None

            # Handle Paused state: hold current frame and sleep briefly to save CPU/GPU
            if latest_cfg.get('is_paused', False):
                if last_annotated_frame is not None:
                    _, jpeg_buf = cv2.imencode('.jpg', last_annotated_frame)
                    frame_bytes = jpeg_buf.tobytes()
                    yield (b'--frame\r\n'
                           b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
                time.sleep(0.12)
                continue

            # Handle Fast-Forward Speed (e.g. 2x, 4x)
            speed = latest_cfg.get('speed', 1)
            if speed > 1:
                for _ in range(speed - 1):
                    cap.grab()
                    frame_cnt += 1

            ret, frame = cap.read()
            if not ret:
                break
            frame_cnt += 1
            latest_cfg['last_frame'] = frame_cnt

            detector.yolo_conf = latest_cfg.get('yolo_conf', 0.35)
            detector.gender_conf = latest_cfg.get('gender_conf', 0.40)
            detector.obj_conf = latest_cfg.get('obj_conf', 0.10)

            # Persist the occupant log periodically so it survives page changes and restarts
            if time.time() - last_flush >= 10:
                last_flush = time.time()
                try:
                    database.save_occupants(filename, detector.get_occupant_roster(), store_faces=app_settings.get('privacy')['store_faces'])
                except Exception as e:
                    print(f"[Warning] Occupant log flush failed for {filename}: {e}", flush=True)

            # Run full AI detection every 2 frames for 2x faster live streaming
            if frame_cnt == 1 or frame_cnt % 2 == 0 or frame_cnt == total_frames or last_annotated_frame is None:
                annotated_frame, stats = detector.process_frame(
                    frame,
                    draw_yolo_objects=latest_cfg.get('draw_objects', True),
                    draw_heads=latest_cfg.get('draw_heads', True),
                    zones=latest_cfg.get('zones', []),
                    target_person_id=latest_cfg.get('target_person_id'),
                    draw_trails=latest_cfg.get('draw_trails', False),
                    draw_zones=latest_cfg.get('draw_zones', False)
                )
                last_annotated_frame = annotated_frame
                pct = (frame_cnt / max(total_frames, 1)) * 100
                stats['pct'] = round(pct, 1)
                stats['current_frame'] = frame_cnt
                stats['total_frames'] = total_frames
                stats['is_paused'] = latest_cfg.get('is_paused', False)
                stats['speed'] = latest_cfg.get('speed', 1)
                live_stream_stats[filename] = stats
            else:
                annotated_frame = last_annotated_frame if last_annotated_frame is not None else frame

            # Console log output every 10 frames
            if frame_cnt % 10 == 0 or frame_cnt == 1 or frame_cnt == total_frames:
                st = live_stream_stats.get(filename, {})
                target_str = latest_cfg.get('target_person_id') or 'All'
                speed_str = f"{speed}x" if speed > 1 else "1x"
                print(f"  [Live Feed] Frame {frame_cnt}/{total_frames} ({((frame_cnt/max(total_frames,1))*100):.1f}%) | "
                      f"Speed: {speed_str} | Male: {st.get('male_count', 0)} | Female: {st.get('female_count', 0)} | "
                      f"Target Lock: {target_str}", flush=True)

            _, jpeg_buf = cv2.imencode('.jpg', annotated_frame)
            frame_bytes = jpeg_buf.tobytes()

            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')

        cap.release()
        latest_cfg['last_frame'] = frame_cnt
        try:
            database.save_occupants(filename, detector.get_occupant_roster(), store_faces=app_settings.get('privacy')['store_faces'])
        except Exception:
            pass
        print(f"[Video Feed] Live Video Feed Stream Completed for {filename}\n", flush=True)

    return Response(generate_mjpeg(), mimetype='multipart/x-mixed-replace; boundary=frame')


@app.route('/api/stream_control/<filename>', methods=['POST'])
def stream_control(filename):
    """Controls live video playback: play, pause, toggle, speed, seek, and restart."""
    data = request.json or {}
    action = data.get('action')
    cfg = active_stream_configs.setdefault(filename, {})
    
    if action == 'pause':
        cfg['is_paused'] = True
    elif action in ['play', 'resume']:
        cfg['is_paused'] = False
    elif action == 'toggle':
        cfg['is_paused'] = not cfg.get('is_paused', False)
    elif action == 'speed':
        cfg['speed'] = max(1, min(8, int(data.get('speed', 1))))
    elif action == 'seek':
        target_f = data.get('frame')
        if target_f is not None:
            cfg['seek_frame'] = int(target_f)
            cfg['last_frame'] = int(target_f)
    elif action == 'skip':
        offset_sec = float(data.get('seconds', 5))
        offset_frames = int(offset_sec * 25)
        curr = cfg.get('last_frame', 0)
        cfg['seek_frame'] = max(0, curr + offset_frames)
        cfg['last_frame'] = cfg['seek_frame']
    elif action == 'restart':
        cfg['seek_frame'] = 0
        cfg['last_frame'] = 0
        cfg['is_paused'] = False

    if filename in live_stream_stats:
        live_stream_stats[filename]['is_paused'] = cfg.get('is_paused', False)
        live_stream_stats[filename]['speed'] = cfg.get('speed', 1)
        if 'last_frame' in cfg:
            live_stream_stats[filename]['current_frame'] = cfg['last_frame']

    return jsonify({
        'success': True,
        'action': action,
        'is_paused': cfg.get('is_paused', False),
        'speed': cfg.get('speed', 1),
        'current_frame': cfg.get('last_frame', 0)
    })


@app.route('/api/active_session', methods=['GET'])
def get_active_session():
    """Returns the running live session (a camera, else the last video) plus the list of connected cameras,
    so any page change or reload re-attaches to what is already running."""
    running = stream_manager.all_active()
    cameras = [_camera_summary(sid) for sid, _ in running]
    wanted = request.args.get('stream_id')
    chosen = next(((sid, w) for sid, w in running if sid == wanted), None) or (running[-1] if running else None)
    if chosen:
        sid, worker = chosen
        cfg = active_stream_configs.get(sid, {})
        return jsonify({
            'success': True,
            'has_active': True,
            'type': 'rtsp',
            'cameras': cameras,
            'stream_id': sid,
            'rtsp_url': cfg.get('rtsp_url'),
            'username': cfg.get('username', ''),
            'camera_status': worker.status,
            'width': cfg.get('width', 960),
            'height': cfg.get('height', 540),
            'first_frame': cfg.get('first_frame'),
            'zones': cfg.get('zones', []),
            'yolo_conf': cfg.get('yolo_conf', 0.35),
            'gender_conf': cfg.get('gender_conf', 0.40),
            'obj_conf': cfg.get('obj_conf', 0.10),
            'draw_heads': cfg.get('draw_heads', True),
            'draw_objects': cfg.get('draw_objects', True),
            'draw_trails': cfg.get('draw_trails', False),
            'draw_zones': cfg.get('draw_zones', False),
            'target_person_id': cfg.get('target_person_id') or 'All',
        })
    for fn, cfg in reversed(list(active_stream_configs.items())):
        if cfg.get('is_rtsp'):
            continue
        filepath = os.path.join(UPLOAD_FOLDER, fn)
        if os.path.exists(filepath):
            st = live_stream_stats.get(fn, {})
            return jsonify({
                'success': True,
                'has_active': True,
                'type': 'video',
                'cameras': [],
                'filename': fn,
                'last_frame': cfg.get('last_frame', 0),
                'total_frames': st.get('total_frames', 0),
                'is_paused': cfg.get('is_paused', False),
                'speed': cfg.get('speed', 1),
                'target_person_id': cfg.get('target_person_id', 'All'),
                'zones': cfg.get('zones', [])
            })
    return jsonify({'success': True, 'has_active': False, 'cameras': []})


@app.route('/api/live_stats/<filename>')
def get_live_stats(filename):
    """Returns the latest frame stats JSON while live video streaming."""
    stats = live_stream_stats.get(filename, {})
    return jsonify({'success': True, 'stats': stats})


@app.route('/api/progress/<filename>', methods=['GET'])
def get_progress(filename):
    """Returns real-time video processing frame count, percentage, and live stats."""
    progress = processing_jobs.get(filename, {
        'current': 0,
        'total': 0,
        'pct': 0.0,
        'status': 'idle',
        'stats': {}
    })
    return jsonify({'success': True, 'progress': progress})


@app.route('/api/process', methods=['POST'])
def process_media():
    """Processes uploaded video or image using YOLO and 4-point custom project boundaries."""
    try:
        data = request.json or {}
        filename = data.get('filename')
        zones = data.get('zones', [])
        yolo_conf = float(data.get('yolo_conf', 0.35))
        gender_conf = float(data.get('gender_conf', 0.40))
        draw_heads = bool(data.get('draw_heads', True))
        draw_objects = bool(data.get('draw_objects', True))
        frame_stride = int(data.get('frame_stride', 2))
        
        if not filename:
            return jsonify({'error': 'Filename missing'}), 400
            
        filepath = os.path.join(UPLOAD_FOLDER, filename)
        if not os.path.exists(filepath):
            return jsonify({'error': 'File not found on server'}), 404
            
        detector.yolo_conf = yolo_conf
        detector.gender_conf = gender_conf
        
        file_ext = os.path.splitext(filename)[1].lower()
        is_image = file_ext in ['.jpg', '.jpeg', '.png', '.bmp', '.webp']
        
        if is_image:
            print(f"[Image] Processing single image: {filename}...", flush=True)
            frame = cv2.imread(filepath)
            annotated_frame, stats = detector.process_frame(
                frame,
                draw_yolo_objects=draw_objects,
                draw_heads=draw_heads,
                zones=zones
            )
            out_b64 = bgr_to_base64(annotated_frame)
            print(f"[Image] Finished image processing: {filename}", flush=True)
            return jsonify({
                'success': True,
                'file_type': 'image',
                'output_image': out_b64,
                'stats': stats
            })
        else:
            cap = cv2.VideoCapture(filepath)
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            fps_v = cap.get(cv2.CAP_PROP_FPS) or 25
            w_v = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            h_v = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            
            print(f"\n[Video Processing] Starting Video Processing: {filename} ({w_v}x{h_v} @ {fps_v:.1f} FPS, Total Frames: {total_frames})", flush=True)
            print(f"[Video Processing] Active Project Boundaries: {len(zones)} shapes defined", flush=True)
            
            out_filename = f"classified_{int(time.time())}.mp4"
            out_filepath = os.path.join(OUTPUT_FOLDER, out_filename)
            
            fourcc = cv2.VideoWriter_fourcc(*'mp4v')
            out_writer = cv2.VideoWriter(out_filepath, fourcc, fps_v, (w_v, h_v))
            
            latest_stats = {}
            frame_cnt = 0
            last_annotated_frame = None
            
            processing_jobs[filename] = {
                'current': 0,
                'total': total_frames,
                'pct': 0.0,
                'status': 'processing',
                'stats': {}
            }
            
            while cap.isOpened():
                ret, frame = cap.read()
                if not ret:
                    break
                frame_cnt += 1
                
                if frame_cnt == 1 or frame_cnt % frame_stride == 0 or frame_cnt == total_frames:
                    annotated_frame, stats = detector.process_frame(
                        frame,
                        draw_yolo_objects=draw_objects,
                        draw_heads=draw_heads,
                        zones=zones
                    )
                    last_annotated_frame = annotated_frame
                    latest_stats = stats
                else:
                    annotated_frame = last_annotated_frame if last_annotated_frame is not None else frame
                    
                out_writer.write(annotated_frame)
                
                pct = (frame_cnt / max(total_frames, 1)) * 100
                processing_jobs[filename] = {
                    'current': frame_cnt,
                    'total': total_frames,
                    'pct': round(pct, 1),
                    'status': 'processing',
                    'stats': latest_stats
                }
                
                if frame_cnt % 5 == 0 or frame_cnt == 1 or frame_cnt == total_frames:
                    print(f"  ▶️ [{filename}] Frame {frame_cnt}/{total_frames} ({pct:.1f}%) | "
                          f"Male: {latest_stats.get('male_count', 0)} | Female: {latest_stats.get('female_count', 0)} | "
                          f"Sitting: {latest_stats.get('sitting_count', 0)} | Standing: {latest_stats.get('standing_count', 0)}", flush=True)
                
            cap.release()
            out_writer.release()
            
            processing_jobs[filename]['status'] = 'completed'
            print(f"[Video Processing] Completed Video Processing: {filename} -> Output: {out_filename}\n", flush=True)
            
            output_video_url = f"/static/outputs/{out_filename}"
            
            return jsonify({
                'success': True,
                'file_type': 'video',
                'output_video_url': output_video_url,
                'download_filename': out_filename,
                'total_frames_processed': frame_cnt,
                'stats': latest_stats
            })
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/static/outputs/<filename>')
def serve_output(filename):
    """Serves processed output video files."""
    return send_from_directory(OUTPUT_FOLDER, filename)


routes_extra.register(app, detector, stream_manager, active_stream_configs, live_stream_stats)


def run_maintenance():
    """Startup housekeeping: apply privacy settings and delete data past its retention period."""
    detector.blur_faces = bool(app_settings.get('privacy')['blur_faces'])
    routes_extra.apply_recognition_settings(detector, app_settings.get('recognition', use_cache=False))
    privacy = app_settings.get('privacy', use_cache=False)
    removed = database.purge_old_sessions(int(os.environ.get('AEGIS_RETENTION_DAYS', 30)))
    faces = database.purge_face_crops(privacy['face_retention_days'])
    database.purge_old_presence(privacy['presence_retention_days'])
    if removed or faces:
        print(f"Retention: removed {removed} old sessions, cleared {faces} stored face crops", flush=True)


if __name__ == '__main__':
    database.init_db()
    run_maintenance()
    resume_saved_rtsp_sessions()
    host = os.environ.get('HOST', '0.0.0.0')
    port = int(os.environ.get('PORT', 5050))
    print(f"\n[Aegis-OS] Running on http://{host}:{port} | accounts: {'ON' if auth.auth_enabled() else 'OFF (open /setup to create the first administrator)'}\n", flush=True)
    try:
        from waitress import serve
        # Each open MJPEG viewer holds one thread, so keep headroom
        serve(app, host=host, port=port, threads=24, channel_timeout=120)
    except ImportError:
        app.run(host=host, port=port, debug=False, threaded=True)
