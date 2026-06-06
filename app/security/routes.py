from flask import render_template, flash, redirect, url_for, request, jsonify, abort, session, make_response
from flask_login import login_required, current_user
from datetime import datetime
from app import db
from app.security import bp
from app.security.two_factor_auth import TwoFactorAuth
from app.models import User, LoginHistory, SecurityEvent, UserSession, DataDeletionRequest, BlockedUser, HiddenPost, NotInterestedPost, InterestedPost
import pyotp


@bp.route('/appearance')
@login_required
def appearance_settings():
    return render_template('security/appearance.html', title='Appearance Settings')


@bp.route('/notifications')
@login_required
def notification_settings():
    return render_template('security/notifications.html', title='Notification Settings')


@bp.route('/screen-protection')
@login_required
def screen_protection():
    return render_template('security/screen_protection.html', title='Screen Protection')


@bp.route('/set-theme', methods=['POST'])
@login_required
def set_theme():
    theme = request.json.get('theme', 'light')
    if theme in ['light', 'dark', 'system']:
        session['theme'] = theme
        return jsonify({'success': True, 'theme': theme})
    return jsonify({'success': False}), 400


@bp.route('/blocked-users')
@login_required
def blocked_users():
    blocked_list = BlockedUser.query.filter_by(blocker_id=current_user.id).all()
    blocked_users = []
    for b in blocked_list:
        user = db.session.get(User, b.blocked_id)
        if user:
            blocked_users.append(user)
    return render_template('security/blocked_users.html', title='Blocked Users', blocked_users=blocked_users)


@bp.route('/unblock/<int:user_id>', methods=['POST'])
@login_required
def unblock(user_id):
    user_to_unblock = db.session.get(User, user_id)
    if not user_to_unblock:
        flash('User not found', 'danger')
        return redirect(url_for('security.blocked_users'))

    blocked = BlockedUser.query.filter_by(blocker_id=current_user.id, blocked_id=user_id).first()
    if blocked:
        db.session.delete(blocked)
        db.session.commit()
        SecurityEvent.log(current_user.id, 'user_unblocked', request.remote_addr,
                          f'Unblocked user {user_to_unblock.username}')
        flash(f'You have unblocked {user_to_unblock.username}', 'success')

    return redirect(url_for('security.blocked_users'))


@bp.route('/set-notification-preference', methods=['POST'])
@login_required
def set_notification_preference():
    data = request.json
    notification_type = data.get('type')
    enabled = data.get('enabled', False)

    if notification_type == 'email_likes':
        current_user.notify_email_likes = enabled
    elif notification_type == 'email_comments':
        current_user.notify_email_comments = enabled
    elif notification_type == 'email_follows':
        current_user.notify_email_follows = enabled
    elif notification_type == 'push_likes':
        current_user.notify_push_likes = enabled
    elif notification_type == 'push_comments':
        current_user.notify_push_comments = enabled
    elif notification_type == 'push_follows':
        current_user.notify_push_follows = enabled

    db.session.commit()
    return jsonify({'success': True})


@bp.route('/settings')
@login_required
def settings():
    return render_template('security/settings.html', title='Settings')


@bp.route('/account')
@login_required
def account_settings():
    return render_template('security/account.html', title='Account Settings')


@bp.route('/security')
@login_required
def security_settings():
    security_events = SecurityEvent.query.filter_by(user_id=current_user.id).order_by(SecurityEvent.timestamp.desc()).limit(5).all()
    return render_template('security/security.html', title='Security Settings', security_events=security_events)


@bp.route('/privacy')
@login_required
def privacy_settings():
    return render_template('security/privacy.html', title='Privacy Settings')


@bp.route('/sessions')
@login_required
def session_management():
    sessions = UserSession.query.filter_by(user_id=current_user.id, is_active=True).all()
    return render_template('security/sessions.html', title='Active Sessions', sessions=sessions)


@bp.route('/revoke-session/<session_id>', methods=['POST'])
@login_required
def revoke_session(session_id):
    session_obj = UserSession.query.filter_by(id=session_id, user_id=current_user.id).first()
    if session_obj:
        session_obj.is_active = False
        db.session.commit()
        flash('Session revoked successfully', 'success')
    return redirect(url_for('security.session_management'))


