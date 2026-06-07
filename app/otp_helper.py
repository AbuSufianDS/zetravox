import random
from datetime import datetime, timedelta, timezone
from flask import current_app
from app import db
from app.models import PasswordResetOTP, User


def generate_otp():
    return ''.join([str(random.randint(0, 9)) for _ in range(6)])


def send_otp_email(email, otp_code, username):
    # Print OTP to console/logs
    print("\n" + "=" * 60)
    print("🔐 PASSWORD RESET OTP")
    print("=" * 60)
    print(f"   Email: {email}")
    print(f"   Username: {username}")
    print(f"   OTP Code: {otp_code}")
    print("=" * 60 + "\n")
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


def check_otp(user_id, otp_code):  # RENAMED from verify_otp to avoid conflict
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