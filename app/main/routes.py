from datetime import datetime, timezone, timedelta
from flask import render_template, flash, redirect, url_for, request, g, current_app, abort, jsonify
from flask_login import current_user, login_required
from flask_babel import _, get_locale
import sqlalchemy as sa
import re
from langdetect import detect, LangDetectException
from app import db
from app.main.forms import EditProfileForm, EmptyForm, PostForm, SearchForm, MessageForm, CommentForm, ReportForm, \
    StoryForm
from app.models import User, Post, Message, Notification, Like, Comment, SpamReport, UserActivity, Hashtag, PostHashtag, \
    SavedPost, SharedPost, BlockedUser, PostReaction, Story, StoryView, ChatMessage
from app.translate import translate
from app.main import bp
from spam_service.integration import spam_checker
from functools import wraps
from app.media_helpers import save_media, delete_media
from app.profile_helpers import save_profile_picture, delete_profile_picture
from app.notification_helper import send_like_notification
from app.notification_helper import send_comment_notification
from app.notification_helper import send_like_notification, send_comment_notification, send_follow_notification, send_share_notification
from app.services.recommendation_service import recommendation_engine
from app.services.report_service import report_service
from flask import send_file


def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            abort(403)
        return f(*args, **kwargs)
    return decorated_function

@bp.route('/admin/reports/csv/users')
@login_required
@admin_required
def download_users_report():
    filepath, filename = report_service.generate_users_report()
    return send_file(
        filepath,
        as_attachment=True,
        download_name=filename,
        mimetype='text/csv'
    )

@bp.route('/admin/reports/csv/posts')
@login_required
@admin_required
def download_posts_report():
    filepath, filename = report_service.generate_posts_report()
    return send_file(
        filepath,
        as_attachment=True,
        download_name=filename,
        mimetype='text/csv'
    )

@bp.route('/admin/reports/csv/reports')
@login_required
@admin_required
def download_reports_summary():
    filepath, filename = report_service.generate_reports_summary()
    return send_file(
        filepath,
        as_attachment=True,
        download_name=filename,
        mimetype='text/csv'
    )

@bp.route('/admin/reports/csv/engagement')
@login_required
@admin_required
def download_engagement_report():
    filepath, filename = report_service.generate_engagement_report()
    return send_file(
        filepath,
        as_attachment=True,
        download_name=filename,
        mimetype='text/csv'
    )

@bp.route('/admin/reports')
@login_required
@admin_required
def report_dashboard():
    reports = report_service.get_all_reports()
    return render_template('admin/report_dashboard.html', title='Reports', reports=reports)

@bp.route('/admin/reports')
@login_required
@admin_required
def view_reports():
    page = request.args.get('page', 1, type=int)

    reports = db.session.query(SpamReport).filter(
        SpamReport.reviewed == False
    ).order_by(SpamReport.timestamp.desc()).paginate(
        page=page, per_page=20, error_out=False
    )

    return render_template('admin/reports.html',
                           title='User Reports',
                           reports=reports)
@bp.route('/admin/dismiss_report/<int:report_id>', methods=['POST'])
@login_required
@admin_required
def dismiss_report(report_id):
    report = db.session.get(SpamReport, report_id)
    if report:
        report.reviewed = True
        db.session.commit()
        flash('Report dismissed.', 'success')
    return redirect(url_for('main.view_reports'))
@bp.route('/for-you')
@login_required
def for_you():
    page = request.args.get('page', 1, type=int)
    limit = current_app.config.get('POSTS_PER_PAGE', 25)

    from app.services.recommendation_service import recommendation_engine

    recommended_post_ids = recommendation_engine.get_personalized_feed(current_user.id, limit=100)

    if not recommended_post_ids:
        query = sa.select(Post).where(
            Post.privacy == 'public',
            Post.scheduled_for == None
        ).order_by(Post.timestamp.desc())
        pagination = db.paginate(query, page=page, per_page=limit, error_out=False)
        posts = pagination.items
        next_url = url_for('main.for_you', page=page + 1) if pagination.has_next else None
        prev_url = url_for('main.for_you', page=page - 1) if pagination.has_prev else None
        is_personalized = False
    else:
        order = {post_id: idx for idx, post_id in enumerate(recommended_post_ids)}
        query = sa.select(Post).where(Post.id.in_(recommended_post_ids))
        posts_list = db.session.scalars(query).all()
        posts_list.sort(key=lambda p: order.get(p.id, 999))

        start = (page - 1) * limit
        end = start + limit
        posts = posts_list[start:end]

        next_url = url_for('main.for_you', page=page + 1) if len(posts) == limit else None
        prev_url = url_for('main.for_you', page=page - 1) if page > 1 else None
        is_personalized = True

    return render_template('for_you.html',
                           title='For You',
                           posts=posts,
                           is_personalized=is_personalized,
                           next_url=next_url,
                           prev_url=prev_url)


