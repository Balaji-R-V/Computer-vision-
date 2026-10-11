"""
Alert rules, notifications and event clips.

Per camera, an AlertEngine watches the stream for:
  - camera offline (and back online)
  - a person staying in one zone longer than a limit
  - anyone entering a restricted zone
Each alert is saved (with a snapshot and a short animated clip of the moments before and after),
shown in the Alerts page, and sent to the configured webhook and/or email.
"""
import io
import json
import os
import smtplib
import threading
import time
import urllib.request
from collections import deque
from email.message import EmailMessage

import cv2
import numpy as np

import app_settings
import database

CLIPS_DIR = os.path.join(os.path.dirname(__file__), 'static', 'clips')
os.makedirs(CLIPS_DIR, exist_ok=True)

UNASSIGNED = 'Floating / Unassigned'
PRESENCE_GAP_SECONDS = 30       # absent this long = the stay is over; a new one starts when they return


def person_label(person_id):
    pid = str(person_id)
    return f"Person #{pid}" if pid.isdigit() else pid


# ---------------------------------------------------------------------------------------------------
# Notifications
# ---------------------------------------------------------------------------------------------------

def _send_webhook(url, text, alert):
    # 'text' (Slack/Teams) and 'content' (Discord) both set so the same URL type works for each.
    body = json.dumps({'text': text, 'content': text, 'alert': alert}).encode()
    req = urllib.request.Request(url, data=body, headers={'Content-Type': 'application/json'})
    urllib.request.urlopen(req, timeout=10).read()


def _send_email(cfg, subject, text, snapshot_path=None):
    msg = EmailMessage()
    msg['Subject'] = subject
    msg['From'] = cfg['smtp_from'] or cfg['smtp_user']
    msg['To'] = cfg['email_to']
    msg.set_content(text)
    if snapshot_path and os.path.exists(snapshot_path):
        with open(snapshot_path, 'rb') as f:
            msg.add_attachment(f.read(), maintype='image', subtype='jpeg', filename='snapshot.jpg')
    with smtplib.SMTP(cfg['smtp_host'], int(cfg['smtp_port']), timeout=15) as smtp:
        if cfg['smtp_tls']:
            smtp.starttls()
        if cfg['smtp_user']:
            smtp.login(cfg['smtp_user'], cfg['smtp_password'])
        smtp.send_message(msg)


def notify(alert, snapshot_path=None):
    """Sends an alert to the configured channels in a background thread; failures are logged, never raised."""
    cfg = app_settings.get('alerts')
    if not cfg['enabled']:
        return
    text = f"[{alert['severity'].upper()}] {alert['message']} ({alert['camera']}, {alert['ts']})"

    def run():
        if cfg['webhook_url']:
            try:
                _send_webhook(cfg['webhook_url'], text, alert)
            except Exception as e:
                print(f"Alert webhook failed: {e}", flush=True)
        if cfg['email_to'] and cfg['smtp_host']:
            try:
                _send_email(cfg, f"Aegis-OS alert: {alert['kind']}", text, snapshot_path)
            except Exception as e:
                print(f"Alert email failed: {e}", flush=True)

    if cfg['webhook_url'] or (cfg['email_to'] and cfg['smtp_host']):
        threading.Thread(target=run, daemon=True, name='alert-notify').start()


# ---------------------------------------------------------------------------------------------------
# Clips
# ---------------------------------------------------------------------------------------------------

class ClipRecorder:
    """Keeps a few seconds of recent frames so an alert can include what happened just before and after it."""

    SAMPLE_INTERVAL = 0.25          # 4 frames per second is plenty for a review clip
    WIDTH = 640

    def __init__(self):
        self._frames = deque()      # (timestamp, jpeg bytes)
        self._pending = []          # [(alert_id, trigger_ts, post_seconds, pre_seconds)]
        self._last_added = 0.0

    def add(self, now, frame):
        if now - self._last_added < self.SAMPLE_INTERVAL:
            return
        self._last_added = now
        h, w = frame.shape[:2]
        small = cv2.resize(frame, (self.WIDTH, int(h * self.WIDTH / w))) if w > self.WIDTH else frame
        ok, buf = cv2.imencode('.jpg', small, [cv2.IMWRITE_JPEG_QUALITY, 60])
        if ok:
            self._frames.append((now, buf.tobytes()))
        horizon = now - 40
        while self._frames and self._frames[0][0] < horizon:
            self._frames.popleft()

    def schedule(self, alert_id, now, seconds):
        self._pending.append((alert_id, now, seconds))

    def tick(self, now):
        """Writes any clip whose 'after' window has elapsed (encoding runs off the worker thread)."""
        ready = [p for p in self._pending if now >= p[1] + p[2]]
        if not ready:
            return
        self._pending = [p for p in self._pending if p not in ready]
        for alert_id, trigger, seconds in ready:
            frames = [jpg for ts, jpg in self._frames if trigger - seconds <= ts <= trigger + seconds]
            if len(frames) >= 2:
                threading.Thread(target=self._write_gif, args=(alert_id, frames), daemon=True, name='clip-writer').start()

    @staticmethod
    def _write_gif(alert_id, jpegs):
        try:
            from PIL import Image
            images = [Image.open(io.BytesIO(j)).convert('P', palette=Image.ADAPTIVE, colors=128) for j in jpegs]
            name = f"alert_{alert_id}.gif"
            images[0].save(os.path.join(CLIPS_DIR, name), save_all=True, append_images=images[1:],
                           duration=int(ClipRecorder.SAMPLE_INTERVAL * 1000), loop=0, optimize=True)
            database.set_alert_media(alert_id, clip=f"/static/clips/{name}")
        except Exception as e:
            print(f"Clip write failed for alert {alert_id}: {e}", flush=True)


