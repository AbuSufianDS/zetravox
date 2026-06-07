import random
import requests
from datetime import datetime, timedelta, timezone
import os
from app import db
from app.models import PasswordResetOTP

# Your Brevo API key
BREVO_API_KEY = "re_DpWrW2JS_469v7crEMB3GwciZuGbmKnyr"


def generate_otp():
    return ''.join([str(random.randint(0, 9)) for _ in range(6)])


def send_otp_email(email, otp_code, username):
    """Send OTP using Brevo API"""

    try:
        url = "https://api.brevo.com/v3/smtp/email"

        headers = {
            "accept": "application/json",
            "api-key": BREVO_API_KEY,
            "content-type": "application/json"
        }

        data = {
            "sender": {
                "name": "ConnectHub",
                "email": "mdabusufian1323@gmail.com"
            },
            "to": [{"email": email, "name": username}],
            "subject": "Password Reset OTP - ConnectHub",
            "htmlContent": f"""
            <!DOCTYPE html>
            <html>
            <head>
                <style>
                    body {{ font-family: Arial, sans-serif; }}
                    .container {{ max-width: 500px; margin: 0 auto; padding: 20px; }}
                    .otp {{ font-size: 36px; font-weight: bold; color: #667eea; text-align: center; margin: 20px 0; }}
                </style>
            </head>
            <body>
                <div class="container">
                    <h2>Password Reset Request</h2>
                    <p>Hello <strong>{username}</strong>,</p>
                    <p>Your OTP code is:</p>
                    <div class="otp">{otp_code}</div>
                    <p>This code expires in <strong>10 minutes</strong>.</p>
                    <p>If you didn't request this, please ignore this email.</p>
                </div>
            </body>
            </html>
            """
        }

        response = requests.post(url, json=data, headers=headers)

        if response.status_code == 201:
            print(f"✅ OTP email sent to {email}")
            return True
        else:
            print(f"❌ Brevo error: {response.status_code} - {response.text}")
            # Fallback to console print
            print(f"📝 OTP for {email}: {otp_code}")
            return True

    except Exception as e:
        print(f"❌ Email error: {e}")
        print(f"📝 Fallback - OTP for {email}: {otp_code}")
        return True


def create_password_reset_otp(user_id):
    PasswordResetOTP.query.filter_by(user_id=user_id, is_used=False).delete()

    otp_code = generate_otp()
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=10)

    otp_record = PasswordResetOTP(
        user_id=user_id,
        otp_code=otp_code,
        expires_at=expires_at,
        is_used=False
    )
    db.session.add(otp_record)
    db.session.commit()

    print(f"✅ OTP created for user {user_id}: {otp_code}")
    return otp_code


def verify_otp(user_id, otp_code):
    otp_record = PasswordResetOTP.query.filter_by(
        user_id=user_id,
        otp_code=otp_code,
        is_used=False
    ).first()

    if otp_record and otp_record.expires_at > datetime.now(timezone.utc):
        otp_record.is_used = True
        db.session.commit()
        return True
    return False