from flask import request, session, jsonify, abort, current_app
from datetime import datetime
import json
import os
from flask_login import current_user, logout_user
from app import db
from app.models import User, Post, LoginHistory, SecurityEvent


class GDPRCompliance:
    def __init__(self, app=None):
        if app:
            self.init_app(app)

    def init_app(self, app):
        self._add_consent_middleware(app)
        self._register_routes(app)

    def _add_consent_middleware(self, app):
        @app.before_request
        def check_consent():
            if app.debug:
                session['gdpr_consent'] = True
                return

            exempt_paths = ['/static', '/gdpr', '/auth/login', '/auth/register', '/security']
            if any(request.path.startswith(path) for path in exempt_paths):
                return

            if not session.get('gdpr_consent', False):
                return jsonify({'error': 'GDPR consent required', 'consent_url': '/gdpr/consent'}), 403

    def _register_routes(self, app):

        @app.route('/gdpr/consent', methods=['GET', 'POST'])
        def gdpr_consent():
            if request.method == 'POST':
                session['gdpr_consent'] = True
                session['gdpr_consent_date'] = datetime.utcnow().isoformat()
                if current_user.is_authenticated:
                    current_user.set_gdpr_consent(True)
                return jsonify({'status': 'consent recorded'})
            return jsonify({
                'consents': [
                    'Account information (username, email)',
                    'Posts and social interactions',
                    'Session cookies',
                    'Email notifications'
                ],
                'version': '1.0'
            })

        @app.route('/gdpr/export-data')
        def export_user_data():
            if not current_user.is_authenticated:
                abort(401)
            user_data = {
                'user': {
                    'username': current_user.username,
                    'email': current_user.email,
                    'created_at': current_user.last_seen.isoformat() if current_user.last_seen else None,
                },
                'posts': [{'body': p.body, 'timestamp': p.timestamp.isoformat()} for p in current_user.posts.all()],
                'export_date': datetime.utcnow().isoformat()
            }
            response = jsonify(user_data)
            response.headers['Content-Disposition'] = f'attachment; filename=user_data_{current_user.id}.json'
            return response

        @app.route('/gdpr/delete-request', methods=['POST'])
        def request_account_deletion():
            if not current_user.is_authenticated:
                abort(401)
            from app.models import DataDeletionRequest
            existing = DataDeletionRequest.query.filter_by(user_id=current_user.id, status='pending').first()
            if existing:
                return jsonify({'message': 'Deletion request already pending'}), 400
            request_obj = DataDeletionRequest(user_id=current_user.id, request_ip=request.remote_addr)
            db.session.add(request_obj)
            db.session.commit()
            SecurityEvent.log(current_user.id, 'deletion_requested', request.remote_addr,
                              f"User requested account deletion")
            return jsonify({'message': 'Deletion request submitted', 'status': 'pending'})