@bp.route('/discover')
@login_required
def discover():
    page = request.args.get('page', 1, type=int)
    limit = current_app.config.get('POSTS_PER_PAGE', 25)

    following = db.session.query(User.following).filter(User.id == current_user.id).first()
    following_ids = [f.id for f in following[0]] if following and following[0] else []
    following_ids.append(current_user.id)

    query = sa.select(Post).where(
        Post.user_id.notin_(following_ids),
        Post.privacy == 'public',
        Post.scheduled_for == None
    ).order_by(Post.timestamp.desc())

    pagination = db.paginate(query, page=page, per_page=limit, error_out=False)
    posts = pagination.items

    suggested = db.session.query(User).filter(
        User.id.notin_(following_ids)
    ).limit(10).all()

    next_url = url_for('main.discover', page=page + 1) if pagination.has_next else None
    prev_url = url_for('main.discover', page=page - 1) if pagination.has_prev else None

    return render_template('discover.html',
                           title='Discover',
                           posts=posts,
                           suggested_users=suggested,
                           next_url=next_url,
                           prev_url=prev_url)


@bp.route('/trending')
@login_required
def trending_feed():
    page = request.args.get('page', 1, type=int)
    limit = current_app.config.get('POSTS_PER_PAGE', 25)

    from datetime import datetime, timedelta
    week_ago = datetime.now(timezone.utc) - timedelta(days=7)

    query = sa.select(Post).where(
        Post.timestamp > week_ago,
        Post.privacy == 'public',
        Post.scheduled_for == None
    ).order_by(Post.timestamp.desc())

    pagination = db.paginate(query, page=page, per_page=limit, error_out=False)
    posts = pagination.items

    next_url = url_for('main.trending_feed', page=page + 1) if pagination.has_next else None
    prev_url = url_for('main.trending_feed', page=page - 1) if pagination.has_prev else None

    return render_template('trending_feed.html',
                           title='Trending',
                           posts=posts,
                           next_url=next_url,
                           prev_url=prev_url)


@bp.route('/following')
@login_required
def following_feed():
    page = request.args.get('page', 1, type=int)
    limit = current_app.config.get('POSTS_PER_PAGE', 25)

    pagination = db.paginate(current_user.following_posts(), page=page,
                             per_page=limit, error_out=False)
    posts = pagination.items

    next_url = url_for('main.following_feed', page=page + 1) if pagination.has_next else None
    prev_url = url_for('main.following_feed', page=page - 1) if pagination.has_prev else None

    return render_template('following_feed.html',
                           title='Following',
                           posts=posts,
                           next_url=next_url,
                           prev_url=prev_url)

@bp.route('/api/recommendations/feed')
@login_required
def recommended_feed():
    page = request.args.get('page', 1, type=int)
    limit = current_app.config.get('POSTS_PER_PAGE', 25)
    recommended_post_ids = recommendation_engine.get_personalized_feed(
        current_user.id,
        limit=100
    )

    if not recommended_post_ids:
        posts = db.paginate(current_user.following_posts(), page=page, per_page=limit)
    else:
        order = {post_id: idx for idx, post_id in enumerate(recommended_post_ids)}
        query = sa.select(Post).where(Post.id.in_(recommended_post_ids))
        posts_list = db.session.scalars(query).all()
        posts_list.sort(key=lambda p: order.get(p.id, 999))
        start = (page - 1) * limit
        end = start + limit
        posts = posts_list[start:end]

    return render_template('recommended_feed.html',
                           title='For You',
                           posts=posts,
                           recommendation=True)


@bp.route('/api/recommendations/users')
@login_required
def recommended_users():
    recommended_user_ids = recommendation_engine.get_user_recommendations(current_user.id, limit=20)
    users = db.session.get(User, recommended_user_ids) if recommended_user_ids else []

    return render_template('suggested_users.html',
                           title='Suggested Users',
                           users=users)

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            abort(403)
        return f(*args, **kwargs)

    return decorated_function


@bp.before_app_request
def before_request():
    if current_user.is_authenticated:
        current_user.last_seen = datetime.now(timezone.utc)
        current_user.last_active = datetime.now(timezone.utc)  # Add this line
        db.session.commit()
        g.search_form = SearchForm()
    g.locale = str(get_locale())


