import random
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta, timezone
from flask import current_app
from app import db
from app.models import PasswordResetOTP, User


def generate_otp():
    """Generate a 6-digit OTP"""
    return ''.join([str(random.randint(0, 9)) for _ in range(6)])


def send_otp_email(email, otp_code, username):
    """Send OTP to user's email"""
    try:
        subject = "Password Reset Request - ConnectHub"
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <style>
                body {{
                    font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                    background-color: #f4f4f4;
                    margin: 0;
                    padding: 0;
                }}
                .container {{
                    max-width: 500px;
                    margin: 50px auto;
                    background: white;
                    border-radius: 16px;
                    box-shadow: 0 10px 30px rgba(0,0,0,0.1);
                    overflow: hidden;
                }}
                .header {{
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    padding: 30px;
                    text-align: center;
                }}
                .header h1 {{
                    color: white;
                    margin: 0;
                    font-size: 24px;
                }}
                .content {{
                    padding: 30px;
                    text-align: center;
                }}
                .otp-code {{
                    font-size: 42px;
                    font-weight: bold;
                    letter-spacing: 8px;
                    color: #667eea;
                    background: #f0f2f5;
                    padding: 15px;
                    border-radius: 12px;
                    display: inline-block;
                    margin: 20px 0;
                    font-family: monospace;
                }}
                .button {{
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    color: white;
                    padding: 12px 30px;
                    text-decoration: none;
                    border-radius: 30px;
                    display: inline-block;
                    margin: 20px 0;
                }}
                .footer {{
                    padding: 20px;
                    text-align: center;
                    color: #888;
                    font-size: 12px;
                    border-top: 1px solid #eee;
                }}
                .warning {{
                    color: #e74c3c;
                    font-size: 12px;
                    margin-top: 20px;
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>🔐 ConnectHub</h1>
                    <p style="color: white; opacity: 0.9;">Password Reset Request</p>
                </div>
                <div class="content">
                    <p>Hello <strong>{username}</strong>,</p>
                    <p>We received a request to reset your password. Use the following OTP to continue:</p>

                    <div class="otp-code">{otp_code}</div>

                    <p>This OTP is valid for <strong>10 minutes</strong>.</p>
                    <p>If you didn't request this, please ignore this email.</p>

                    <div class="warning">
                        ⚠️ Never share this OTP with anyone.
                    </div>
                </div>
                <div class="footer">
                    <p>&copy; 2024 ConnectHub. All rights reserved.</p>
                    <p>This is an automated message, please do not reply.</p>
                </div>
            </div>
        </body>
        </html>
        """

        text_content = f"""Password Reset Request - ConnectHub

Hello {username},

We received a request to reset your password. Use the following OTP to continue:

OTP Code: {otp_code}

This OTP is valid for 10 minutes.

If you didn't request this, please ignore this email.

Never share this OTP with anyone.

© 2024 ConnectHub
        """

        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From'] = current_app.config['MAIL_USERNAME']
        msg['To'] = email

        part1 = MIMEText(text_content, 'plain')
        part2 = MIMEText(html_content, 'html')

        msg.attach(part1)
        msg.attach(part2)

        server = smtplib.SMTP(current_app.config['MAIL_SERVER'], current_app.config['MAIL_PORT'])
        server.starttls()
        server.login(current_app.config['MAIL_USERNAME'], current_app.config['MAIL_PASSWORD'])
        server.send_message(msg)
        server.quit()

        return True
    except Exception as e:
        print(f"Email error: {e}")
        return False


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

    return otp_code


def verify_otp(user_id, otp_code):
    """Verify OTP code"""
    otp_record = PasswordResetOTP.query.filter_by(
        user_id=user_id,
        otp_code=otp_code,
        is_used=False
    ).first()

    if otp_record and otp_record.is_valid():
        otp_record.is_used = True
        db.session.commit()
        return True
    return False