from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app, jsonify
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
import os
from app.models import db
import uuid
from datetime import datetime

human_verification_bp = Blueprint('human_verification', __name__, url_prefix='/human-verification')


@human_verification_bp.route('/request', methods=['GET', 'POST'])
@login_required
def request_verification():
    if current_user.is_human_verified:
        flash('You are already verified as a human.', 'info')
        return redirect(url_for('main.user', username=current_user.username))

    if current_user.verification_status == 'pending':
        flash('Your verification request is pending review.', 'info')
        return redirect(url_for('main.profile', username=current_user.username))

    if request.method == 'POST':
        from flask_wtf.csrf import validate_csrf
        try:
            validate_csrf(request.form.get('csrf_token'))
        except:
            flash('CSRF token missing or invalid. Please try again.', 'danger')
            return redirect(request.url)

        if 'verification_video' not in request.files:
            flash('Please upload a verification video.', 'danger')
            return redirect(request.url)

        video_file = request.files['verification_video']
        if video_file.filename == '':
            flash('Please select a video file.', 'danger')
            return redirect(request.url)

        allowed_extensions = {'mp4', 'webm', 'mov', 'avi', 'mkv'}
        if '.' not in video_file.filename or video_file.filename.rsplit('.', 1)[1].lower() not in allowed_extensions:
            flash('Please upload a valid video file (MP4, WebM, MOV, AVI, MKV).', 'danger')
            return redirect(request.url)

        video_file.seek(0, os.SEEK_END)
        file_size = video_file.tell()
        video_file.seek(0)

        if file_size > 20 * 1024 * 1024:
            flash('Video file size cannot exceed 20MB.', 'danger')
            return redirect(request.url)
        filename = secure_filename(f"{uuid.uuid4().hex}_{video_file.filename}")
        upload_folder = current_app.config.get('UPLOAD_FOLDER', 'app/static/uploads/verification')
        os.makedirs(upload_folder, exist_ok=True)

        filepath = os.path.join(upload_folder, filename)
        video_file.save(filepath)

        current_user.verification_video = f'uploads/verification/{filename}'
        current_user.verification_status = 'pending'
        current_user.verification_requested_at = datetime.utcnow()
        db.session.commit()

        flash('Your verification request has been submitted. Please wait for admin review.', 'success')
        return redirect(url_for('main.profile', username=current_user.username))

    return render_template('human_verification/request.html')


@human_verification_bp.route('/status')
@login_required
def verification_status():
    return jsonify({
        'is_verified': current_user.is_human_verified,
        'status': current_user.verification_status,
        'requested_at': current_user.verification_requested_at.isoformat() if current_user.verification_requested_at else None,
        'verified_at': current_user.verified_at.isoformat() if current_user.verified_at else None
    })