# ---------------------------------------------------------------------------------------------------
# Rules
# ---------------------------------------------------------------------------------------------------

class AlertEngine:
    def __init__(self, camera_id, camera_label, recorder):
        self.camera_id = camera_id
        self.camera_label = camera_label
        self.recorder = recorder
        self._stays = {}            # (person, zone) -> [first_seen, last_seen]
        self._inside = set()        # (person, zone) present at the previous evaluation
        self._cooldowns = {}        # (kind, key) -> last raised
        self._offline_since = None
        self._offline_alerted = False
        self._last_jpeg = None      # last good frame, kept for 'camera offline' alerts
        self.current_frame = None   # newest annotated frame (set by the worker); encoded only when an alert fires

    # ---- helpers ----
    def _cooling(self, kind, key, now, minutes):
        last = self._cooldowns.get((kind, key))
        return last is not None and now - last < minutes * 60

    def raise_alert(self, kind, severity, message, now, person='', zone='', jpeg=None, clip=True):
        alert_id = database.add_alert(self.camera_label, kind, severity, message, person, zone)
        snapshot_path = None
        if jpeg is None:
            if kind in ('camera_offline', 'camera_online') or self.current_frame is None:
                jpeg = self._last_jpeg
            else:
                ok, buf = cv2.imencode('.jpg', self.current_frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
                jpeg = buf.tobytes() if ok else self._last_jpeg
        if jpeg:
            name = f"alert_{alert_id}.jpg"
            snapshot_path = os.path.join(CLIPS_DIR, name)
            with open(snapshot_path, 'wb') as f:
                f.write(jpeg)
            database.set_alert_media(alert_id, snapshot=f"/static/clips/{name}")
        cfg = app_settings.get('alerts')
        if clip and cfg['clip_seconds'] > 0:
            self.recorder.schedule(alert_id, now, cfg['clip_seconds'])
        notify({'id': alert_id, 'kind': kind, 'severity': severity, 'message': message, 'camera': self.camera_label,
                'person': person, 'zone': zone, 'ts': time.strftime('%Y-%m-%d %H:%M:%S')}, snapshot_path)
        print(f"ALERT #{alert_id} [{kind}] {message}", flush=True)
        return alert_id

    def remember_frame(self, frame):
        ok, buf = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
        if ok:
            self._last_jpeg = buf.tobytes()

    # ---- camera state ----
    def on_offline(self, now):
        cfg = app_settings.get('alerts')
        if not cfg['enabled']:
            return
        if self._offline_since is None:
            self._offline_since = now
        if not self._offline_alerted and now - self._offline_since >= cfg['offline_after_seconds']:
            self._offline_alerted = True
            self.raise_alert('camera_offline', 'critical',
                             f"Camera {self.camera_label} has been offline for {int(now - self._offline_since)} s",
                             now, clip=False)

    def on_online(self, now):
        if self._offline_alerted:
            self.raise_alert('camera_online', 'info', f"Camera {self.camera_label} is back online", now, clip=False)
        self._offline_since = None
        self._offline_alerted = False

    # ---- per frame ----
    def on_frame(self, people, now):
        """people: the detector's per-person records for this frame (person_id, zone)."""
        cfg = app_settings.get('alerts')
        if not cfg['enabled']:
            return
        restricted = {z.lower() for z in cfg['restricted_zones']}
        inside_now = set()
        for p in people:
            person, zone = str(p.get('person_id')), p.get('zone') or UNASSIGNED
            key = (person, zone)
            inside_now.add(key)

            stay = self._stays.get(key)
            if stay is None or now - stay[1] > PRESENCE_GAP_SECONDS:
                stay = self._stays[key] = [now, now]
            stay[1] = now

            if zone.lower() in restricted and key not in self._inside and not self._cooling('restricted', zone, now, cfg['cooldown_minutes']):
                self._cooldowns[('restricted', zone)] = now
                self.raise_alert('restricted_zone', 'critical',
                                 f"{person_label(person)} entered restricted zone '{zone}'", now, person=person, zone=zone)

            minutes = (now - stay[0]) / 60.0
            if cfg['dwell_minutes'] > 0 and zone != UNASSIGNED and minutes >= cfg['dwell_minutes'] \
                    and not self._cooling('dwell', key, now, cfg['cooldown_minutes']):
                self._cooldowns[('dwell', key)] = now
                self.raise_alert('dwell', 'warning',
                                 f"{person_label(person)} has been in '{zone}' for {int(minutes)} min", now, person=person, zone=zone)
        self._inside = inside_now
        for k in [k for k, v in self._stays.items() if now - v[1] > 3600]:
            del self._stays[k]
