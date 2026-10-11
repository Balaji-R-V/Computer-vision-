"""
Accounts and access control.

Auth turns on automatically as soon as an account exists (or AEGIS_PASSWORD is set); until then the app
stays open so a fresh install is never locked out. Roles:
  admin   - everything, including settings and user management
  viewer  - read-only: can look at live view, logs, alerts and reports, but change nothing
"""
import hashlib
import hmac
import os
import re
import threading
import time
from datetime import timedelta
from urllib.parse import urlparse

from flask import Response, jsonify, redirect, render_template, request, session
from werkzeug.security import check_password_hash, generate_password_hash

import database
import secrets_store

LEGACY_USER = os.environ.get('AEGIS_USER', 'admin')
LEGACY_PASSWORD = os.environ.get('AEGIS_PASSWORD', '')
ROLES = ('admin', 'viewer')
PUBLIC_PATHS = {'/health', '/login', '/setup'}
MIN_PASSWORD_LENGTH = 8
MAX_FAILURES, LOCKOUT_SECONDS = 5, 300

_failures = {}          # ip -> [count, first_failure_ts]
_failures_lock = threading.Lock()


def auth_enabled():
    return bool(LEGACY_PASSWORD) or database.count_users() > 0


def _session_secret():
    return hashlib.sha256(('flask-session:' + secrets_store.master_key()).encode()).digest()


def current_user():
    """The signed-in user as {'username', 'role', 'engine_mode'}, or None. Accepts the session cookie or HTTP Basic credentials."""
    name = session.get('user')
    default_mode = os.environ.get('AEGIS_ENGINE_MODE', 'gpu_local')
    mode = session.get('engine_mode') or default_mode
    if session.get('legacy') and LEGACY_PASSWORD and name == LEGACY_USER:
        return {'username': LEGACY_USER, 'role': 'admin', 'engine_mode': mode}
    if name:
        user = database.get_user(name)
        if user and not user['disabled']:
            user_mode = session.get('engine_mode') or user.get('engine_mode') or mode
            return {'username': user['username'], 'role': user['role'], 'engine_mode': user_mode}
        session.clear()
    auth = request.authorization
    if auth and auth.username:
        if LEGACY_PASSWORD and hmac.compare_digest(auth.username, LEGACY_USER) and hmac.compare_digest(auth.password or '', LEGACY_PASSWORD):
            return {'username': LEGACY_USER, 'role': 'admin', 'engine_mode': mode}
        user = database.get_user(auth.username)
        if user and not user['disabled'] and check_password_hash(user['password_hash'], auth.password or ''):
            user_mode = session.get('engine_mode') or user.get('engine_mode') or mode
            return {'username': user['username'], 'role': user['role'], 'engine_mode': user_mode}
    return None


def _locked_out(ip):
    with _failures_lock:
        rec = _failures.get(ip)
        if not rec:
            return False
        if time.time() - rec[1] > LOCKOUT_SECONDS:
            del _failures[ip]
            return False
        return rec[0] >= MAX_FAILURES


def _record_failure(ip):
    with _failures_lock:
        rec = _failures.setdefault(ip, [0, time.time()])
        rec[0] += 1


def _safe_next(target):
    """Only allow same-site relative redirects after login."""
    if target and target.startswith('/') and not target.startswith('//') and not urlparse(target).netloc:
        return target
    return '/'


def valid_username(name):
    return bool(re.fullmatch(r'[A-Za-z0-9_.-]{3,32}', name or ''))


