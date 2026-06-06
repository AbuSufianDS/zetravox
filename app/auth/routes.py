from flask import render_template, redirect, url_for, flash, request, session
from urllib.parse import urlsplit
from datetime import datetime
from flask_login import login_user, logout_user, current_user
from flask_babel import _
import sqlalchemy as sa
from app import db
from app.auth import bp
from app.auth.forms import LoginForm, RegistrationForm, \
    ResetPasswordRequestForm, ResetPasswordForm
from app.models import User
from app.auth.email import send_password_reset_email
from app.models import LoginHistory, SecurityEvent, UserSession
import hashlib


@bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))

    form = LoginForm()
    if form.validate_on_submit():
        user = db.session.scalar(
            sa.select(User).where(User.username == form.username.data))

        # Check if account is locked
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

        # Successful login
        user.reset_login_attempts()
        user.last_login_ip = request.remote_addr
        user.last_login_time = datetime.utcnow()

        # Check if 2FA is enabled
        if user.two_factor_enabled:
            session['2fa_user_id'] = user.id
            session['2fa_verified'] = False
            return redirect(url_for('auth.verify_2fa'))

        login_user(user, remember=form.remember_me.data)

        # Log successful login
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
    return render_template('auth/register.html', title=_('Register'),
                           form=form)


@bp.route('/reset_password_request', methods=['GET', 'POST'])
def reset_password_request():
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
    form = ResetPasswordRequestForm()
    if form.validate_on_submit():
        user = db.session.scalar(
            sa.select(User).where(User.email == form.email.data))
        if user:
            send_password_reset_email(user)
        flash(
            _('Check your email for the instructions to reset your password'))
        return redirect(url_for('auth.login'))
    return render_template('auth/reset_password_request.html',
                           title=_('Reset Password'), form=form)


@bp.route('/reset_password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
    user = User.verify_reset_password_token(token)
    if not user:
        return redirect(url_for('main.index'))
    form = ResetPasswordForm()
    if form.validate_on_submit():
        user.set_password(form.password.data)
        db.session.commit()
        flash(_('Your password has been reset.'))
        return redirect(url_for('auth.login'))
    return render_template('auth/reset_password.html', form=form)