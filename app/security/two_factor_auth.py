import pyotp
import qrcode
from io import BytesIO
import base64
import secrets
from app import db


class TwoFactorAuth:
    @staticmethod
    def generate_secret():
        return pyotp.random_base32()

    @staticmethod
    def get_totp_uri(secret, email):
        return pyotp.totp.TOTP(secret).provisioning_uri(
            name=email,
            issuer_name="TinyBook"
        )

    @staticmethod
    def generate_qr_code(secret, email):
        uri = TwoFactorAuth.get_totp_uri(secret, email)
        qr = qrcode.QRCode(version=1, box_size=10, border=4)
        qr.add_data(uri)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        buffered = BytesIO()
        img.save(buffered, format="PNG")
        return base64.b64encode(buffered.getvalue()).decode()

    @staticmethod
    def verify_otp(secret, otp_code):
        totp = pyotp.TOTP(secret)
        return totp.verify(otp_code)

    @staticmethod
    def generate_backup_codes(count=10):
        return [secrets.token_hex(4) for _ in range(count)]

    @staticmethod
    def verify_backup_code(user, code):
        if not user.backup_codes:
            return False
        codes = user.backup_codes.split(',')
        if code in codes:
            codes.remove(code)
            user.backup_codes = ','.join(codes)
            db.session.commit()
            return True
        return False