@bp.route('/', methods=['GET', 'POST'])
@bp.route('/index', methods=['GET', 'POST'])
@login_required
def index():
    form = PostForm()
    comment_form = CommentForm()
    story_form = StoryForm()

    if story_form.validate_on_submit() and story_form.media.data:
        media_filename, media_type = save_media(story_form.media.data, 'stories')
        if media_filename:
            from datetime import timedelta
            story = Story(
                user_id=current_user.id,
                media_url=media_filename,
                media_type=media_type,
                caption=story_form.caption.data,
                timestamp=datetime.now(timezone.utc),
                expires_at=datetime.now(timezone.utc) + timedelta(hours=24)
            )
            db.session.add(story)
            db.session.commit()
            flash('Story added! It will disappear in 24 hours.', 'success')
        return redirect(url_for('main.index'))

    if form.validate_on_submit():
        media_filename = None
        media_type = None

        if form.media.data and form.media.data.filename:
            media_filename, media_type = save_media(form.media.data)

        is_spam, spam_confidence, should_warn = spam_checker.check_post(form.post.data)

        profanity_words = []
        has_profanity = any(word in form.post.data.lower() for word in profanity_words)

        try:
            language = detect(form.post.data)
        except LangDetectException:
            language = ''

        scheduled_for = None
        if form.schedule_date.data:
            scheduled_for = form.schedule_date.data.replace(tzinfo=timezone.utc)

        post = Post(
            body=form.post.data,
            author=current_user,
            language=language,
            is_spam=is_spam or has_profanity,
            spam_confidence=spam_confidence,
            reviewed=False,
            approved=not should_warn and not has_profanity,
            media_url=media_filename,
            media_type=media_type,
            privacy=form.privacy.data,
            scheduled_for=scheduled_for
        )
        db.session.add(post)
        db.session.commit()

        hashtags = re.findall(r'#(\w+)', post.body)
        for tag_name in hashtags:
            hashtag = db.session.scalar(sa.select(Hashtag).where(Hashtag.name == tag_name.lower()))
            if not hashtag:
                hashtag = Hashtag(name=tag_name.lower())
                db.session.add(hashtag)
            post_hashtag = PostHashtag(post_id=post.id, hashtag_id=hashtag.id)
            db.session.add(post_hashtag)
            hashtag.post_count += 1

        db.session.commit()

        current_user.points += 10
        db.session.commit()

        if should_warn:
            flash('Warning: Your post has been flagged for review.', 'warning')
        else:
            flash('Your post is now live!', 'success')
        return redirect(url_for('main.index'))

    following_ids = [f.id for f in db.session.scalars(current_user.following.select())]
    following_ids.append(current_user.id)
    stories = db.session.scalars(
        sa.select(Story).where(
            Story.user_id.in_(following_ids),
            Story.expires_at > datetime.now(timezone.utc)
        ).order_by(Story.timestamp.desc())
    ).all()

    stories_by_user = {}
    for story in stories:
        if story.user_id not in stories_by_user:
            stories_by_user[story.user_id] = []
        stories_by_user[story.user_id].append(story)

    page = request.args.get('page', 1, type=int)
    posts = db.paginate(current_user.following_posts(), page=page,
                        per_page=current_app.config['POSTS_PER_PAGE'],
                        error_out=False)
    next_url = url_for('main.index', page=posts.next_num) if posts.has_next else None
    prev_url = url_for('main.index', page=posts.prev_num) if posts.has_prev else None

    return render_template('index.html', title='Home', form=form, comment_form=comment_form,
                           story_form=story_form, stories_by_user=stories_by_user,
                           posts=posts.items, next_url=next_url, prev_url=prev_url)


@bp.route('/edit_post/<int:post_id>', methods=['GET', 'POST'])
@login_required
def edit_post(post_id):
    post = db.session.get(Post, post_id)
    if post is None or post.author != current_user:
        abort(404)

    form = PostForm()
    if form.validate_on_submit():
        post.original_body = post.body
        post.body = form.post.data
        post.edited_at = datetime.now(timezone.utc)
        db.session.commit()
        flash('Post updated!', 'success')
        return redirect(url_for('main.index'))

    form.post.data = post.body
    return render_template('edit_post.html', title='Edit Post', form=form, post=post)

@bp.route('/notifications-page')
@login_required
def notifications_page():
    return render_template('notifications.html', title='Notifications')

@bp.route('/delete_post/<int:post_id>')
@login_required
def delete_post(post_id):
    post = db.session.get(Post, post_id)
    if post is None:
        flash('Post not found.')
        return redirect(url_for('main.index'))

    if post.author != current_user and not current_user.is_admin:
        flash('You cannot delete this post.')
        return redirect(url_for('main.index'))

    if post.media_url:
        delete_media(post.media_url)

    db.session.delete(post)
    db.session.commit()

    flash('Your post has been deleted.', 'info')
    return redirect(url_for('main.index'))


@bp.route('/pin_post/<int:post_id>')
@login_required
def pin_post(post_id):
    post = db.session.get(Post, post_id)
    if post is None or post.author != current_user:
        abort(404)

    db.session.execute(sa.update(Post).where(Post.user_id == current_user.id).values(is_pinned=False))
    post.is_pinned = True
    db.session.commit()

    flash('Post pinned to your profile!', 'success')
    return redirect(request.referrer or url_for('main.user', username=current_user.username))


@bp.route('/share_post/<int:post_id>', methods=['POST'])
@login_required
def share_post(post_id):
    original_post = db.session.get(Post, post_id)
    if original_post is None:
        flash('Post not found.')
        return redirect(url_for('main.index'))

    shared_post = SharedPost(
        original_post_id=post_id,
        shared_by_id=current_user.id
    )
    db.session.add(shared_post)
    original_post.share_count += 1

    share_post = Post(
        body=f" Shared a post from @{original_post.author.username}",
        author=current_user,
        privacy='public'
    )
    db.session.add(share_post)
    db.session.commit()

    flash('Post shared!', 'success')
    return redirect(url_for('main.index'))


