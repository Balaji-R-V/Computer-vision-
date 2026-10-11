import sqlite3
import os
import json
import time
from datetime import datetime

DB_PATH = os.environ.get('AEGIS_DB_PATH') or os.path.join(os.path.dirname(__file__), 'peoples.db')

TRANSIENT_ERRORS = ('disk i/o error', 'database is locked', 'database table is locked', 'unable to open database file')


class _RetryConnection(sqlite3.Connection):
    """Retries statements that hit a transient error. This project often lives in a cloud-synced folder
    (e.g. Google Drive), where the sync client can lock the database file for a moment."""

    def _retry(self, fn, *args, **kwargs):
        for attempt in range(8):
            try:
                return fn(*args, **kwargs)
            except sqlite3.OperationalError as e:
                if attempt == 7 or not any(t in str(e).lower() for t in TRANSIENT_ERRORS):
                    raise
                time.sleep(0.25 * (attempt + 1))

    def execute(self, *args, **kwargs):
        return self._retry(super().execute, *args, **kwargs)

    def executemany(self, *args, **kwargs):
        return self._retry(super().executemany, *args, **kwargs)

    def commit(self):
        return self._retry(super().commit)


def get_db_connection():
    """SQLite connection with row factory, a generous busy timeout and automatic retry of transient errors.

    Journal mode defaults to DELETE because WAL is not reliable on network/cloud-synced drives; set
    AEGIS_SQLITE_JOURNAL=WAL if the database is on a local disk and you want maximum concurrency."""
    conn = sqlite3.connect(DB_PATH, timeout=30.0, factory=_RetryConnection)
    try:
        conn.execute(f"PRAGMA journal_mode={os.environ.get('AEGIS_SQLITE_JOURNAL', 'DELETE')};")
    except Exception:
        pass
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Initializes the SQLite database table for registered people and populates initial sample entries if empty."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS peoples (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            person_code TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL,
            gender TEXT DEFAULT 'Unspecified',
            department TEXT DEFAULT 'Engineering',
            role TEXT DEFAULT 'Staff Occupant',
            photo_b64 TEXT DEFAULT '',
            embedding_json TEXT DEFAULT '[]',
            notes TEXT DEFAULT '',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            last_seen TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()

    # Seed sample database entries if table is empty
    cursor.execute('SELECT COUNT(*) as count FROM peoples')
    count = cursor.fetchone()['count']
    if count == 0:
        sample_peoples = [
            {
                'person_code': 'PER-001',
                'name': 'Alex Mercer',
                'gender': 'Male',
                'department': 'R&D Labs',
                'role': 'Senior AI Systems Lead',
                'notes': 'Authorized for Level 4 AI Control Room Access.',
                'photo_b64': '',
                'embedding_json': '[]'
            },
            {
                'person_code': 'PER-002',
                'name': 'Elena Rostova',
                'gender': 'Female',
                'department': 'Operations',
                'role': 'Perimeter Security Officer',
                'notes': 'Monitors live RTSP stream feeds & boundary compliance.',
                'photo_b64': '',
                'embedding_json': '[]'
            },
            {
                'person_code': 'PER-003',
                'name': 'Marcus Vance',
                'gender': 'Male',
                'department': 'Engineering',
                'role': 'Hardware Infra Specialist',
                'notes': 'RTSP Network & Camera Maintenance Team.',
                'photo_b64': '',
                'embedding_json': '[]'
            }
        ]
        for p in sample_peoples:
            cursor.execute('''
                INSERT INTO peoples (person_code, name, gender, department, role, photo_b64, embedding_json, notes, created_at, last_seen)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, datetime('now'), datetime('now'))
            ''', (p['person_code'], p['name'], p['gender'], p['department'], p['role'], p['photo_b64'], p['embedding_json'], p['notes']))
        conn.commit()
        print("✅ People Database Initialized with sample registered entries.")
    
    conn.close()

