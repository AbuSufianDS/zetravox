import random
import requests
from datetime import datetime, timedelta, timezone
from app import db
from app.models import PasswordResetOTP

BREVO_API_KEY = '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'


def generate_otp():
    return ''.join([str(random.randint(0, 9)) for _ in range(6)])


def send_otp_email(email, otp_code, username):
    print(f"\n📧 Attempting to send OTP to {email}...")

    try:
        url = "https://api.brevo.com/v3/smtp/email"
        headers = {
            "accept": "application/json",
            "api-key": BREVO_API_KEY,
            "content-type": "application/json"
        }
        data = {
            "sender": {"name": "ConnectHub", "email": "mdabusufian1323@gmail.com"},
            "to": [{"email": email, "name": username}],
            "subject": "Password Reset OTP - ConnectHub",
            "htmlContent": f"<h2>Your OTP Code: {otp_code}</h2><p>Valid for 10 minutes.</p>"
        }
        response = requests.post(url, json=data, headers=headers)
        if response.status_code == 201:
            print(f"✅ Email sent to {email}")
            return True
    except Exception as e:
        print(f"Email error: {e}")

    print(f"📝 OTP for {email}: {otp_code}")
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
    print(f"✅ OTP created: {otp_code}")
    return otp_code


def check_otp_code(user_id, otp_code):
    print(f"Verifying OTP: user={user_id}, code={otp_code}")

    otp_record = PasswordResetOTP.query.filter_by(
        user_id=user_id,
        otp_code=otp_code,
        is_used=False
    ).first()

    if otp_record:
        expires_at = otp_record.expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        now = datetime.now(timezone.utc)

        if expires_at > now:
            otp_record.is_used = True
            db.session.commit()
            print(f"✅ OTP verified for user {user_id}")
            return True
        else:
            print(f"❌ OTP expired for user {user_id}")
    else:
        print(f"❌ OTP not found for user {user_id}")

    return False