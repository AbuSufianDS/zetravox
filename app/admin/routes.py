from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app, jsonify
from flask_login import login_required, current_user
from app.models import User, Post, Comment, SpamReport, db, Feedback, HelpRequest,VIPUser
from functools import wraps
from datetime import datetime

bp = Blueprint('admin', __name__, url_prefix='/admin')


def admin_required(f):

    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            flash('Access denied. Admin privileges required.', 'danger')
            return redirect(url_for('main.index'))
        return f(*args, **kwargs)

    return decorated_function

@bp.route('/moderation')
@login_required
@admin_required
def moderation():
    page = request.args.get('page', 1, type=int)
    posts = Post.query.filter_by(is_spam=False, is_deleted=False).order_by(Post.timestamp.desc()).paginate(page=page,
                                                                                                           per_page=20)
    return render_template('admin/moderation.html', posts=posts)


@bp.route('/reports')
@login_required
@admin_required
def reports():
    page = request.args.get('page', 1, type=int)
    reports = SpamReport.query.order_by(SpamReport.created_at.desc()).paginate(page=page, per_page=20)
    return render_template('admin/reports.html', reports=reports)


@bp.route('/analytics')
@login_required
@admin_required
def analytics():
    return render_template('admin/report_dashboard.html')


@bp.route('/flagged')
@login_required
@admin_required
def flagged():
    page = request.args.get('page', 1, type=int)
    posts = Post.query.filter_by(is_spam=True).order_by(Post.timestamp.desc()).paginate(page=page, per_page=20)
    return render_template('admin/flagged.html', posts=posts)


@bp.route('/moderate/<int:post_id>', methods=['POST'])
@login_required
@admin_required
def moderate_post(post_id):
    post = Post.query.get_or_404(post_id)
    action = request.form.get('action')

    if action == 'approve':
        post.is_spam = False
        flash('Post approved.', 'success')
    elif action == 'reject':
        post.is_spam = True
        post.is_deleted = True
        flash('Post rejected and deleted.', 'warning')

    db.session.commit()
    return redirect(url_for('admin.moderation'))


@bp.route('/resolve-report/<int:report_id>', methods=['POST'])
@login_required
@admin_required
def resolve_report(report_id):
    report = SpamReport.query.get_or_404(report_id)
    report.status = 'resolved'
    report.resolved_by = current_user.id
    report.resolved_at = datetime.utcnow()
    db.session.commit()
    flash('Report resolved.', 'success')
    return redirect(url_for('admin.reports'))


@bp.route('/verification-requests')
@login_required
@admin_required
def verification_requests():
    pending_users = User.query.filter_by(verification_status='pending').order_by(User.verification_requested_at).all()
    return render_template('admin/verification_requests.html', pending_users=pending_users)


@bp.route('/verify-user/<int:user_id>', methods=['POST'])
@login_required
@admin_required
def verify_user(user_id):

    user = User.query.get_or_404(user_id)
    action = request.form.get('action')
    notes = request.form.get('notes', '')

    if action == 'approve':
        user.is_human_verified = True
        user.verification_status = 'approved'
        user.verified_at = datetime.utcnow()
        user.verification_notes = notes

        from app.notification_helper import create_notification
        create_notification(
            user_id=user.id,
            actor_id=current_user.id,
            notification_type='system',
            message='Your human verification has been approved! You now have the Human-First badge.',
            link=url_for('main.profile', username=user.username)
        )

        flash(f'User {user.username} has been verified as human.', 'success')

    elif action == 'reject':
        user.verification_status = 'rejected'
        user.verification_notes = notes

        from app.notification_helper import create_notification
        create_notification(
            user_id=user.id,
            actor_id=current_user.id,
            notification_type='system',
            message=f'Your human verification request was rejected. Reason: {notes or "No reason provided."}',
            link=url_for('main.profile', username=user.username)
        )

        flash(f'User {user.username} verification request rejected.', 'warning')

    db.session.commit()
    return redirect(url_for('admin.verification_requests'))


@bp.route('/feedback')
@login_required
@admin_required
def feedback_dashboard():
    feedbacks = Feedback.query.order_by(Feedback.created_at.desc()).all()
    total = Feedback.query.count()
    pending = Feedback.query.filter_by(status='pending').count()
    resolved = Feedback.query.filter_by(status='resolved').count()

    # Calculate average rating
    from sqlalchemy import func
    avg = db.session.query(func.avg(Feedback.rating)).scalar()
    avg_rating = round(avg, 1) if avg else 0

    return render_template('admin/feedback.html',
                           feedbacks=feedbacks,
                           total=total,
                           pending=pending,
                           resolved=resolved,
                           avg_rating=avg_rating)


@bp.route('/feedback/respond/<int:feedback_id>', methods=['POST'])
@login_required
@admin_required
def respond_feedback(feedback_id):
    feedback = Feedback.query.get_or_404(feedback_id)
    action = request.form.get('action')
    response = request.form.get('response', '').strip()

    from app.notification_helper import create_notification

    if action == 'resolve':
        feedback.status = 'resolved'
        feedback.admin_response = response

        create_notification(
            recipient_id=feedback.user_id,
            actor_id=current_user.id,
            notification_type='system',
            message=f' Thank you for your feedback! It has been resolved.\nResponse: {response[:100]}{"..." if len(response) > 100 else ""}',
            link=url_for('main.feedback')
        )
        flash('Feedback resolved and user notified.', 'success')

    elif action == 'reject':
        feedback.status = 'rejected'
        feedback.admin_response = response or 'No action taken.'

        create_notification(
            recipient_id=feedback.user_id,
            actor_id=current_user.id,
            notification_type='system',
            message=f' Your feedback was reviewed but not implemented.\nReason: {response[:100]}{"..." if len(response) > 100 else ""}',
            link=url_for('main.feedback')
        )
        flash('Feedback rejected and user notified.', 'warning')

    feedback.updated_at = datetime.utcnow()
    db.session.commit()
    return redirect(url_for('admin.feedback_dashboard'))


