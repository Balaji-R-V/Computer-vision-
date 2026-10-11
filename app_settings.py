"""Runtime settings stored in the database (alert rules, notification channels, privacy)."""
import threading
import time

import database
import secrets_store

DEFAULTS = {
    'alerts': {
        'enabled': True,
        'offline_after_seconds': 60,       # camera unreachable this long -> alert
        'dwell_minutes': 0,                # someone stays in one zone this long -> alert (0 = off)
        'restricted_zones': [],            # zone names; any entry raises an alert
        'cooldown_minutes': 10,            # same alert is not repeated within this time
        'clip_seconds': 5,                 # seconds of video before AND after the event
        'webhook_url': '',                 # Slack / Teams / Discord / generic incoming-webhook URL
        'email_to': '',                    # comma-separated recipients
        'smtp_host': '', 'smtp_port': 587, 'smtp_user': '', 'smtp_password': '', 'smtp_from': '', 'smtp_tls': True,
    },
    'recognition': {
        'body_match_threshold': 0.72,      # how alike a body must look to a registered person (lower = names more people, more mistakes)
        'face_match_threshold': 0.40,      # how alike a face must look (lower = more matches, more mistakes)
        'auto_learn': True,                # after a confident face match, remember how that person looks on camera
    },
    'privacy': {
        'blur_faces': False,               # blur heads in the live view/clips and pixelate stored face crops
        'store_faces': True,               # save face crops in the occupant log at all
        'face_retention_days': 30,         # blank stored face crops older than this (0 = keep)
        'presence_retention_days': 180,    # delete presence history older than this (0 = keep)
    },
    'aws': {
        'access_key_id': '',               # AWS Access Key ID
        'secret_access_key': '',           # AWS Secret Access Key (encrypted in database)
        'region': 'us-east-1',             # AWS Default Region (e.g. us-east-1, eu-west-1)
        'collection_id': 'aegis-rekognition-collection', # AWS Rekognition Collection ID
        'min_confidence': 50.0,            # Minimum detection confidence (0-100)
        'sample_interval_sec': 0.35,       # Cloud API keyframe interval (seconds)
    },
}
SECRET_FIELDS = {'alerts': ('smtp_password',), 'aws': ('secret_access_key',)}
MASK = '********'
_cache = {}
_lock = threading.Lock()


def get(section, use_cache=True):
    """Current settings for a section, defaults filled in, secrets decrypted."""
    with _lock:
        hit = _cache.get(section)
        if use_cache and hit and time.time() - hit[0] < 5:
            return dict(hit[1])
    saved = database.get_state(f'settings_{section}', {}) or {}
    merged = {**DEFAULTS[section], **saved}
    for f in SECRET_FIELDS.get(section, ()):
        merged[f] = secrets_store.decrypt(merged.get(f) or '')
    with _lock:
        _cache[section] = (time.time(), merged)
    return dict(merged)


def public(section):
    """Settings safe to send to the browser (secrets masked)."""
    out = get(section, use_cache=False)
    for f in SECRET_FIELDS.get(section, ()):
        out[f] = MASK if out.get(f) else ''
    return out


def update(section, patch):
    """Validates and saves a partial update. A masked/blank secret keeps the stored value."""
    current = get(section, use_cache=False)
    base = DEFAULTS[section]
    clean = {}
    for key, default in base.items():
        if key not in patch:
            clean[key] = current[key]
            continue
        val = patch[key]
        if isinstance(default, bool):
            val = bool(val)
        elif isinstance(default, float):
            val = float(val)
            if key == 'body_match_threshold':
                val = min(0.95, max(0.50, val))
            elif key == 'face_match_threshold':
                val = min(0.80, max(0.25, val))
        elif isinstance(default, int):
            val = max(0, int(val))
        elif isinstance(default, list):
            val = [str(v).strip() for v in (val if isinstance(val, list) else str(val).split(',')) if str(v).strip()]
        else:
            val = str(val).strip()
        if key in SECRET_FIELDS.get(section, ()) and val in ('', MASK):
            val = current[key]
        clean[key] = val
    if section == 'alerts' and clean['webhook_url'] and not clean['webhook_url'].lower().startswith(('http://', 'https://')):
        raise ValueError('Webhook URL must start with http:// or https://')
    to_store = dict(clean)
    for f in SECRET_FIELDS.get(section, ()):
        to_store[f] = secrets_store.encrypt(to_store.get(f) or '')
    database.set_state(f'settings_{section}', to_store)
    with _lock:
        _cache.pop(section, None)
    return public(section)
