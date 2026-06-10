@"
# Security Policy for Zetravox

## Reporting a Vulnerability

If you discover a security vulnerability, please **DO NOT** report it publicly.

### Private Reporting
- **Email**: security@zetravox.com

## Security Features

### Implemented
- Password hashing using Werkzeug
- CSRF protection on all forms
- Session management with expiration
- Login attempt rate limiting (5 attempts)
- Account lockout (15 minutes)
- Two-Factor Authentication (2FA)
- XSS prevention using Bleach
- SQL injection prevention via SQLAlchemy ORM
- Secure cookie flags (HttpOnly, Secure, SameSite)

### Environment Security
- No hardcoded secrets in code
- Environment variables for all sensitive data
- `.env` excluded from version control

## API Keys Management

**NEVER commit API keys to Git!**

Use environment variables instead:
\`\`\`bash
export DEEPSEEK_API_KEY="your-key-here"
\`\`\`

## If a Key is Compromised
1. Immediately revoke the compromised key
2. Generate a new key from the service provider
3. Update environment variables
4. Restart the application

## Supported Versions

| Version | Supported |
|---------|-----------|
| 1.0.x   | ✅ Current |
| < 1.0   | ❌ Not supported |

## Last Updated

June 10, 2025
"@ | Out-File -FilePath SECURITY.md -Encoding utf8