@bp.route('/help')
@login_required
@admin_required
def help_dashboard():
    help_requests = HelpRequest.query.order_by(
        HelpRequest.priority.desc(),
        HelpRequest.created_at.desc()
    ).all()

    total = HelpRequest.query.count()
    pending = HelpRequest.query.filter_by(status='pending').count()
    in_progress = HelpRequest.query.filter_by(status='in_progress').count()
    resolved = HelpRequest.query.filter_by(status='resolved').count()

    return render_template('admin/help.html',
                           help_requests=help_requests,
                           total=total,
                           pending=pending,
                           in_progress=in_progress,
                           resolved=resolved)


@bp.route('/help/respond/<int:help_id>', methods=['POST'])
@login_required
@admin_required
def respond_help(help_id):
    help_request = HelpRequest.query.get_or_404(help_id)
    action = request.form.get('action')
    response = request.form.get('response', '').strip()

    from app.notification_helper import create_notification

    if action == 'resolve':
        help_request.status = 'resolved'
        help_request.resolved_at = datetime.utcnow()
        help_request.admin_response = response

        # Send notification to user
        create_notification(
            recipient_id=help_request.user_id,
            actor_id=current_user.id,
            notification_type='system',
            message=f'✅ Your help request "{help_request.subject}" has been resolved.\nResponse: {response[:100]}{"..." if len(response) > 100 else ""}',
            link=url_for('main.help')
        )
        flash('Help request resolved and user notified.', 'success')

    elif action == 'in_progress':
        help_request.status = 'in_progress'
        help_request.admin_response = response

        create_notification(
            recipient_id=help_request.user_id,
            actor_id=current_user.id,
            notification_type='system',
            message=f'🔄 Your help request "{help_request.subject}" is now in progress.\n{response[:100]}{"..." if len(response) > 100 else ""}',
            link=url_for('main.help')
        )
        flash('Help request marked as in progress and user notified.', 'info')

    elif action == 'reject':
        help_request.status = 'rejected'
        help_request.admin_response = response or 'No action taken.'

        create_notification(
            recipient_id=help_request.user_id,
            actor_id=current_user.id,
            notification_type='system',
            message=f'❌ Your help request "{help_request.subject}" was rejected.\nReason: {response[:100]}{"..." if len(response) > 100 else ""}',
            link=url_for('main.help')
        )
        flash('Help request rejected and user notified.', 'warning')

    db.session.commit()
    return redirect(url_for('admin.help_dashboard'))


# ========== VIP PAYMENT VERIFICATION ==========

@bp.route('/vip-verification')
@login_required
@admin_required
def vip_verification():
    """Admin VIP payment verification dashboard"""
    # Get all VIP verification requests
    # These are users who have submitted transaction IDs but not yet verified
    pending_requests = VIPUser.query.filter_by(is_active=False).all()

    # Count stats
    total = VIPUser.query.count()
    pending = VIPUser.query.filter_by(is_active=False).count()
    verified = VIPUser.query.filter_by(is_active=True).count()

    # Create request objects for display
    requests = []
    for vip in pending_requests:
        requests.append({
            'id': vip.id,
            'user': vip.user,
            'plan': vip.vip_level,
            'transaction_id': vip.payment_id or 'N/A',
            'payment_method': vip.payment_method or 'unknown',
            'amount': '18' if vip.vip_level == 'premium' else '38' if vip.vip_level == 'elite' else '68',
            'status': 'pending' if vip.is_active == False else 'verified',
            'created_at': vip.started_at
        })

    return render_template('admin/vip_verification.html',
                           requests=requests,
                           total=total,
                           pending=pending,
                           verified=verified)


@bp.route('/verify-vip/<int:request_id>', methods=['POST'])
@login_required
@admin_required
def verify_vip_payment(request_id):
    """Verify VIP payment and upgrade user"""
    vip = VIPUser.query.get_or_404(request_id)
    action = request.form.get('action')

    if action == 'approve':
        # Upgrade to VIP
        vip.is_active = True
        vip.started_at = datetime.utcnow()

        # Auto-verify human badge
        user = vip.user
        user.is_human_verified = True
        user.verification_status = 'approved'
        user.verified_at = datetime.utcnow()

        db.session.commit()

        # Send notification
        from app.notification_helper import create_notification
        create_notification(
            user_id=user.id,
            actor_id=current_user.id,
            notification_type='system',
            message=f'🎉 Your VIP {vip.vip_level.capitalize()} membership has been activated!',
            link=url_for('main.vip')
        )

        flash(f' VIP {vip.vip_level.capitalize()} activated for {user.username}', 'success')

    elif action == 'reject':
        # Reject and delete request
        db.session.delete(vip)
        db.session.commit()
        flash(f' VIP request rejected for {vip.user.username}', 'warning')

    return redirect(url_for('admin.vip_verification'))