@bp.route('/save_post/<int:post_id>')
@login_required
def save_post(post_id):
    post = db.session.get(Post, post_id)
    if post is None:
        return jsonify({'error': 'Post not found'}), 404

    saved = db.session.scalar(
        sa.select(SavedPost).where(SavedPost.user_id == current_user.id, SavedPost.post_id == post_id)
    )

    if saved:
        db.session.delete(saved)
        saved_status = False
    else:
        saved = SavedPost(user_id=current_user.id, post_id=post_id)
        db.session.add(saved)
        saved_status = True

    db.session.commit()
    return jsonify({'saved': saved_status})


@bp.route('/react_post/<int:post_id>/<reaction>')
@login_required
def react_post(post_id, reaction):
    valid_reactions = ['like', 'love', 'haha', 'wow', 'sad', 'angry']
    if reaction not in valid_reactions:
        return jsonify({'error': 'Invalid reaction'}), 400

    post = db.session.get(Post, post_id)
    if post is None:
        return jsonify({'error': 'Post not found'}), 404

    existing = db.session.scalar(
        sa.select(PostReaction).where(PostReaction.user_id == current_user.id, PostReaction.post_id == post_id)
    )

    if existing:
        if existing.reaction == reaction:
            db.session.delete(existing)
            reaction_set = False
        else:
            existing.reaction = reaction
            reaction_set = True
    else:
        post_reaction = PostReaction(user_id=current_user.id, post_id=post_id, reaction=reaction)
        db.session.add(post_reaction)
        reaction_set = True

    db.session.commit()

    reaction_counts = post.get_reaction_counts()

    return jsonify({
        'reaction_set': reaction_set,
        'reaction': reaction if reaction_set else None,
        'counts': reaction_counts,
        'total': sum(reaction_counts.values())
    })


@bp.route('/like/<int:post_id>')
@login_required
def like_post(post_id):
    post = db.session.get(Post, post_id)
    if post is None:
        return jsonify({'error': 'Post not found'}), 404

    existing = db.session.scalar(
        sa.select(Like).where(Like.user_id == current_user.id, Like.post_id == post_id)
    )

    if not existing:
        like = Like(user_id=current_user.id, post_id=post_id)
        db.session.add(like)
        post.author.points += 1
        liked = True

        if post.author.id != current_user.id:
            print(f"Sending like notification - Author: {post.author.id}, Liker: {current_user.id}")
            send_like_notification(post.author.id, current_user.username, post.id, post.body)
    else:
        db.session.delete(existing)
        liked = False

    db.session.commit()
    like_count = post.like_count()

    return jsonify({'liked': liked, 'count': like_count})


@bp.route('/add_comment/<int:post_id>', methods=['POST'])
@login_required
def add_comment(post_id):
    post = db.session.get(Post, post_id)
    if post is None:
        flash('Post not found.')
        return redirect(url_for('main.index'))

    body = request.form.get('body', '').strip()
    if body:
        comment = Comment(body=body, user_id=current_user.id, post_id=post_id)
        db.session.add(comment)
        db.session.commit()

        if post.author.id != current_user.id:
            print(f"Sending comment notification - Author: {post.author.id}, Commenter: {current_user.id}")
            send_comment_notification(post.author.id, current_user.username, post.id, body)

        flash('Comment added.', 'success')

    return redirect(request.referrer or url_for('main.index'))

@bp.route('/delete_comment/<int:comment_id>')
@login_required
def delete_comment(comment_id):
    comment = db.session.get(Comment, comment_id)
    if comment is None:
        flash('Comment not found.')
        return redirect(request.referrer or url_for('main.index'))

    if comment.author != current_user and not current_user.is_admin:
        flash('You cannot delete this comment.')
        return redirect(request.referrer or url_for('main.index'))

    db.session.delete(comment)
    db.session.commit()
    flash('Comment deleted.', 'info')
    return redirect(request.referrer or url_for('main.index'))


@bp.route('/saved')
@login_required
def saved_posts():
    saved = db.session.scalars(
        sa.select(SavedPost).where(SavedPost.user_id == current_user.id).order_by(SavedPost.timestamp.desc())
    ).all()
    posts = [s.post for s in saved]
    return render_template('saved_posts.html', title='Saved Posts', posts=posts)


@bp.route('/hashtag/<tag>')
def hashtag_posts(tag):
    hashtag = db.session.scalar(sa.select(Hashtag).where(Hashtag.name == tag.lower()))
    if not hashtag:
        flash('No posts found with this hashtag.')
        return redirect(url_for('main.index'))

    post_hashtags = db.session.scalars(
        sa.select(PostHashtag).where(PostHashtag.hashtag_id == hashtag.id)
    ).all()
    post_ids = [ph.post_id for ph in post_hashtags]
    posts = db.session.scalars(
        sa.select(Post).where(Post.id.in_(post_ids)).order_by(Post.timestamp.desc())
    ).all()
    return render_template('hashtag.html', title=f'#{tag}', posts=posts, hashtag=hashtag)


