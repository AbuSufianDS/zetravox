from flask import request, abort, g, current_app
import time
import re


class SecurityMiddleware:
    def __init__(self, app=None):
        if app:
            self.init_app(app)

    def init_app(self, app):
        self._set_security_headers(app)
        self._add_request_validation(app)
        self._add_sql_injection_detection(app)

    def _set_security_headers(self, app):
        @app.after_request
        def add_security_headers(response):
            headers = {
                'X-Frame-Options': 'DENY',
                'X-Content-Type-Options': 'nosniff',
                'X-XSS-Protection': '1; mode=block',
                'Referrer-Policy': 'strict-origin-when-cross-origin'
            }
            for header, value in headers.items():
                response.headers[header] = value
            response.headers.pop('Server', None)
            return response

    def _add_request_validation(self, app):
        @app.before_request
        def validate_request():
            if request.content_length and request.content_length > 10 * 1024 * 1024:
                abort(413, "Request too large")
            g.request_start_time = time.time()

    def _add_sql_injection_detection(self, app):
        @app.before_request
        def detect_sql_injection():
            sql_patterns = [
                r'(?i)(union.*select|select.*from|insert.*into|delete.*from)',
                r'(?i)(or\s+1\s*=\s*1|and\s+1\s*=\s*1)',
                r'(?i)(drop\s+table|alter\s+table|create\s+table)'
            ]

            for key, value in request.args.items():
                for pattern in sql_patterns:
                    if re.search(pattern, str(value)):
                        current_app.logger.warning(f"SQL injection attempt from {request.remote_addr}")
                        abort(400)
