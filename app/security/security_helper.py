import bleach
import secrets
import re
from datetime import datetime


class SecurityHelper:
    ALLOWED_TAGS = ['p', 'br', 'strong', 'em', 'u', 'h1', 'h2', 'h3', 'ul', 'ol', 'li', 'a', 'code', 'pre']
    ALLOWED_ATTRIBUTES = {'a': ['href', 'title', 'target'], 'code': ['class'], 'pre': ['class']}

    @staticmethod
    def sanitize_html(content):
        if not content:
            return content
        return bleach.clean(content, tags=SecurityHelper.ALLOWED_TAGS, attributes=SecurityHelper.ALLOWED_ATTRIBUTES,
                            strip=True)

    @staticmethod
    def validate_input(data, max_length):
        if data and len(str(data)) > max_length:
            raise ValueError(f"Input exceeds maximum length of {max_length}")
        return data

    @staticmethod
    def detect_sql_injection(value):
        if not value or not isinstance(value, str):
            return False
        sql_patterns = [
            r'(?i)(union.*select|select.*from|insert.*into|delete.*from)',
            r'(?i)(or\s+1\s*=\s*1|and\s+1\s*=\s*1)',
            r'(?i)(drop\s+table|alter\s+table|create\s+table)'
        ]
        for pattern in sql_patterns:
            if re.search(pattern, value):
                return True
        dangerous = ['--', ';', '/*', '*/', 'xp_', 'sp_']
        for pattern in dangerous:
            if pattern.lower() in value.lower():
                return True
        return False

    @staticmethod
    def mask_sensitive(data, show_first=2, show_last=2):
        if not data or len(data) < show_first + show_last + 2:
            return "***MASKED***"
        return f"{data[:show_first]}...{data[-show_last:]}"

    @staticmethod
    def generate_secure_token():
        return secrets.token_urlsafe(32)