@bp.route('/trending')
def trending():
    trending_hashtags = db.session.scalars(
        sa.select(Hashtag).order_by(Hashtag.post_count.desc()).limit(10)
    ).all()
    return render_template('trending.html', title='Trending', hashtags=trending_hashtags)


@bp.route('/block_user/<int:user_id>')
@login_required
def block_user(user_id):
    user_to_block = db.session.get(User, user_id)
    if user_to_block is None:
        flash('User not found.')
        return redirect(url_for('main.index'))

    blocked = db.session.scalar(
        sa.select(BlockedUser).where(
            BlockedUser.blocker_id == current_user.id,
            BlockedUser.blocked_id == user_id
        )
    )

    if not blocked:
        blocked = BlockedUser(blocker_id=current_user.id, blocked_id=user_id)
        db.session.add(blocked)
        db.session.commit()
        flash(f'You have blocked {user_to_block.username}.', 'warning')
    else:
        flash('User already blocked.', 'info')

    return redirect(request.referrer or url_for('main.index'))


@bp.route('/unblock_user/<int:user_id>')
@login_required
def unblock_user(user_id):
    blocked = db.session.scalar(
        sa.select(BlockedUser).where(
            BlockedUser.blocker_id == current_user.id,
            BlockedUser.blocked_id == user_id
        )
    )

    if blocked:
        db.session.delete(blocked)
        db.session.commit()
        flash('User unblocked.', 'success')

    return redirect(url_for('main.user', username=current_user.username))


@bp.route('/report_post/<int:post_id>', methods=['GET', 'POST'])
@login_required
def report_post(post_id):
    post = db.session.get(Post, post_id)
    if post is None:
        flash('Post not found.')
        return redirect(url_for('main.index'))

    form = ReportForm()
    if form.validate_on_submit():
        existing_report = SpamReport.query.filter_by(
            post_id=post_id,
            reporter_id=current_user.id
        ).first()

        if existing_report:
            flash('You have already reported this post.', 'warning')
            return redirect(url_for('main.index'))

        report = SpamReport(
            post_id=post_id,
            reporter_id=current_user.id,
            reason=form.reason.data,
            reviewed=False
        )
        db.session.add(report)
        db.session.commit()
        from app.services.report_service import report_service
        report_service.generate_reports_summary()
        report_service.generate_users_report()
        report_service.generate_posts_report()

        flash('Thank you for your report. An admin will review it.', 'success')
        return redirect(url_for('main.index'))

    return render_template('report_post.html', title='Report Post', form=form, post=post)


@bp.route('/chat/<username>')
@login_required
def chat(username):
    other_user = db.first_or_404(sa.select(User).where(User.username == username))

    messages = db.session.scalars(
        sa.select(ChatMessage).where(
            ((ChatMessage.sender_id == current_user.id) & (ChatMessage.recipient_id == other_user.id)) |
            ((ChatMessage.sender_id == other_user.id) & (ChatMessage.recipient_id == current_user.id))
        ).order_by(ChatMessage.timestamp.asc())
    ).all()

    db.session.execute(
        sa.update(ChatMessage).where(
            ChatMessage.sender_id == other_user.id,
            ChatMessage.recipient_id == current_user.id,
            ChatMessage.is_read == False
        ).values(is_read=True)
    )
    db.session.commit()

    return render_template('chat.html', title='Chat', other_user=other_user, messages=messages)


@bp.route('/send_chat_message', methods=['POST'])
@login_required
def send_chat_message():
    recipient_id = request.form.get('recipient_id', type=int)
    message = request.form.get('message', '').strip()

    if not message:
        return jsonify({'error': 'Message cannot be empty'}), 400

    recipient = db.session.get(User, recipient_id)
    if recipient is None:
        return jsonify({'error': 'User not found'}), 404

    chat_message = ChatMessage(
        sender_id=current_user.id,
        recipient_id=recipient_id,
        message=message,
        is_read=False,
        timestamp=datetime.now(timezone.utc)
    )
    db.session.add(chat_message)
    db.session.commit()

    return jsonify({
        'success': True,
        'message': message,
        'timestamp': chat_message.timestamp.timestamp()
    })


@bp.route('/get_chat_messages/<int:other_user_id>')
@login_required
def get_chat_messages(other_user_id):
    since = request.args.get('since', 0, type=float)

    messages = db.session.scalars(
        sa.select(ChatMessage).where(
            ((ChatMessage.sender_id == current_user.id) & (ChatMessage.recipient_id == other_user_id)) |
            ((ChatMessage.sender_id == other_user_id) & (ChatMessage.recipient_id == current_user.id)),
            ChatMessage.timestamp > datetime.fromtimestamp(since, tz=timezone.utc)
        ).order_by(ChatMessage.timestamp.asc())
    ).all()

    return jsonify([{
        'id': m.id,
        'sender_id': m.sender_id,
        'message': m.message,
        'timestamp': m.timestamp.timestamp(),
        'is_mine': m.sender_id == current_user.id
    } for m in messages])

