"""Alerts, settings, reports and camera-list endpoints/pages."""
import csv
import io
import time
from datetime import datetime, timedelta

from flask import Response, jsonify, render_template, request

import alerts
import app_settings
import database


def _who():
    from auth import current_user
    return (current_user() or {}).get('username', 'local')


def apply_recognition_settings(detector, s):
    detector.DB_MATCH_SIM = float(s['body_match_threshold'])
    detector.face_match_sim = float(s['face_match_threshold'])
    detector.auto_learn = bool(s['auto_learn'])


def register(app, detector, stream_manager, active_stream_configs, live_stream_stats):

    # ---- pages ------------------------------------------------------------------------------------
    @app.route('/alerts')
    def alerts_page():
        return render_template('alerts.html')

    @app.route('/reports')
    def reports_page():
        return render_template('reports.html')

    @app.route('/settings')
    def settings_page():
        return render_template('settings.html')

    # ---- recognition photos -------------------------------------------------------------------------
    @app.route('/api/peoples/analyze_photo', methods=['POST'])
    def analyze_person_photo():
        """Checks a photo BEFORE it is saved and tells the user what recognition can use from it."""
        img = detector._decode_photo((request.json or {}).get('photo_b64'))
        if img is None:
            return jsonify({'error': 'The image could not be read.'}), 400
        return jsonify({'success': True, 'report': detector.public_report(detector.analyze_photo(detector.prepare_photo(img)))})

    @app.route('/api/peoples/recognition')
    def peoples_recognition():
        """Per registered person: how many face/body exemplars recognition currently has."""
        return jsonify({'success': True, 'people': {
            str(pid): {'faces': len(p['faces']), 'bodies': len(p['bodies']), 'photos': database.count_person_photos(pid)}
            for pid, p in detector.db_peoples.items()}})

    @app.route('/api/peoples/<int:person_id>/photos', methods=['GET'])
    def person_photos(person_id):
        return jsonify({'success': True, 'photos': database.list_person_photos(person_id)})

    @app.route('/api/peoples/<int:person_id>/photos', methods=['POST'])
    def person_photo_add(person_id):
        if not database.get_person_by_id(person_id):
            return jsonify({'error': 'Person not found'}), 404
        try:
            report = detector.add_person_photo(person_id, (request.json or {}).get('photo_b64'))
        except ValueError as e:
            return jsonify({'error': str(e)}), 400
        return jsonify({'success': True, 'report': report})

    @app.route('/api/peoples/<int:person_id>/photos/<int:photo_id>', methods=['DELETE'])
    def person_photo_delete(person_id, photo_id):
        if not database.delete_person_photo(person_id, photo_id):
            return jsonify({'error': 'Photo not found'}), 404
        detector.load_db_peoples()
        return jsonify({'success': True})

    @app.route('/api/peoples/<int:person_id>/link_occupant', methods=['POST'])
    def person_link_occupant(person_id):
        """Teach recognition from live tracking: 'Person #7' on camera is really this registered person."""
        data = request.json or {}
        try:
            photo_id = detector.learn_live_identity(person_id, data.get('identity'), data.get('thumb_b64', ''))
        except ValueError as e:
            return jsonify({'error': str(e)}), 400
        return jsonify({'success': True, 'photo_id': photo_id})

    # ---- cameras ----------------------------------------------------------------------------------
    @app.route('/api/cameras')
    def cameras():
        out = []
        for sid, w in stream_manager.all_active():
            cfg = active_stream_configs.get(sid, {})
            st = live_stream_stats.get(sid, {})
            out.append({'stream_id': sid, 'label': w.label, 'status': w.status,
                        'people': st.get('person_count', 0), 'fps': st.get('fps', 0)})
        return jsonify({'success': True, 'cameras': out})

    # ---- alerts -----------------------------------------------------------------------------------
    @app.route('/api/alerts')
    def alerts_list():
        limit = min(int(request.args.get('limit', 100)), 500)
        return jsonify({'success': True, 'alerts': database.list_alerts(limit, request.args.get('open') == '1'),
                        'open_count': database.count_open_alerts()})

    @app.route('/api/alerts/count')
    def alerts_count():
        return jsonify({'success': True, 'open_count': database.count_open_alerts()})

    @app.route('/api/alerts/ack', methods=['POST'])
    def alerts_ack():
        data = request.json or {}
        ids = None if data.get('all') else [int(i) for i in data.get('ids', [])]
        database.acknowledge_alerts(ids, _who())
        return jsonify({'success': True, 'open_count': database.count_open_alerts()})

    # ---- settings (admin only; enforced by the /api/settings prefix rule) -------------------------
    @app.route('/api/settings/<section>', methods=['GET'])
    def settings_get(section):
        if section not in app_settings.DEFAULTS:
            return jsonify({'error': 'Unknown settings section'}), 404
        return jsonify({'success': True, 'settings': app_settings.public(section)})

    @app.route('/api/settings/<section>', methods=['POST'])
    def settings_save(section):
        if section not in app_settings.DEFAULTS:
            return jsonify({'error': 'Unknown settings section'}), 404
        try:
            saved = app_settings.update(section, request.json or {})
        except (ValueError, TypeError) as e:
            return jsonify({'error': str(e)}), 400
        if section == 'privacy':
            detector.blur_faces = bool(saved['blur_faces'])
        if section == 'recognition':
            apply_recognition_settings(detector, saved)
        if section == 'aws' and hasattr(detector, 'aws_detector') and detector.aws_detector:
            detector.aws_detector.reload_credentials()
        return jsonify({'success': True, 'settings': saved})

    @app.route('/api/settings/aws/test', methods=['POST'])
    def settings_test_aws():
        """Tests AWS Rekognition API connection and returns latency & collection status."""
        if hasattr(detector, 'aws_detector') and detector.aws_detector:
            diag = detector.aws_detector.run_diagnostic_test()
            if diag.get('connected'):
                return jsonify({'success': True, 'diagnostics': diag})
            return jsonify({'error': diag.get('message', 'AWS connection failed'), 'diagnostics': diag}), 400
        return jsonify({'error': 'AWS Rekognition detector not loaded'}), 500

    @app.route('/api/settings/alerts/test', methods=['POST'])
    def settings_test_notification():
        """Sends a test message through the configured webhook/email so the setup can be verified."""
        cfg = app_settings.get('alerts', use_cache=False)
        if not (cfg['webhook_url'] or (cfg['email_to'] and cfg['smtp_host'])):
            return jsonify({'error': 'Configure a webhook URL or an email server first'}), 400
        errors = []
        text = f"[INFO] Test notification from Aegis-OS ({time.strftime('%Y-%m-%d %H:%M:%S')})"
        if cfg['webhook_url']:
            try:
                alerts._send_webhook(cfg['webhook_url'], text, {'kind': 'test'})
            except Exception as e:
                errors.append(f'Webhook: {e}')
        if cfg['email_to'] and cfg['smtp_host']:
            try:
                alerts._send_email(cfg, 'Aegis-OS test notification', text)
            except Exception as e:
                errors.append(f'Email: {e}')
        if errors:
            return jsonify({'error': '; '.join(errors)}), 502
        return jsonify({'success': True})

    # ---- reports ----------------------------------------------------------------------------------
    def _range():
        today = datetime.now().date()
        try:
            start = datetime.strptime(request.args.get('start') or str(today - timedelta(days=6)), '%Y-%m-%d')
            end = datetime.strptime(request.args.get('end') or str(today), '%Y-%m-%d')
        except ValueError:
            raise ValueError('Dates must be YYYY-MM-DD')
        if end < start:
            raise ValueError('End date is before the start date')
        return (start.strftime('%Y-%m-%d 00:00:00'), end.strftime('%Y-%m-%d 23:59:59'))

    @app.route('/api/reports/summary')
    def report_summary():
        try:
            start, end = _range()
        except ValueError as e:
            return jsonify({'error': str(e)}), 400
        data = database.report_summary(start, end, request.args.get('camera') or None)
        data.update(success=True, start=start[:10], end=end[:10])
        return jsonify(data)

    @app.route('/api/reports/export.csv')
    def report_export():
        try:
            start, end = _range()
        except ValueError as e:
            return jsonify({'error': str(e)}), 400
        data = database.report_summary(start, end, request.args.get('camera') or None)
        out = io.StringIO()
        w = csv.writer(out)
        w.writerow(['report', start[:10], 'to', end[:10]])
        w.writerow([])
        w.writerow(['zone', 'person_minutes'])
        for z in data['zones']:
            w.writerow([z['zone'], z['minutes']])
        w.writerow([])
        w.writerow(['hour_of_day', 'average_people', 'peak_people'])
        for h in data['hourly']:
            w.writerow([h['hour'], h['avg'], h['peak']])
        w.writerow([])
        w.writerow(['day', 'person_hours'])
        for d in data['daily']:
            w.writerow([d['day'], d['person_hours']])
        w.writerow([])
        w.writerow(['session', 'occupant', 'gender', 'seconds'])
        for p in data['top_people']:
            w.writerow([p['session'], p['track_id'], p['gender'], p['seconds']])
        return Response(out.getvalue(), mimetype='text/csv',
                        headers={'Content-Disposition': f'attachment; filename=report_{start[:10]}_{end[:10]}.csv'})
