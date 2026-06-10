from urllib.parse import urlsplit
from flask_babel import _
from app.auth.email import send_password_reset_email
from app.models import LoginHistory, SecurityEvent, UserSession
import hashlib
from flask import render_template, flash, redirect, url_for, request, jsonify, session
from flask_login import current_user, login_user, logout_user, login_required
from datetime import datetime, timezone
import sqlalchemy as sa
from app import db
from app.auth import bp
from app.auth.forms import LoginForm, RegistrationForm, ResetPasswordRequestForm, ResetPasswordForm
from app.models import User
from app.otp_helper import create_password_reset_otp, send_otp_email, check_otp_code


@bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))

    form = LoginForm()
    if form.validate_on_submit():
        user = db.session.scalar(
            sa.select(User).where(User.username == form.username.data))

        if user and user.is_account_locked():
            flash('Account is temporarily locked. Please try again later.', 'danger')
            SecurityEvent.log(user.id, 'login_blocked_locked', request.remote_addr,
                              'Account locked due to too many failed attempts')
            return redirect(url_for('auth.login'))

        if user is None or not user.check_password(form.password.data):
            if user:
                user.increment_login_attempts()
                remaining = 5 - user.login_attempts
                flash(f'Invalid username or password. {remaining} attempts remaining.', 'danger')
                SecurityEvent.log(user.id, 'login_failed', request.remote_addr,
                                  f'Failed login attempt. {remaining} attempts remaining')
            else:
                flash('Invalid username or password.', 'danger')
            return redirect(url_for('auth.login'))

        user.reset_login_attempts()
        user.last_login_ip = request.remote_addr
        user.last_login_time = datetime.utcnow()

        if user.two_factor_enabled:
            session['2fa_user_id'] = user.id
            session['2fa_verified'] = False
            return redirect(url_for('auth.verify_2fa'))

        login_user(user, remember=form.remember_me.data)

        login_history = LoginHistory(
            user_id=user.id,
            ip_address=request.remote_addr,
            user_agent=request.headers.get('User-Agent', 'Unknown'),
            success=True
        )
        db.session.add(login_history)
        SecurityEvent.log(user.id, 'login_success', request.remote_addr, f'Successful login from {request.remote_addr}')
        db.session.commit()

        next_page = request.args.get('next')
        if not next_page or urlsplit(next_page).netloc != '':
            next_page = url_for('main.index')
        return redirect(next_page)

    return render_template('auth/login.html', title='Sign In', form=form)


@bp.route('/verify-2fa', methods=['GET', 'POST'])
def verify_2fa():
    if '2fa_user_id' not in session:
        return redirect(url_for('auth.login'))

    user = db.session.get(User, session['2fa_user_id'])
    if not user:
        return redirect(url_for('auth.login'))

    if request.method == 'POST':
        otp_code = request.form.get('otp_code')
        backup_code = request.form.get('backup_code')

        if backup_code:
            from app.security.two_factor_auth import TwoFactorAuth
            if TwoFactorAuth.verify_backup_code(user, backup_code):
                login_user(user)
                session.pop('2fa_user_id', None)
                session.pop('2fa_verified', None)
                db.session.commit()
                return redirect(url_for('main.index'))
            flash('Invalid backup code', 'danger')

        elif otp_code:
            import pyotp
            totp = pyotp.TOTP(user.otp_secret)
            if totp.verify(otp_code):
                login_user(user)
                session.pop('2fa_user_id', None)
                session.pop('2fa_verified', None)
                SecurityEvent.log(user.id, '2fa_verified', request.remote_addr, '2FA verification successful')
                db.session.commit()
                return redirect(url_for('main.index'))
            flash('Invalid verification code', 'danger')

    return render_template('auth/verify_2fa.html')


@bp.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('main.index'))


@bp.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
    form = RegistrationForm()
    if form.validate_on_submit():
        user = User(username=form.username.data, email=form.email.data)
        user.set_password(form.password.data)
        user.account_created_ip = request.remote_addr
        db.session.add(user)
        db.session.commit()
        flash(_('Congratulations, you are now a registered user!'))
        return redirect(url_for('auth.login'))
    return render_template('auth/register.html', title=_('Register'), form=form)


@bp.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))

    form = ResetPasswordRequestForm()

    if form.validate_on_submit():
        email = form.email.data
        user = User.query.filter_by(email=email).first()

        if user:
            otp_code = create_password_reset_otp(user.id)

            if send_otp_email(email, otp_code, user.username):
                session['reset_email'] = email
                session['reset_user_id'] = user.id
                flash('OTP sent to your email address. Please check your inbox.', 'success')
                return redirect(url_for('auth.verify_otp'))
            else:
                flash('Failed to send OTP. Please try again later.', 'danger')
        else:
            flash('No account found with this email address.', 'danger')

        return redirect(url_for('auth.forgot_password'))

    return render_template('auth/forgot_password.html', title='Forgot Password', form=form)


@bp.route('/verify-otp', methods=['GET', 'POST'])
def verify_otp():
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))

    if 'reset_email' not in session:
        flash('Please start the password reset process again.', 'warning')
        return redirect(url_for('auth.forgot_password'))

    if request.method == 'POST':
        otp_code = request.form.get('otp_code', '').strip()
        user_id = session.get('reset_user_id')

        if not user_id:
            flash('Session expired. Please try again.', 'danger')
            return redirect(url_for('auth.forgot_password'))

        if check_otp_code(user_id, otp_code):
            session['otp_verified'] = True
            flash('OTP verified! Please create your new password.', 'success')
            return redirect(url_for('auth.reset_password'))
        else:
            flash('Invalid or expired OTP. Please try again.', 'danger')

    return render_template('auth/verify_otp.html', title='Verify OTP', email=session.get('reset_email'))


@bp.route('/reset-password', methods=['GET', 'POST'])
def reset_password():
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))

    if not session.get('otp_verified'):
        flash('Please verify your OTP first.', 'warning')
        return redirect(url_for('auth.forgot_password'))

    user_id = session.get('reset_user_id')
    if not user_id:
        flash('Session expired. Please try again.', 'danger')
        return redirect(url_for('auth.forgot_password'))

    user = User.query.get(user_id)
    if not user:
        flash('User not found.', 'danger')
        return redirect(url_for('auth.forgot_password'))

    form = ResetPasswordForm()

    if form.validate_on_submit():
        user.set_password(form.password.data)
        db.session.commit()

        session.pop('reset_email', None)
        session.pop('reset_user_id', None)
        session.pop('otp_verified', None)

        flash('Your password has been reset successfully! Please login with your new password.', 'success')
        return redirect(url_for('auth.login'))

    return render_template('auth/reset_password_new.html', title='Reset Password', form=form)


@bp.route('/resend-otp', methods=['POST'])
def resend_otp():
    try:
        email = session.get('reset_email')
        if not email:
            return jsonify({'success': False, 'error': 'Session expired'})

        user = User.query.filter_by(email=email).first()
        if not user:
            return jsonify({'success': False, 'error': 'User not found'})

        otp_code = create_password_reset_otp(user.id)

        if send_otp_email(email, otp_code, user.username):
            return jsonify({'success': True})
        else:
            return jsonify({'success': False, 'error': 'Failed to send email'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})