@bp.route('/conversations')
@login_required
def conversations():
    sent_messages = db.session.scalars(
        sa.select(ChatMessage).where(ChatMessage.sender_id == current_user.id)
    ).all()
    received_messages = db.session.scalars(
        sa.select(ChatMessage).where(ChatMessage.recipient_id == current_user.id)
    ).all()

    user_ids = set()
    for msg in sent_messages:
        user_ids.add(msg.recipient_id)
    for msg in received_messages:
        user_ids.add(msg.sender_id)

    conversations = []
    for user_id in user_ids:
        other_user = db.session.get(User, user_id)
        if other_user:
            last_message = db.session.scalar(
                sa.select(ChatMessage).where(
                    ((ChatMessage.sender_id == current_user.id) & (ChatMessage.recipient_id == user_id)) |
                    ((ChatMessage.sender_id == user_id) & (ChatMessage.recipient_id == current_user.id))
                ).order_by(ChatMessage.timestamp.desc())
            )
            unread_count = db.session.query(ChatMessage).filter(
                ChatMessage.sender_id == user_id,
                ChatMessage.recipient_id == current_user.id,
                ChatMessage.is_read == False
            ).count()

            conversations.append({
                'user': other_user,
                'last_message': last_message,
                'unread_count': unread_count
            })

    conversations.sort(key=lambda x: x['last_message'].timestamp if x['last_message'] else datetime.min, reverse=True)

    return render_template('conversations.html', title='Conversations', conversations=conversations)


@bp.route('/view_story/<int:story_id>')
@login_required
def view_story(story_id):
    story = db.session.get(Story, story_id)
    if story is None:
        flash('Story not found.')
        return redirect(url_for('main.index'))

    expires_at = story.expires_at
    if expires_at.tzinfo is None:
        from datetime import timezone
        expires_at = expires_at.replace(tzinfo=timezone.utc)

    if expires_at < datetime.now(timezone.utc):
        flash('Story has expired.')
        return redirect(url_for('main.index'))

    existing_view = db.session.scalar(
        sa.select(StoryView).where(StoryView.story_id == story_id, StoryView.viewer_id == current_user.id)
    )
    if not existing_view:
        view = StoryView(story_id=story_id, viewer_id=current_user.id)
        db.session.add(view)
        db.session.commit()

    return render_template('view_story.html', title='Story', story=story)

@bp.route('/user/<username>')
@login_required
def user(username):
    user = db.first_or_404(sa.select(User).where(User.username == username))

    if user.is_private and not current_user.is_following(user) and user != current_user and not current_user.is_admin:
        return render_template('private_profile.html', user=user)

    if user.is_blocked_by(current_user) or current_user.is_blocked_by(user):
        return render_template('blocked_profile.html', user=user)

    page = request.args.get('page', 1, type=int)
    query = user.posts.select().where(Post.scheduled_for == None).order_by(Post.is_pinned.desc(), Post.timestamp.desc())
    posts = db.paginate(query, page=page,
                        per_page=current_app.config['POSTS_PER_PAGE'],
                        error_out=False)
    next_url = url_for('main.user', username=user.username, page=posts.next_num) if posts.has_next else None
    prev_url = url_for('main.user', username=user.username, page=posts.prev_num) if posts.has_prev else None
    form = EmptyForm()

    return render_template('user.html', user=user, posts=posts.items,
                           next_url=next_url, prev_url=prev_url, form=form)


@bp.route('/user/<username>/popup')
@login_required
def user_popup(username):
    user = db.first_or_404(sa.select(User).where(User.username == username))
    form = EmptyForm()
    return render_template('user_popup.html', user=user, form=form)


@bp.route('/edit_profile', methods=['GET', 'POST'])
@login_required
def edit_profile():
    form = EditProfileForm(current_user.username)
    if form.validate_on_submit():
        current_user.username = form.username.data
        current_user.about_me = form.about_me.data
        current_user.is_private = form.is_private.data == 'True'

        if form.profile_pic.data and form.profile_pic.data.filename:
            old_pic = current_user.profile_pic
            current_user.profile_pic = save_profile_picture(form.profile_pic.data, old_pic)

        db.session.commit()
        flash('Your changes have been saved.')
        return redirect(url_for('main.edit_profile'))
    elif request.method == 'GET':
        form.username.data = current_user.username
        form.about_me.data = current_user.about_me
        form.is_private.data = str(current_user.is_private)
    return render_template('edit_profile.html', title='Edit Profile', form=form)


from app.notification_helper import send_follow_notification


@bp.route('/follow/<username>', methods=['POST'])
@login_required
def follow(username):
    form = EmptyForm()
    if form.validate_on_submit():
        user = db.session.scalar(sa.select(User).where(User.username == username))
        if user is None:
            flash(f'User {username} not found.')
            return redirect(url_for('main.index'))
        if user == current_user:
            flash('You cannot follow yourself!')
            return redirect(url_for('main.user', username=username))
        current_user.follow(user)
        db.session.commit()

        print(f"Sending follow notification - Author: {user.id}, Follower: {current_user.id}")
        send_follow_notification(user.id, current_user.username)

        flash(f'You are following {username}!')
        return redirect(url_for('main.user', username=username))
    else:
        return redirect(url_for('main.index'))