@bp.route('/enable-2fa', methods=['GET', 'POST'])
@login_required
def enable_2fa():
    if request.method == 'POST':
        otp_code = request.form.get('otp_code')
        if TwoFactorAuth.verify_otp(current_user.otp_secret, otp_code):
            current_user.enable_2fa()
            backup_codes = TwoFactorAuth.generate_backup_codes()
            current_user.backup_codes = ','.join(backup_codes)
            db.session.commit()
            flash('Two-factor authentication enabled successfully', 'success')
            return render_template('security/backup_codes.html', backup_codes=backup_codes)
        flash('Invalid verification code', 'danger')

    if not current_user.otp_secret:
        current_user.otp_secret = TwoFactorAuth.generate_secret()
        db.session.commit()

    qr_code = TwoFactorAuth.generate_qr_code(current_user.otp_secret, current_user.email)
    return render_template('security/enable_2fa.html', qr_code=qr_code, secret=current_user.otp_secret)


@bp.route('/disable-2fa', methods=['POST'])
@login_required
def disable_2fa():
    otp_code = request.form.get('otp_code')
    if TwoFactorAuth.verify_otp(current_user.otp_secret, otp_code):
        current_user.two_factor_enabled = False
        current_user.backup_codes = None
        db.session.commit()
        flash('Two-factor authentication disabled', 'warning')
    else:
        flash('Invalid verification code', 'danger')
    return redirect(url_for('security.security_settings'))


@bp.route('/change-password', methods=['GET', 'POST'])
@login_required
def change_password():
    if request.method == 'POST':
        current_password = request.form.get('current_password')
        new_password = request.form.get('new_password')
        confirm_password = request.form.get('confirm_password')

        if not current_user.check_password(current_password):
            flash('Current password is incorrect', 'danger')
        elif new_password != confirm_password:
            flash('New passwords do not match', 'danger')
        elif len(new_password) < 8:
            flash('Password must be at least 8 characters', 'danger')
        else:
            current_user.set_password(new_password)
            db.session.commit()
            SecurityEvent.log(current_user.id, 'password_changed', request.remote_addr, "Password changed")
            flash('Password changed successfully', 'success')
            return redirect(url_for('security.security_settings'))

    return render_template('security/change_password.html')


@bp.route('/login-history')
@login_required
def login_history():
    page = request.args.get('page', 1, type=int)
    history = LoginHistory.query.filter_by(user_id=current_user.id).order_by(LoginHistory.timestamp.desc()).paginate(
        page=page, per_page=20)
    return render_template('security/login_history.html', history=history)


@bp.route('/security-log')
@login_required
def security_log():
    if not current_user.is_admin:
        abort(403)
    page = request.args.get('page', 1, type=int)
    events = SecurityEvent.query.order_by(SecurityEvent.timestamp.desc()).paginate(page=page, per_page=50)
    return render_template('security/security_log.html', events=events)


@bp.route('/api/revoke-all-sessions', methods=['POST'])
@login_required
def revoke_all_sessions():
    UserSession.query.filter_by(user_id=current_user.id).update({'is_active': False})
    db.session.commit()
    flash('All other sessions have been revoked', 'success')
    return redirect(url_for('security.session_management'))


@bp.route('/export-data')
@login_required
def export_data():
    user_data = {
        'username': current_user.username,
        'email': current_user.email,
        'created_at': current_user.last_seen.isoformat() if current_user.last_seen else None,
        'profile': {
            'about_me': current_user.about_me,
            'work': current_user.work,
            'education': current_user.education,
            'location': current_user.location
        },
        'posts': [{'body': p.body, 'timestamp': p.timestamp.isoformat()} for p in current_user.posts.all()],
        'export_date': datetime.utcnow().isoformat()
    }
    response = jsonify(user_data)
    response.headers['Content-Disposition'] = f'attachment; filename=user_data_{current_user.id}.json'
    return response


@bp.route('/request-deletion', methods=['POST'])
@login_required
def request_deletion():
    existing = DataDeletionRequest.query.filter_by(user_id=current_user.id, status='pending').first()
    if existing:
        return jsonify({'message': 'Deletion request already pending'}), 400

    request_obj = DataDeletionRequest(
        user_id=current_user.id,
        request_ip=request.remote_addr
    )
    db.session.add(request_obj)
    db.session.commit()
    SecurityEvent.log(current_user.id, 'deletion_requested', request.remote_addr, "User requested account deletion")
    return jsonify({'message': 'Deletion request submitted', 'status': 'pending'})