def init_auth(app):
    app.secret_key = _session_secret()
    app.config.update(SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE='Lax',
                      PERMANENT_SESSION_LIFETIME=timedelta(hours=12))

    ADMIN_ONLY_PREFIXES = ('/admin', '/api/users', '/api/settings', '/settings')

    @app.before_request
    def require_login():
        path = request.path
        if path in PUBLIC_PATHS or not auth_enabled():
            return None
        user = current_user()
        if user is None:
            if path.startswith('/api/') or path.startswith('/static/'):
                return Response('{"error":"Login required"}', 401, {'Content-Type': 'application/json',
                                'WWW-Authenticate': 'Basic realm="Aegis-OS"'})
            return redirect('/login?next=' + path)
        if user['role'] != 'admin':
            if request.method not in ('GET', 'HEAD', 'OPTIONS') and path != '/logout':
                return jsonify({'error': 'Your account is read-only'}), 403
            if path.startswith(ADMIN_ONLY_PREFIXES):
                return jsonify({'error': 'Administrator access required'}), 403
        request.environ['aegis.user'] = user
        return None

    @app.context_processor
    def inject_user():
        return {'current_user': current_user(), 'auth_enabled': auth_enabled()}

    # ---- sign in / out --------------------------------------------------------------------------
    @app.route('/login/aws')
    def login_aws():
        nxt = request.args.get('next', '/')
        return redirect(f"/login?engine=aws_rekognition&next={urllib.parse.quote(nxt)}")

    @app.route('/login/gpu')
    def login_gpu():
        nxt = request.args.get('next', '/')
        return redirect(f"/login?engine=gpu_local&next={urllib.parse.quote(nxt)}")

    @app.route('/login', methods=['GET', 'POST'])
    def login():
        nxt = _safe_next(request.values.get('next'))
        if not auth_enabled():
            return redirect('/setup')
        if request.method == 'GET':
            requested_engine = request.args.get('engine', '').strip().lower()
            return render_template('login.html', error=None, next=nxt, requested_engine=requested_engine)
        ip = request.remote_addr or '?'
        if _locked_out(ip):
            return render_template('login.html', error='Too many failed attempts. Try again in a few minutes.', next=nxt), 429
        username, password = request.form.get('username', '').strip(), request.form.get('password', '')
        user = database.get_user(username)
        ok = bool(user and not user['disabled'] and check_password_hash(user['password_hash'], password))
        legacy = False
        if not ok and LEGACY_PASSWORD and hmac.compare_digest(username, LEGACY_USER) and hmac.compare_digest(password, LEGACY_PASSWORD):
            ok, legacy, user = True, True, {'username': LEGACY_USER, 'role': 'admin', 'engine_mode': 'gpu_local'}
        if not ok:
            _record_failure(ip)
            return render_template('login.html', error='Wrong username or password.', next=nxt), 401
        with _failures_lock:
            _failures.pop(ip, None)
        session.clear()
        session.permanent = True
        session['user'] = user['username']

        # Engine Mode resolution (form selection -> user profile preference -> env default)
        form_engine = request.form.get('engine_mode', '').strip().lower()
        if form_engine in ('aws_rekognition', 'gpu_local'):
            active_engine = form_engine
        elif isinstance(user, dict) and user.get('engine_mode') in ('aws_rekognition', 'gpu_local'):
            active_engine = user['engine_mode']
        else:
            active_engine = os.environ.get('AEGIS_ENGINE_MODE', 'gpu_local').lower()
        session['engine_mode'] = active_engine

        # Sync with global engine manager if registered
        mgr = app.config.get('engine_manager')
        if mgr:
            try:
                mgr.switch_engine(active_engine)
            except Exception as e:
                print(f"Notice switching engine on login: {e}", flush=True)

        if legacy:
            session['legacy'] = True
        else:
            database.touch_login(user['username'])
        return redirect(nxt)

    @app.route('/logout', methods=['POST', 'GET'])
    def logout():
        session.clear()
        return redirect('/login')

    @app.route('/setup', methods=['GET', 'POST'])
    def setup():
        """First-run page: creates the initial administrator. Only available while no account exists."""
        if auth_enabled():
            return redirect('/')
        if request.method == 'GET':
            requested_engine = request.args.get('engine', '').strip().lower()
            return render_template('login.html', setup=True, error=None, next='/', requested_engine=requested_engine)
        username, password = request.form.get('username', '').strip(), request.form.get('password', '')
        engine_mode = request.form.get('engine_mode', 'gpu_local').strip().lower()
        if engine_mode not in ('aws_rekognition', 'gpu_local'):
            engine_mode = 'gpu_local'
        if not valid_username(username):
            return render_template('login.html', setup=True, error='Username: 3-32 letters, digits, . _ -', next='/'), 400
        if len(password) < MIN_PASSWORD_LENGTH:
            return render_template('login.html', setup=True, error=f'Password must be at least {MIN_PASSWORD_LENGTH} characters.', next='/'), 400
        database.upsert_user(username, generate_password_hash(password), 'admin', engine_mode)
        session.clear()
        session.permanent = True
        session['user'] = username
        session['engine_mode'] = engine_mode
        mgr = app.config.get('engine_manager')
        if mgr:
            try:
                mgr.switch_engine(engine_mode)
            except Exception:
                pass
        return redirect('/')

    @app.route('/api/me')
    def me():
        user = current_user()
        engine_mode = session.get('engine_mode') or (user.get('engine_mode') if user else 'gpu_local')
        return jsonify({'auth_enabled': auth_enabled(), 'username': user['username'] if user else None,
                        'role': user['role'] if user else ('admin' if not auth_enabled() else None),
                        'engine_mode': engine_mode})

    @app.route('/api/engine_mode', methods=['GET', 'POST'])
    def engine_mode_api():
        """Returns or switches active engine mode between 'aws_rekognition' and 'gpu_local'."""
        mgr = app.config.get('engine_manager')
        if request.method == 'POST':
            data = request.json or {}
            mode = (data.get('mode') or '').strip().lower()
            if mode not in ('aws_rekognition', 'gpu_local'):
                return jsonify({'error': "Invalid engine mode. Must be 'aws_rekognition' or 'gpu_local'"}), 400
            session['engine_mode'] = mode
            status = {}
            if mgr:
                try:
                    status = mgr.switch_engine(mode)
                except Exception as e:
                    return jsonify({'error': str(e)}), 400
            return jsonify({'success': True, 'mode': mode, 'status': status})
        
        # GET
        cur_mode = session.get('engine_mode') or (mgr.active_mode if mgr else 'gpu_local')
        status = mgr.get_status() if mgr else {'active_mode': cur_mode}
        return jsonify({'success': True, 'current_engine': cur_mode, 'status': status})

    # ---- user administration (admin only; enforced by the prefix rule above) --------------------
    @app.route('/admin/users')
    def users_page():
        return render_template('users.html')

    @app.route('/api/users', methods=['GET'])
    def users_list():
        return jsonify({'success': True, 'users': database.list_users()})

    @app.route('/api/users', methods=['POST'])
    def users_create():
        data = request.json or {}
        username, password, role = (data.get('username') or '').strip(), data.get('password') or '', data.get('role', 'viewer')
        if not valid_username(username):
            return jsonify({'error': 'Username: 3-32 letters, digits, . _ -'}), 400
        if len(password) < MIN_PASSWORD_LENGTH:
            return jsonify({'error': f'Password must be at least {MIN_PASSWORD_LENGTH} characters'}), 400
        if role not in ROLES:
            return jsonify({'error': 'Role must be admin or viewer'}), 400
        database.upsert_user(username, generate_password_hash(password), role)
        return jsonify({'success': True})

    def _active_admins():
        return [u for u in database.list_users() if u['role'] == 'admin' and not u['disabled']]

    @app.route('/api/users/<username>', methods=['PATCH'])
    def users_update(username):
        data = request.json or {}
        user = database.get_user(username)
        if not user:
            return jsonify({'error': 'No such user'}), 404
        me_name = (current_user() or {}).get('username')
        admins = _active_admins()
        losing_admin = user['role'] == 'admin' and len(admins) <= 1 and \
            (data.get('role') == 'viewer' or data.get('disabled') is True)
        if losing_admin:
            return jsonify({'error': 'Cannot demote or disable the last administrator'}), 400
        if data.get('disabled') is True and username == me_name:
            return jsonify({'error': 'You cannot disable your own account'}), 400
        if 'password' in data and data['password']:
            if len(data['password']) < MIN_PASSWORD_LENGTH:
                return jsonify({'error': f'Password must be at least {MIN_PASSWORD_LENGTH} characters'}), 400
            database.upsert_user(username, generate_password_hash(data['password']), data.get('role', user['role']))
        elif data.get('role') in ROLES:
            database.upsert_user(username, user['password_hash'], data['role'])
        if 'disabled' in data:
            database.set_user_disabled(username, bool(data['disabled']))
        return jsonify({'success': True})

    @app.route('/api/users/<username>', methods=['DELETE'])
    def users_delete(username):
        user = database.get_user(username)
        if not user:
            return jsonify({'error': 'No such user'}), 404
        if username == (current_user() or {}).get('username'):
            return jsonify({'error': 'You cannot delete your own account'}), 400
        if user['role'] == 'admin' and len(_active_admins()) <= 1:
            return jsonify({'error': 'Cannot delete the last administrator'}), 400
        database.delete_user(username)
        return jsonify({'success': True})