@bp.route('/unfollow/<username>', methods=['POST'])
@login_required
def unfollow(username):
    form = EmptyForm()
    if form.validate_on_submit():
        user = db.session.scalar(sa.select(User).where(User.username == username))
        if user is None:
            flash(f'User {username} not found.')
            return redirect(url_for('main.index'))
        if user == current_user:
            flash('You cannot unfollow yourself!')
            return redirect(url_for('main.user', username=username))
        current_user.unfollow(user)
        db.session.commit()
        flash(f'You are not following {username}.')
        return redirect(url_for('main.user', username=username))
    else:
        return redirect(url_for('main.index'))

@bp.route('/explore')
@login_required
def explore():
    page = request.args.get('page', 1, type=int)
    query = sa.select(Post).where(
        Post.privacy == 'public',
        Post.scheduled_for == None
    ).order_by(Post.timestamp.desc())
    posts = db.paginate(query, page=page,
                        per_page=current_app.config['POSTS_PER_PAGE'],
                        error_out=False)
    next_url = url_for('main.explore', page=posts.next_num) if posts.has_next else None
    prev_url = url_for('main.explore', page=posts.prev_num) if posts.has_prev else None
    return render_template('explore.html', title='Explore',
                           posts=posts.items, next_url=next_url, prev_url=prev_url)

@bp.route('/translate', methods=['POST'])
@login_required
def translate_text():
    data = request.get_json()
    return {'text': translate(data['text'], data['source_language'], data['dest_language'])}


@bp.route('/send_message/<recipient>', methods=['GET', 'POST'])
@login_required
def send_message(recipient):
    user = db.first_or_404(sa.select(User).where(User.username == recipient))
    form = MessageForm()
    if form.validate_on_submit():
        msg = Message(author=current_user, recipient=user, body=form.message.data)
        db.session.add(msg)
        user.add_notification('unread_message_count', user.unread_message_count())
        db.session.commit()
        flash('Your message has been sent.')
        return redirect(url_for('main.user', username=recipient))
    return render_template('send_message.html', title='Send Message', form=form, recipient=recipient)


@bp.route('/messages')
@login_required
def messages():
    current_user.last_message_read_time = datetime.now(timezone.utc)
    current_user.add_notification('unread_message_count', 0)
    db.session.commit()
    page = request.args.get('page', 1, type=int)
    query = current_user.messages_received.select().order_by(Message.timestamp.desc())
    messages = db.paginate(query, page=page, per_page=current_app.config['POSTS_PER_PAGE'], error_out=False)
    next_url = url_for('main.messages', page=messages.next_num) if messages.has_next else None
    prev_url = url_for('main.messages', page=messages.prev_num) if messages.has_prev else None
    return render_template('messages.html', messages=messages.items, next_url=next_url, prev_url=prev_url)


@bp.route('/notifications')
@login_required
def notifications():
    since = request.args.get('since', 0.0, type=float)
    query = current_user.notifications.select().where(Notification.timestamp > since).order_by(
        Notification.timestamp.asc())
    notifications = db.session.scalars(query)
    return [{'name': n.name, 'data': n.get_data(), 'timestamp': n.timestamp} for n in notifications]


@bp.route('/export_posts')
@login_required
def export_posts():
    if current_user.get_task_in_progress('export_posts'):
        flash('An export task is currently in progress')
    else:
        current_user.launch_task('export_posts', 'Exporting posts...')
        db.session.commit()
    return redirect(url_for('main.user', username=current_user.username))


@bp.route('/admin/moderation')
@login_required
@admin_required
def moderation():
    page = request.args.get('page', 1, type=int)

    reported_posts = db.session.query(Post).join(
        SpamReport, SpamReport.post_id == Post.id
    ).filter(
        Post.reviewed == False,
        SpamReport.reviewed == False
    ).group_by(Post.id).order_by(
        db.func.count(SpamReport.id).desc(),
        Post.timestamp.desc()
    ).paginate(page=page, per_page=20, error_out=False)

    spam_posts = Post.query.filter(
        Post.is_spam == True,
        Post.reviewed == False
    ).order_by(Post.timestamp.desc()).all()

    all_post_ids = set()
    all_posts = []

    for post in reported_posts.items:
        if post.id not in all_post_ids:
            all_post_ids.add(post.id)
            all_posts.append(post)

    for post in spam_posts:
        if post.id not in all_post_ids:
            all_post_ids.add(post.id)
            all_posts.append(post)

    all_posts.sort(key=lambda x: x.timestamp, reverse=True)

    report_counts = {}
    for post in all_posts:
        count = SpamReport.query.filter_by(post_id=post.id, reviewed=False).count()
        report_counts[post.id] = count

    return render_template('admin/moderation.html',
                           title='Moderation Queue',
                           posts=all_posts,
                           report_counts=report_counts,
                           pagination=reported_posts)

