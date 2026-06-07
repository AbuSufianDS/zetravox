import random
from datetime import datetime, timedelta, timezone
from flask import current_app
from app import db
from app.models import PasswordResetOTP, User


def generate_otp():
    """Generate a 6-digit OTP"""
    return ''.join([str(random.randint(0, 9)) for _ in range(6)])


def send_otp_email(email, otp_code, username):
    """Print OTP to console/logs (no real email)"""

    # Print OTP to console - this will appear in Render logs
    print("\n" + "=" * 60)
    print("🔐 PASSWORD RESET OTP")
    print("=" * 60)
    print(f"   Email: {email}")
    print(f"   Username: {username}")
    print(f"   OTP Code: {otp_code}")
    print("=" * 60)
    print("   Use this code to verify your identity")
    print("=" * 60 + "\n")

    # Return True to indicate success (for testing)
    return True


def create_password_reset_otp(user_id):
    """Create and store OTP for user"""
    # Delete any existing unused OTPs for this user
    PasswordResetOTP.query.filter_by(
        user_id=user_id,
        is_used=False
    ).delete()

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

    # Also print OTP here for safety
    print(f"✅ OTP created for user {user_id}: {otp_code}")

    return otp_code


def verify_otp(user_id, otp_code):
    """Verify OTP code"""
    otp_record = PasswordResetOTP.query.filter_by(
        user_id=user_id,
        otp_code=otp_code,
        is_used=False
    ).first()

    if otp_record and otp_record.expires_at > datetime.now(timezone.utc):
        otp_record.is_used = True
        db.session.commit()
        print(f"✅ OTP verified for user {user_id}")
        return True
    else:
        print(f"❌ Invalid or expired OTP for user {user_id}")
        return False