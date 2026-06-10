from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask import jsonify

limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["200 per day", "50 per hour"],
    storage_uri="memory://",
    strategy="fixed-window"
)

def rate_limit_response(request_limit):
    return jsonify({
        'error': 'Rate limit exceeded',
        'message': 'Too many requests. Please try again later.',
        'retry_after': request_limit.reset_time
    }), 429

def auth_limit():
    return limiter.limit("5 per minute")

def api_limit():
    return limiter.limit("100 per hour")

def registration_limit():
    return limiter.limit("3 per hour")