@bp.route('/admin/approve/<int:post_id>')
@login_required
@admin_required
def approve_post(post_id):
    post = db.session.get(Post, post_id)
    if post is None:
        flash('Post not found.')
        return redirect(url_for('main.moderation'))

    post.is_spam = False
    post.reviewed = True
    post.approved = True
    db.session.commit()

    flash(f'Post by {post.author.username} has been approved.', 'success')
    return redirect(url_for('main.moderation'))


@bp.route('/admin/reject/<int:post_id>')
@login_required
@admin_required
def reject_post(post_id):
    post = db.session.get(Post, post_id)
    if post is None:
        flash('Post not found.')
        return redirect(url_for('main.moderation'))

    username = post.author.username

    if post.media_url:
        delete_media(post.media_url)

    db.session.delete(post)
    db.session.commit()

    flash(f'Post by {username} has been rejected and deleted.', 'warning')
    return redirect(url_for('main.moderation'))


@bp.route('/admin/flagged')
@login_required
@admin_required
def flagged_posts():
    page = request.args.get('page', 1, type=int)
    query = sa.select(Post).where(Post.is_spam == True).order_by(Post.timestamp.desc())
    posts = db.paginate(query, page=page, per_page=current_app.config['POSTS_PER_PAGE'], error_out=False)
    next_url = url_for('main.flagged_posts', page=posts.next_num) if posts.has_next else None
    prev_url = url_for('main.flagged_posts', page=posts.prev_num) if posts.has_prev else None
    return render_template('admin/flagged.html', title='Flagged Posts History', posts=posts.items, next_url=next_url,
                           prev_url=prev_url)


@bp.route('/admin/analytics')
@login_required
@admin_required
def analytics():
    total_users = db.session.query(User).count()
    active_today = db.session.query(User).filter(
        User.last_seen > datetime.now(timezone.utc) - timedelta(days=1)
    ).count()
    total_posts = db.session.query(Post).count()
    spam_posts = db.session.query(Post).filter(Post.is_spam == True).count()

    return render_template('admin/analytics.html', title='Analytics',
                           total_users=total_users, active_today=active_today,
                           total_posts=total_posts, spam_posts=spam_posts)


@bp.route('/test-notification')
@login_required
def test_notification():
    from app.notification_helper import create_notification

    create_notification(current_user.id, 'test', {
        'type': 'test',
        'message': 'This is a test notification',
        'username': 'System'
    })

    flash('Test notification created!', 'success')
    return redirect(url_for('main.notifications_page'))


@bp.route('/search')
@login_required
def search():
    if not g.search_form.validate():
        return redirect(url_for('main.explore'))

    query = g.search_form.q.data
    page = request.args.get('page', 1, type=int)

    search_query = sa.select(Post).where(
        sa.or_(
            Post.body.ilike(f'%{query}%'),
            Post.body.contains(query)
        ),
        Post.scheduled_for == None
    ).order_by(Post.timestamp.desc())

    posts = db.paginate(search_query, page=page,
                        per_page=current_app.config['POSTS_PER_PAGE'],
                        error_out=False)

    next_url = url_for('main.search', q=query, page=posts.next_num) if posts.has_next else None
    prev_url = url_for('main.search', q=query, page=posts.prev_num) if posts.has_prev else None

    users = db.session.scalars(
        sa.select(User).where(
            sa.or_(
                User.username.ilike(f'%{query}%'),
                User.about_me.ilike(f'%{query}%')
            )
        ).limit(10)
    ).all()

    return render_template('search.html', title='Search',
                           posts=posts.items, users=users,
                           query=query, next_url=next_url, prev_url=prev_url)

from app.ai_helper import ai
from flask import current_app

def get_ai():
    if not ai.api_key:
        api_key = current_app.config.get('OPENROUTER_API_KEY')
        if api_key:
            ai.set_api_key(api_key)
    return ai


@bp.route('/ai/chat', methods=['POST'])
@login_required
def ai_chat():
    user_message = request.form.get('message', '')
    if not user_message:
        return jsonify({'error': 'No message provided'}), 400
    ai_instance = get_ai()
    response = ai_instance.chat(user_message)
    return jsonify({'response': response})


@bp.route('/ai/generate-post', methods=['POST'])
@login_required
def ai_generate_post():
    data = request.get_json()
    topic = data.get('topic', '')
    tone = data.get('tone', 'casual')
    if not topic:
        return jsonify({'error': 'No topic provided'}), 400
    ai_instance = get_ai()
    post = ai_instance.generate_post(topic, tone)
    return jsonify({'post': post})


@bp.route('/ai/improve', methods=['POST'])
@login_required
def ai_improve_text():
    data = request.get_json()
    text = data.get('text', '')
    instruction = data.get('instruction', 'improve this text')
    if not text:
        return jsonify({'error': 'No text provided'}), 400
    ai_instance = get_ai()
    improved = ai_instance.improve_text(text, instruction)
    return jsonify({'improved': improved})


@bp.route('/ai-chat')
@login_required
def ai_chat_page():
    return render_template('ai_chat.html', title='AI Assistant')