def get_all_peoples():
    """Retrieves all registered people from the database."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM peoples ORDER BY id ASC')
    rows = cursor.fetchall()
    conn.close()
    
    peoples = []
    for r in rows:
        peoples.append({
            'id': r['id'],
            'person_code': r['person_code'],
            'name': r['name'],
            'gender': r['gender'],
            'department': r['department'],
            'role': r['role'],
            'photo_b64': r['photo_b64'],
            'embedding_json': r['embedding_json'],
            'face_embedding_json': r['face_embedding_json'] if 'face_embedding_json' in r.keys() else '',
            'notes': r['notes'],
            'created_at': r['created_at'],
            'last_seen': r['last_seen']
        })
    return peoples

def get_person_by_id(person_id):
    """Retrieves a single person record by numeric ID or person_code string."""
    conn = get_db_connection()
    cursor = conn.cursor()
    if isinstance(person_id, int) or (isinstance(person_id, str) and person_id.isdigit()):
        cursor.execute('SELECT * FROM peoples WHERE id = ?', (int(person_id),))
    else:
        cursor.execute('SELECT * FROM peoples WHERE person_code = ?', (str(person_id),))
    row = cursor.fetchone()
    conn.close()
    
    if row:
        return {
            'id': row['id'],
            'person_code': row['person_code'],
            'name': row['name'],
            'gender': row['gender'],
            'department': row['department'],
            'role': row['role'],
            'photo_b64': row['photo_b64'],
            'embedding_json': row['embedding_json'],
            'notes': row['notes'],
            'created_at': row['created_at'],
            'last_seen': row['last_seen']
        }
    return None

def add_person(name, gender, department, role, photo_b64, embedding_json, notes):
    """Adds a new person record to the database."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Generate unique person_code PER-XXX
    cursor.execute('SELECT MAX(id) as max_id FROM peoples')
    max_id = cursor.fetchone()['max_id'] or 0
    next_num = max_id + 1
    person_code = f"PER-{next_num:03d}"
    
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    cursor.execute('''
        INSERT INTO peoples (person_code, name, gender, department, role, photo_b64, embedding_json, notes, created_at, last_seen)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (person_code, name, gender, department, role, photo_b64, embedding_json, notes, now_str, now_str))
    
    conn.commit()
    new_id = cursor.lastrowid
    conn.close()
    
    print(f"👤 Added Person to DB: {name} ({person_code})")
    return get_person_by_id(new_id)

def update_person(person_id, name, gender, department, role, notes, photo_b64=None, embedding_json=None):
    """Updates existing person record in the database."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    if photo_b64 and embedding_json and embedding_json != '[]':
        cursor.execute('''
            UPDATE peoples
            SET name = ?, gender = ?, department = ?, role = ?, notes = ?, photo_b64 = ?, embedding_json = ?,
                face_embedding_json = ''
            WHERE id = ? OR person_code = ?
        ''', (name, gender, department, role, notes, photo_b64, embedding_json, person_id, str(person_id)))
    else:
        cursor.execute('''
            UPDATE peoples
            SET name = ?, gender = ?, department = ?, role = ?, notes = ?
            WHERE id = ? OR person_code = ?
        ''', (name, gender, department, role, notes, person_id, str(person_id)))
        
    conn.commit()
    conn.close()
    return get_person_by_id(person_id)

def update_person_embedding(person_id, embedding_json):
    """Stores a rebuilt ReID embedding for a registered person."""
    conn = get_db_connection()
    conn.execute('UPDATE peoples SET embedding_json = ? WHERE id = ?', (embedding_json, person_id))
    conn.commit()
    conn.close()


def update_person_face_embedding(person_id, face_embedding_json):
    """Stores the face embedding computed from a registered person's photo ('[]' = photo has no usable face)."""
    conn = get_db_connection()
    conn.execute('UPDATE peoples SET face_embedding_json = ? WHERE id = ?', (face_embedding_json, person_id))
    conn.commit()
    conn.close()


def update_person_last_seen(person_id):
    """Updates last_seen timestamp for a person."""
    conn = get_db_connection()
    cursor = conn.cursor()
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute('''
        UPDATE peoples SET last_seen = ? WHERE id = ? OR person_code = ?
    ''', (now_str, person_id, str(person_id)))
    conn.commit()
    conn.close()

def delete_person(person_id):
    """Deletes a person record from database."""
    conn = get_db_connection()
    cursor = conn.cursor()
    row = cursor.execute('SELECT id FROM peoples WHERE id = ? OR person_code = ?', (person_id, str(person_id))).fetchone()
    if row:
        cursor.execute('DELETE FROM person_photos WHERE person_id = ?', (row['id'],))
    cursor.execute('DELETE FROM peoples WHERE id = ? OR person_code = ?', (person_id, str(person_id)))
    conn.commit()
    conn.close()
    print(f"🗑️ Deleted Person #{person_id} from database.")
    return True

# -------------------------------------------------------------------
# MONITORING SESSIONS, OCCUPANT LOGS & RUNTIME STATE
# -------------------------------------------------------------------

def init_runtime_tables():
    """Creates tables that make occupant logs and the live session survive page changes and restarts."""
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute('''
        CREATE TABLE IF NOT EXISTS monitoring_sessions (
            session_id TEXT PRIMARY KEY,
            source TEXT DEFAULT '',
            started_at TEXT,
            ended_at TEXT
        )
    ''')
    cur.execute('''
        CREATE TABLE IF NOT EXISTS occupant_logs (
            session_id TEXT NOT NULL,
            track_id INTEGER NOT NULL,
            gender TEXT DEFAULT 'Unknown',
            gender_conf REAL DEFAULT 0,
            posture TEXT DEFAULT '',
            total_seconds REAL DEFAULT 0,
            time_per_zone TEXT DEFAULT '{}',
            current_zone TEXT DEFAULT '',
            timeline TEXT DEFAULT '[]',
            face_b64 TEXT DEFAULT '',
            updated_at TEXT,
            PRIMARY KEY (session_id, track_id)
        )
    ''')
    cur.execute('''
        CREATE TABLE IF NOT EXISTS alerts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts TEXT NOT NULL,
            camera TEXT DEFAULT '',
            kind TEXT NOT NULL,
            severity TEXT DEFAULT 'warning',
            message TEXT NOT NULL,
            person TEXT DEFAULT '',
            zone TEXT DEFAULT '',
            snapshot TEXT DEFAULT '',
            clip TEXT DEFAULT '',
            acknowledged INTEGER DEFAULT 0,
            acknowledged_by TEXT DEFAULT ''
        )
    ''')
    cur.execute('''
        CREATE TABLE IF NOT EXISTS presence_samples (
            session_id TEXT NOT NULL,
            camera TEXT DEFAULT '',
            ts TEXT NOT NULL,
            zone TEXT NOT NULL,
            count INTEGER NOT NULL
        )
    ''')
    cur.execute('CREATE INDEX IF NOT EXISTS idx_presence_ts ON presence_samples (ts)')
    cur.execute('''
        CREATE TABLE IF NOT EXISTS heatmaps (
            session_id TEXT PRIMARY KEY,
            camera TEXT DEFAULT '',
            cols INTEGER, rows INTEGER,
            grid_json TEXT,
            ref_image TEXT DEFAULT '',
            updated_at TEXT
        )
    ''')
    cur.execute('''
        CREATE TABLE IF NOT EXISTS users (
            username TEXT PRIMARY KEY,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'viewer',
            disabled INTEGER DEFAULT 0,
            created_at TEXT,
            last_login TEXT
        )
    ''')
    cur.execute('''
        CREATE TABLE IF NOT EXISTS person_photos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            person_id INTEGER NOT NULL,
            kind TEXT DEFAULT 'upload',
            photo_b64 TEXT DEFAULT '',
            face_json TEXT DEFAULT '',
            bodies_json TEXT DEFAULT '[]',
            face_px INTEGER DEFAULT 0,
            note TEXT DEFAULT '',
            created_at TEXT
        )
    ''')
    cur.execute('CREATE INDEX IF NOT EXISTS idx_person_photos_person ON person_photos (person_id)')
    cols = [r['name'] for r in cur.execute('PRAGMA table_info(peoples)').fetchall()]
    if 'face_embedding_json' not in cols:
        cur.execute("ALTER TABLE peoples ADD COLUMN face_embedding_json TEXT DEFAULT ''")
    cols_users = [r['name'] for r in cur.execute('PRAGMA table_info(users)').fetchall()]
    if 'engine_mode' not in cols_users:
        cur.execute("ALTER TABLE users ADD COLUMN engine_mode TEXT DEFAULT 'gpu_local'")
    cur.execute('''
        CREATE TABLE IF NOT EXISTS app_state (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    ''')
    conn.commit()
    conn.close()


def _now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def start_session(session_id, source=''):
    conn = get_db_connection()
    conn.execute('INSERT OR IGNORE INTO monitoring_sessions (session_id, source, started_at) VALUES (?, ?, ?)',
                 (session_id, source, _now()))
    conn.commit()
    conn.close()


def end_session(session_id):
    conn = get_db_connection()
    conn.execute('UPDATE monitoring_sessions SET ended_at = ? WHERE session_id = ?', (_now(), session_id))
    conn.commit()
    conn.close()


def save_occupants(session_id, roster, store_faces=True):
    """Upserts the live occupant roster (list of dicts from detector.get_occupant_roster) for a session."""
    if not session_id or not roster:
        return
    now = _now()
    rows = [(
        session_id, o['track_id'], o.get('gender', 'Unknown'), float(o.get('gender_conf', 0) or 0),
        o.get('posture', ''), float(o.get('total_seconds', 0) or 0),
        json.dumps(o.get('time_per_zone', {})), o.get('current_zone') or '',
        json.dumps(o.get('timeline', [])), (o.get('face_b64', '') or '') if store_faces else '', now
    ) for o in roster]
    conn = get_db_connection()
    conn.executemany('''
        INSERT INTO occupant_logs (session_id, track_id, gender, gender_conf, posture, total_seconds,
                                   time_per_zone, current_zone, timeline, face_b64, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(session_id, track_id) DO UPDATE SET
            gender = excluded.gender, gender_conf = excluded.gender_conf, posture = excluded.posture,
            total_seconds = excluded.total_seconds, time_per_zone = excluded.time_per_zone,
            current_zone = excluded.current_zone, timeline = excluded.timeline,
            face_b64 = excluded.face_b64, updated_at = excluded.updated_at
    ''', rows)
    conn.commit()
    conn.close()


def get_occupants(session_id):
    """Loads a saved occupant roster in the same shape detector.get_occupant_roster() returns."""
    conn = get_db_connection()
    rows = conn.execute('SELECT * FROM occupant_logs WHERE session_id = ? ORDER BY track_id', (session_id,)).fetchall()
    conn.close()
    roster = []
    for r in rows:
        tpz = json.loads(r['time_per_zone'] or '{}')
        tot = max(r['total_seconds'], 0.1)
        roster.append({
            'track_id': r['track_id'],
            'face_b64': r['face_b64'],
            'gender': r['gender'],
            'gender_conf': r['gender_conf'],
            'posture': r['posture'],
            'total_seconds': round(r['total_seconds'], 1),
            'time_per_zone': tpz,
            'zone_percentages': {z: round(s / tot * 100, 1) for z, s in tpz.items()},
            'current_zone': r['current_zone'],
            'timeline': json.loads(r['timeline'] or '[]'),
        })
    return roster


def get_latest_session_id():
    """Most recent session that actually has occupant rows."""
    conn = get_db_connection()
    row = conn.execute('''
        SELECT s.session_id FROM monitoring_sessions s
        WHERE EXISTS (SELECT 1 FROM occupant_logs o WHERE o.session_id = s.session_id)
        ORDER BY s.started_at DESC, s.rowid DESC LIMIT 1
    ''').fetchone()
    conn.close()
    return row['session_id'] if row else None


def list_sessions(limit=30):
    conn = get_db_connection()
    rows = conn.execute('''
        SELECT s.session_id, s.source, s.started_at, s.ended_at,
               (SELECT COUNT(*) FROM occupant_logs o WHERE o.session_id = s.session_id) AS occupants
        FROM monitoring_sessions s ORDER BY s.started_at DESC, s.rowid DESC LIMIT ?
    ''', (limit,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# -------------------------------------------------------------------
# ALERTS
# -------------------------------------------------------------------

def add_alert(camera, kind, severity, message, person='', zone='', snapshot=''):
    conn = get_db_connection()
    cur = conn.execute('INSERT INTO alerts (ts, camera, kind, severity, message, person, zone, snapshot) VALUES (?,?,?,?,?,?,?,?)',
                       (_now(), camera, kind, severity, message, person, zone, snapshot))
    conn.commit()
    alert_id = cur.lastrowid
    conn.close()
    return alert_id


def set_alert_media(alert_id, snapshot=None, clip=None):
    conn = get_db_connection()
    if snapshot is not None:
        conn.execute('UPDATE alerts SET snapshot = ? WHERE id = ?', (snapshot, alert_id))
    if clip is not None:
        conn.execute('UPDATE alerts SET clip = ? WHERE id = ?', (clip, alert_id))
    conn.commit()
    conn.close()


def list_alerts(limit=100, only_open=False):
    conn = get_db_connection()
    rows = conn.execute('SELECT * FROM alerts ' + ('WHERE acknowledged = 0 ' if only_open else '') +
                        'ORDER BY id DESC LIMIT ?', (limit,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def count_open_alerts():
    conn = get_db_connection()
    n = conn.execute('SELECT COUNT(*) AS n FROM alerts WHERE acknowledged = 0').fetchone()['n']
    conn.close()
    return n


def acknowledge_alerts(ids, user):
    """ids: list of alert ids, or None to acknowledge everything open."""
    conn = get_db_connection()
    if ids is None:
        conn.execute("UPDATE alerts SET acknowledged = 1, acknowledged_by = ? WHERE acknowledged = 0", (user,))
    else:
        conn.executemany("UPDATE alerts SET acknowledged = 1, acknowledged_by = ? WHERE id = ?", [(user, i) for i in ids])
    conn.commit()
    conn.close()


# -------------------------------------------------------------------
# PRESENCE HISTORY & HEATMAPS (feed the reports page)
# -------------------------------------------------------------------

def add_presence_samples(session_id, camera, zone_counts):
    """zone_counts: {zone_name: people_in_zone}; the key '*' holds the total in frame."""
    if not zone_counts:
        return
    now = _now()
    conn = get_db_connection()
    conn.executemany('INSERT INTO presence_samples (session_id, camera, ts, zone, count) VALUES (?,?,?,?,?)',
                     [(session_id, camera, now, z, int(c)) for z, c in zone_counts.items()])
    conn.commit()
    conn.close()


def save_heatmap(session_id, camera, cols, rows, grid, ref_image=''):
    conn = get_db_connection()
    conn.execute('''INSERT INTO heatmaps (session_id, camera, cols, rows, grid_json, ref_image, updated_at)
                    VALUES (?,?,?,?,?,?,?)
                    ON CONFLICT(session_id) DO UPDATE SET grid_json = excluded.grid_json,
                        ref_image = CASE WHEN excluded.ref_image != '' THEN excluded.ref_image ELSE ref_image END,
                        updated_at = excluded.updated_at''',
                 (session_id, camera, cols, rows, json.dumps(grid), ref_image, _now()))
    conn.commit()
    conn.close()


def report_summary(start, end, camera=None):
    """Aggregates saved logs for [start, end] ('YYYY-MM-DD HH:MM:SS' strings, inclusive)."""
    conn = get_db_connection()
    cam_sql, cam_args = ('', ())
    if camera:
        cam_sql, cam_args = ' AND s.source = ?', (camera,)

    occ = conn.execute(f'''
        SELECT o.session_id, o.track_id, o.gender, o.total_seconds, o.time_per_zone, s.source
        FROM occupant_logs o JOIN monitoring_sessions s ON s.session_id = o.session_id
        WHERE o.updated_at BETWEEN ? AND ?{cam_sql}''', (start, end) + cam_args).fetchall()
    zone_seconds, people = {}, []
    for r in occ:
        for z, sec in json.loads(r['time_per_zone'] or '{}').items():
            zone_seconds[z] = zone_seconds.get(z, 0.0) + sec
        people.append({'session': r['session_id'], 'track_id': r['track_id'], 'gender': r['gender'],
                       'seconds': round(r['total_seconds'], 1), 'source': r['source']})
    people.sort(key=lambda p: -p['seconds'])

    pres = conn.execute(f'''
        SELECT substr(p.ts, 1, 10) AS day, substr(p.ts, 12, 2) AS hour, p.count AS count
        FROM presence_samples p JOIN monitoring_sessions s ON s.session_id = p.session_id
        WHERE p.zone = '*' AND p.ts BETWEEN ? AND ?{cam_sql}''', (start, end) + cam_args).fetchall()
    hourly, daily = {}, {}
    for r in pres:
        h = hourly.setdefault(int(r['hour']), [0, 0, 0])      # sum, samples, peak
        h[0] += r['count']
        h[1] += 1
        h[2] = max(h[2], r['count'])
        daily[r['day']] = daily.get(r['day'], 0.0) + r['count'] * 60.0 / 3600.0   # one sample per minute

    heat = conn.execute(f'''
        SELECT h.cols, h.rows, h.grid_json, h.ref_image FROM heatmaps h
        JOIN monitoring_sessions s ON s.session_id = h.session_id
        WHERE h.updated_at BETWEEN ? AND ?{cam_sql}''', (start, end) + cam_args).fetchall()
    grid, cols, rows, ref = None, 0, 0, ''
    for r in heat:
        g = json.loads(r['grid_json'] or '[]')
        if not g:
            continue
        if grid is None or (cols, rows) != (r['cols'], r['rows']):
            grid, cols, rows = [0.0] * (r['cols'] * r['rows']), r['cols'], r['rows']
        for i, v in enumerate(g[:len(grid)]):
            grid[i] += v
        ref = r['ref_image'] or ref
    sessions = conn.execute(f'''SELECT COUNT(*) AS n FROM monitoring_sessions s
        WHERE s.started_at <= ? AND COALESCE(s.ended_at, ?) >= ?{cam_sql}''', (end, end, start) + cam_args).fetchone()['n']
    conn.close()

    return {
        'sessions': sessions,
        'occupants': len(people),
        'person_hours': round(sum(p['seconds'] for p in people) / 3600.0, 2),
        'zones': sorted(({'zone': z, 'minutes': round(sec / 60.0, 1)} for z, sec in zone_seconds.items()),
                        key=lambda x: -x['minutes']),
        'top_people': people[:15],
        'hourly': [{'hour': h, 'avg': round(v[0] / v[1], 2), 'peak': v[2]} for h, v in sorted(hourly.items())],
        'daily': [{'day': d, 'person_hours': round(v, 2)} for d, v in sorted(daily.items())],
        'heatmap': {'cols': cols, 'rows': rows, 'grid': grid or [], 'ref_image': ref},
    }


def purge_old_presence(days):
    if not days or days <= 0:
        return
    conn = get_db_connection()
    conn.execute("DELETE FROM presence_samples WHERE ts < datetime('now', 'localtime', ?)", (f"-{int(days)} days",))
    conn.commit()
    conn.close()


def purge_face_crops(days):
    """Privacy: blanks stored face crops older than `days` while keeping the time logs. Returns rows cleared."""
    if not days or days <= 0:
        return 0
    conn = get_db_connection()
    cur = conn.execute("UPDATE occupant_logs SET face_b64 = '' WHERE face_b64 != '' AND updated_at < datetime('now', 'localtime', ?)",
                       (f"-{int(days)} days",))
    conn.commit()
    n = cur.rowcount
    conn.close()
    return n


# -------------------------------------------------------------------
# USER ACCOUNTS
# -------------------------------------------------------------------

def count_users():
    conn = get_db_connection()
    n = conn.execute('SELECT COUNT(*) AS n FROM users WHERE disabled = 0').fetchone()['n']
    conn.close()
    return n


def get_user(username):
    conn = get_db_connection()
    row = conn.execute('SELECT * FROM users WHERE username = ?', (username,)).fetchone()
    conn.close()
    return dict(row) if row else None


def list_users():
    conn = get_db_connection()
    rows = conn.execute('SELECT username, role, disabled, engine_mode, created_at, last_login FROM users ORDER BY username').fetchall()
    conn.close()
    return [dict(r) for r in rows]


def upsert_user(username, password_hash, role, engine_mode='gpu_local'):
    conn = get_db_connection()
    conn.execute('''INSERT INTO users (username, password_hash, role, engine_mode, created_at) VALUES (?,?,?,?,?)
                    ON CONFLICT(username) DO UPDATE SET password_hash = excluded.password_hash, role = excluded.role,
                                                         engine_mode = excluded.engine_mode, disabled = 0''',
                 (username, password_hash, role, engine_mode or 'gpu_local', _now()))
    conn.commit()
    conn.close()


def set_user_disabled(username, disabled):
    conn = get_db_connection()
    conn.execute('UPDATE users SET disabled = ? WHERE username = ?', (1 if disabled else 0, username))
    conn.commit()
    conn.close()


def delete_user(username):
    conn = get_db_connection()
    conn.execute('DELETE FROM users WHERE username = ?', (username,))
    conn.commit()
    conn.close()


def touch_login(username):
    conn = get_db_connection()
    conn.execute('UPDATE users SET last_login = ? WHERE username = ?', (_now(), username))
    conn.commit()
    conn.close()


# -------------------------------------------------------------------
# PERSON PHOTOS / RECOGNITION EXEMPLARS
# One registered person owns many photos (and live examples); each carries the face and body
# embeddings computed from it, so recognition can match against all of them.
# -------------------------------------------------------------------

def add_person_photo(person_id, photo_b64, face_vec, body_vecs, face_px=0, kind='upload', note=''):
    """face_vec: list|None; body_vecs: list of lists (several views of the body)."""
    conn = get_db_connection()
    cur = conn.execute('''INSERT INTO person_photos (person_id, kind, photo_b64, face_json, bodies_json, face_px, note, created_at)
                          VALUES (?,?,?,?,?,?,?,?)''',
                       (person_id, kind, photo_b64, json.dumps(face_vec) if face_vec else '', json.dumps(body_vecs or []),
                        int(face_px or 0), note, _now()))
    conn.commit()
    photo_id = cur.lastrowid
    conn.close()
    return photo_id


def list_person_photos(person_id):
    conn = get_db_connection()
    rows = conn.execute('SELECT id, kind, photo_b64, face_json, bodies_json, face_px, note, created_at '
                        'FROM person_photos WHERE person_id = ? ORDER BY id', (person_id,)).fetchall()
    conn.close()
    return [{'id': r['id'], 'kind': r['kind'], 'photo_b64': r['photo_b64'], 'has_face': bool(r['face_json']),
             'body_views': len(json.loads(r['bodies_json'] or '[]')), 'face_px': r['face_px'],
             'note': r['note'], 'created_at': r['created_at']} for r in rows]


def count_person_photos(person_id):
    conn = get_db_connection()
    n = conn.execute('SELECT COUNT(*) AS n FROM person_photos WHERE person_id = ?', (person_id,)).fetchone()['n']
    conn.close()
    return n


def get_all_person_exemplars():
    """{person_id: [{'face': list|None, 'bodies': [list, ...], 'kind': str}, ...]} for the detector."""
    conn = get_db_connection()
    rows = conn.execute('SELECT person_id, kind, face_json, bodies_json FROM person_photos ORDER BY id').fetchall()
    conn.close()
    out = {}
    for r in rows:
        try:
            out.setdefault(r['person_id'], []).append({
                'kind': r['kind'],
                'face': json.loads(r['face_json']) if r['face_json'] else None,
                'bodies': json.loads(r['bodies_json'] or '[]'),
            })
        except Exception:
            continue
    return out


def delete_person_photo(person_id, photo_id):
    conn = get_db_connection()
    cur = conn.execute('DELETE FROM person_photos WHERE id = ? AND person_id = ?', (photo_id, person_id))
    conn.commit()
    n = cur.rowcount
    conn.close()
    return n > 0


def set_primary_photo(person_id, photo_b64):
    conn = get_db_connection()
    conn.execute('UPDATE peoples SET photo_b64 = ? WHERE id = ?', (photo_b64, person_id))
    conn.commit()
    conn.close()


def purge_old_sessions(days):
    """Deletes sessions (and their occupant rows) that ended more than `days` ago. Returns sessions removed."""
    if not days or days <= 0:
        return 0
    cutoff = f"-{int(days)} days"
    conn = get_db_connection()
    old = [r['session_id'] for r in conn.execute(
        "SELECT session_id FROM monitoring_sessions WHERE ended_at IS NOT NULL AND ended_at < datetime('now', 'localtime', ?)",
        (cutoff,)).fetchall()]
    for sid in old:
        conn.execute('DELETE FROM occupant_logs WHERE session_id = ?', (sid,))
        conn.execute('DELETE FROM monitoring_sessions WHERE session_id = ?', (sid,))
    conn.commit()
    conn.close()
    return len(old)


def set_state(key, value):
    conn = get_db_connection()
    conn.execute('INSERT INTO app_state (key, value) VALUES (?, ?) '
                 'ON CONFLICT(key) DO UPDATE SET value = excluded.value', (key, json.dumps(value)))
    conn.commit()
    conn.close()


def get_state(key, default=None):
    conn = get_db_connection()
    row = conn.execute('SELECT value FROM app_state WHERE key = ?', (key,)).fetchone()
    conn.close()
    if not row:
        return default
    try:
        return json.loads(row['value'])
    except Exception:
        return default


def delete_state(key):
    conn = get_db_connection()
    conn.execute('DELETE FROM app_state WHERE key = ?', (key,))
    conn.commit()
    conn.close()


# Initialize database schema upon module import
init_db()
init_runtime_tables()
