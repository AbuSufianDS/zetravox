from datetime import datetime, timezone, timedelta
from flask import render_template, flash, redirect, url_for, request, g, current_app, abort, jsonify, send_file
from flask_login import current_user, login_required
from flask_babel import _, get_locale
import sqlalchemy as sa
import re
from functools import wraps
from langdetect import detect, LangDetectException
from app import db
from app.main.forms import EditProfileForm, EmptyForm, PostForm, SearchForm, MessageForm, CommentForm, ReportForm, StoryForm
from app.media_helpers import save_media, delete_media, save_multiple_media, delete_multiple_media
from app.translate import translate
from app.main import bp
from spam_service.integration import spam_checker
from app.profile_helpers import save_profile_picture, save_cover_picture, delete_profile_picture, delete_cover_picture
from app.services.recommendation_service import recommendation_engine
from app.services.report_service import report_service
from app.models import (User, Post, Message, Notification, Like, Comment, SpamReport, UserActivity, Hashtag, PostHashtag, SavedPost, SharedPost, BlockedUser,
                        PostReaction, Story, StoryView, ChatMessage, StoryReaction, StoryComment, FriendRequest, friends, PostMedia, HiddenPost, NotInterestedPost, InterestedPost, SecurityEvent, CommentReaction)
from app.models import InnerCircleMembership
lastNotificationTime = 0
from flask import session
from app.models import VIPUser, Feedback, HelpRequest
from app.main.forms import VIPUpgradeForm, FeedbackForm, HelpForm

@bp.route('/settings/notifications', methods=['GET', 'POST'])
@login_required
def notification_settings():
    from app.main.forms import NotificationSettingsForm

    form = NotificationSettingsForm()

    if form.validate_on_submit():
        current_user.notify_push_likes = form.notify_push_likes.data
        current_user.notify_push_comments = form.notify_push_comments.data
        current_user.notify_push_follows = form.notify_push_follows.data
        current_user.notify_push_shares = form.notify_push_shares.data
        current_user.notify_push_friend_requests = form.notify_push_friend_requests.data
        current_user.notify_push_messages = form.notify_push_messages.data

        current_user.notify_email_likes = form.notify_email_likes.data
        current_user.notify_email_comments = form.notify_email_comments.data
        current_user.notify_email_follows = form.notify_email_follows.data
        current_user.notify_email_shares = form.notify_email_shares.data
        current_user.notify_email_friend_requests = form.notify_email_friend_requests.data
        current_user.notify_email_messages = form.notify_email_messages.data

        db.session.commit()
        flash('Your notification settings have been updated.', 'success')
        return redirect(url_for('main.notification_settings'))

    form.notify_push_likes.data = current_user.notify_push_likes
    form.notify_push_comments.data = current_user.notify_push_comments
    form.notify_push_follows.data = current_user.notify_push_follows
    form.notify_push_shares.data = getattr(current_user, 'notify_push_shares', True)
    form.notify_push_friend_requests.data = getattr(current_user, 'notify_push_friend_requests', True)
    form.notify_push_messages.data = getattr(current_user, 'notify_push_messages', True)

    form.notify_email_likes.data = current_user.notify_email_likes
    form.notify_email_comments.data = current_user.notify_email_comments
    form.notify_email_follows.data = current_user.notify_email_follows
    form.notify_email_shares.data = getattr(current_user, 'notify_email_shares', False)
    form.notify_email_friend_requests.data = getattr(current_user, 'notify_email_friend_requests', False)
    form.notify_email_messages.data = getattr(current_user, 'notify_email_messages', False)

    return render_template('security/notifications.html', title='Notification Settings', form=form)

def vip_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            flash('Please login first.', 'warning')
            return redirect(url_for('auth.login'))
        if not current_user.is_vip:
            flash('This feature is available for VIP members only. Please upgrade to VIP.', 'warning')
            return redirect(url_for('main.vip'))
        return f(*args, **kwargs)
    return decorated_function

@bp.route('/api/notifications')
@login_required
def api_get_notifications():
    try:
        page = request.args.get('page', 1, type=int)
        per_page = 20

        notifications_query = current_user.notifications.select().order_by(Notification.timestamp.desc())
        notifications = db.paginate(notifications_query, page=page, per_page=per_page, error_out=False)

        notifications_list = []
        for notif in notifications.items:
            payload = notif.get_data() if hasattr(notif, 'get_data') else {}
            notifications_list.append({
                'id': notif.id,
                'name': notif.name,
                'timestamp': notif.timestamp,
                'payload': payload,
                'read': getattr(notif, 'read', False)
            })

        unread_count_query = current_user.notifications.select().where(Notification.read == False)
        unread_count = db.session.scalar(sa.select(sa.func.count()).select_from(unread_count_query.subquery()))

        return jsonify({
            'success': True,
            'notifications': notifications_list,
            'unread_count': unread_count or 0,
            'has_next': notifications.has_next,
            'total': notifications.total
        })
    except Exception as e:
        current_app.logger.error(f"API notifications error: {e}")
        return jsonify({'success': False, 'error': str(e), 'notifications': [], 'unread_count': 0})

@bp.route('/api/notifications/mark-read', methods=['POST'])
@login_required
def api_mark_notifications_read():
    try:
        query = current_user.notifications.select().where(Notification.read == False)
        notifications = db.session.scalars(query).all()
        for notif in notifications:
            notif.read = True
        db.session.commit()
        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500

@bp.route('/api/notifications/<int:notif_id>/mark-read', methods=['POST'])
@login_required
def api_mark_single_notification_read(notif_id):
    try:
        notification = db.session.get(Notification, notif_id)
        if notification and notification.user_id == current_user.id:
            notification.read = True
            db.session.commit()
            return jsonify({'success': True})
        return jsonify({'success': False, 'error': 'Notification not found'}), 404
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


@bp.route('/api/test-notification', methods=['POST'])
@login_required
def api_test_notification():
    try:
        from app.notification_helper import create_notification
        create_notification(current_user.id, 'test', {
            'type': 'test',
            'message': 'This is a test notification',
            'username': 'System'
        })
        return jsonify({'success': True, 'message': 'Test notification sent'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

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
        current_user.last_active = datetime.now(timezone.utc)
        db.session.commit()
        g.search_form = SearchForm()
    g.locale = str(get_locale())


from datetime import datetime, timezone


@bp.route('/', methods=['GET', 'POST'])
@bp.route('/index', methods=['GET', 'POST'])
@login_required
def index():
    form = PostForm()
    comment_form = CommentForm()
    story_form = StoryForm()

    if request.method == 'POST' and 'submit_post' in request.form:
        post_content = request.form.get('post', '')
        if not post_content:
            flash('Post content cannot be empty.', 'warning')
            return redirect(url_for('main.index'))

        is_spam, spam_confidence, should_warn = spam_checker.check_post(post_content)

        try:
            language = detect(post_content)
        except LangDetectException:
            language = ''

        scheduled_for = None
        schedule_date = request.form.get('schedule_date', '')
        if schedule_date:
            try:
                scheduled_for = datetime.strptime(schedule_date, '%Y-%m-%d %H:%M').replace(tzinfo=timezone.utc)
            except ValueError:
                pass

        post = Post(
            body=post_content,
            author=current_user,
            language=language,
            is_spam=is_spam,
            spam_confidence=spam_confidence,
            reviewed=False,
            approved=not should_warn,
            privacy=request.form.get('privacy', 'public'),
            scheduled_for=scheduled_for
        )
        db.session.add(post)
        db.session.commit()

        if 'media_files' in request.files:
            print("DEBUG: media_files found in request")
            files = request.files.getlist('media_files')
            print(f"DEBUG: Found {len(files)} files")
            files = [f for f in files if f and f.filename]
            print(f"DEBUG: After filtering: {len(files)} files")
            if files:
                saved_media = save_multiple_media(files, 'posts')
                for idx, media in enumerate(saved_media):
                    post_media = PostMedia(
                        post_id=post.id,
                        media_url=media['filename'],
                        media_type=media['media_type'],
                        order=idx
                    )
                    db.session.add(post_media)
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
            flash('Your post is now live!')
        return redirect(url_for('main.index'))

    following_ids = [f.id for f in db.session.scalars(current_user.following.select())]
    following_ids.append(current_user.id)
    stories = db.session.scalars(
        sa.select(Story).where(
            Story.user_id.in_(following_ids),
            Story.expires_at > datetime.now(timezone.utc)
        ).order_by(Story.timestamp.desc())
    ).all()

    def time_ago(dt):
        now = datetime.now(timezone.utc)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        diff = now - dt
        if diff.days > 0:
            return f'{diff.days}d ago'
        if diff.seconds > 3600:
            return f'{diff.seconds // 3600}h ago'
        if diff.seconds > 60:
            return f'{diff.seconds // 60}m ago'
        return 'Just now'

    stories_by_user = {}
    stories_data = []
    for story in stories:
        if story.user_id not in stories_by_user:
            stories_by_user[story.user_id] = []
        stories_by_user[story.user_id].append(story)
        reaction_count = db.session.query(StoryReaction).filter_by(story_id=story.id).count()
        stories_data.append({
            'id': story.id,
            'media_url': story.media_url,
            'media_type': story.media_type,
            'caption': story.caption or '',
            'author_name': story.author.username,
            'author_avatar': story.author.avatar(48),
            'time_ago': time_ago(story.timestamp),
            'reaction_count': reaction_count
        })

    upcoming_birthdays = []
    for friend in current_user.get_friends():
        if friend.birthday:
            try:
                birthday_date = datetime.strptime(friend.birthday, '%Y-%m-%d').date()
                today = datetime.now().date()
                birthday_this_year = birthday_date.replace(year=today.year)
                if birthday_this_year < today:
                    birthday_this_year = birthday_date.replace(year=today.year + 1)
                days_until = (birthday_this_year - today).days
                if days_until <= 7:
                    upcoming_birthdays.append({
                        'user': friend,
                        'days_until': days_until
                    })
            except:
                pass
    upcoming_birthdays.sort(key=lambda x: x['days_until'])

    active_contacts = current_user.get_active_friends_online()

    page = request.args.get('page', 1, type=int)

    blocked_user_ids = db.session.query(BlockedUser.blocked_id).filter_by(blocker_id=current_user.id).all()
    blocked_ids = [b[0] for b in blocked_user_ids]

    hidden_post_ids = db.session.query(HiddenPost.post_id).filter_by(user_id=current_user.id).all()
    not_interested_ids = db.session.query(NotInterestedPost.post_id).filter_by(user_id=current_user.id).all()
    excluded_post_ids = list(set([h[0] for h in hidden_post_ids] + [n[0] for n in not_interested_ids]))

    posts_query = sa.select(Post).where(
        Post.scheduled_for == None,
        Post.privacy == 'public'
    )

    if blocked_ids:
        posts_query = posts_query.where(Post.user_id.notin_(blocked_ids))
    if excluded_post_ids:
        posts_query = posts_query.where(Post.id.notin_(excluded_post_ids))

    posts_query = posts_query.order_by(Post.timestamp.desc())

    posts = db.paginate(posts_query, page=page,
                        per_page=current_app.config['POSTS_PER_PAGE'],
                        error_out=False)

    next_url = url_for('main.index', page=posts.next_num) if posts.has_next else None
    prev_url = url_for('main.index', page=posts.prev_num) if posts.has_prev else None

    grouped_temp = {}
    for story in stories_data:
        author = story['author_name']
        if author not in grouped_temp:
            grouped_temp[author] = []
        grouped_temp[author].append(story)

    grouped_stories_data = []
    for author, stories in grouped_temp.items():
        grouped_stories_data.append({
            'author_name': author,
            'author_avatar': stories[0]['author_avatar'],
            'story_count': len(stories),
            'stories': stories
        })

    print("=== DEBUG: stories_data ===")
    print(f"Total stories: {len(stories_data)}")
    for s in stories_data:
        print(f"  - {s['author_name']}")

    print("=== DEBUG: grouped_stories_data ===")
    print(f"Total groups: {len(grouped_stories_data)}")
    for g in grouped_stories_data:
        print(f"  - {g['author_name']}: {g['story_count']} stories")


    return render_template('index.html', title='Home', form=form, comment_form=comment_form,
                           story_form=story_form, stories_by_user=stories_by_user,
                           stories_data=stories_data,
                           grouped_stories_data=grouped_stories_data,
                           posts=posts.items, next_url=next_url, prev_url=prev_url,
                           upcoming_birthdays=upcoming_birthdays,
                           active_contacts=active_contacts)


@bp.route('/interested/<int:post_id>')
@login_required
def interested(post_id):
    post = db.session.get(Post, post_id)
    if not post:
        return jsonify({'error': 'Post not found'}), 404

    existing = InterestedPost.query.filter_by(user_id=current_user.id, post_id=post_id).first()
    if existing:
        db.session.delete(existing)
        interested = False
    else:
        interested_post = InterestedPost(user_id=current_user.id, post_id=post_id)
        db.session.add(interested_post)
        not_interested = NotInterestedPost.query.filter_by(user_id=current_user.id, post_id=post_id).first()
        if not_interested:
            db.session.delete(not_interested)
        interested = True

    db.session.commit()
    return jsonify(
        {'interested': interested, 'message': 'Post marked as interested' if interested else 'Removed from interested'})


@bp.route('/get-blocked-users')
@login_required
def get_blocked_users():
    blocked_list = BlockedUser.query.filter_by(blocker_id=current_user.id).all()
    blocked_users = []
    for b in blocked_list:
        user = db.session.get(User, b.blocked_id)
        if user:
            blocked_users.append({
                'id': user.id,
                'username': user.username,
                'avatar': user.avatar(50),
                'is_verified': user.is_verified
            })
    return jsonify({'blocked_users': blocked_users})

@bp.route('/user/<username>/media-data')
@login_required
def user_media_data(username):
    user = db.first_or_404(sa.select(User).where(User.username == username))

    media_list = []
    posts_with_media = Post.query.filter(
        Post.user_id == user.id,
        Post.media_items.any(),
        Post.privacy == 'public'
    ).order_by(Post.timestamp.desc()).limit(20).all()

    for post in posts_with_media:
        for media in post.media_items:
            media_list.append({
                'url': media.media_url,
                'type': media.media_type,
                'post_id': post.id
            })

    return jsonify({'media': media_list})

@bp.route('/not-interested/<int:post_id>')
@login_required
def not_interested(post_id):
    post = db.session.get(Post, post_id)
    if not post:
        return jsonify({'error': 'Post not found'}), 404

    existing = NotInterestedPost.query.filter_by(user_id=current_user.id, post_id=post_id).first()
    if not existing:
        not_interested = NotInterestedPost(user_id=current_user.id, post_id=post_id)
        db.session.add(not_interested)
        db.session.commit()
        flash('Post marked as not interested', 'info')

    return redirect(request.referrer or url_for('main.index'))


@bp.route('/hide-post/<int:post_id>')
@login_required
def hide_post(post_id):
    post = db.session.get(Post, post_id)
    if not post:
        return jsonify({'error': 'Post not found'}), 404

    existing = HiddenPost.query.filter_by(user_id=current_user.id, post_id=post_id).first()
    if not existing:
        hidden = HiddenPost(user_id=current_user.id, post_id=post_id)
        db.session.add(hidden)
        db.session.commit()
        flash('Post hidden from your feed', 'info')

    return redirect(request.referrer or url_for('main.index'))
@bp.route('/block-user/<int:user_id>', methods=['POST'])
@login_required
def block_user(user_id):
    user_to_block = db.session.get(User, user_id)
    if not user_to_block:
        return jsonify({'error': 'User not found'}), 404

    if user_to_block.id == current_user.id:
        return jsonify({'error': 'Cannot block yourself'}), 400

    existing = BlockedUser.query.filter_by(blocker_id=current_user.id, blocked_id=user_id).first()
    if not existing:
        blocked = BlockedUser(blocker_id=current_user.id, blocked_id=user_id)
        db.session.add(blocked)

        if current_user.is_following(user_to_block):
            current_user.unfollow(user_to_block)

        if current_user.is_friend_with(user_to_block):
            current_user.friends.remove(user_to_block)
            user_to_block.friends.remove(current_user)

        db.session.commit()
        SecurityEvent.log(current_user.id, 'user_blocked', request.remote_addr,
                          f'Blocked user {user_to_block.username}')
        return jsonify({'success': True, 'message': f'Blocked {user_to_block.username}'})

    return jsonify({'error': 'User already blocked'}), 400

@bp.route('/unblock-user/<int:user_id>', methods=['POST'])
@login_required
def unblock_user(user_id):
    blocked = BlockedUser.query.filter_by(
        blocker_id=current_user.id,
        blocked_id=user_id
    ).first()

    if blocked:
        db.session.delete(blocked)
        db.session.commit()
        flash('User unblocked', 'success')

    return redirect(url_for('main.user', username=current_user.username))


@bp.route('/user/<username>/media')
@login_required
def user_media(username):
    user = db.first_or_404(sa.select(User).where(User.username == username))

    posts_with_media = Post.query.filter(
        Post.user_id == user.id,
        Post.media_items.any()
    ).order_by(Post.timestamp.desc()).all()

    all_media = []
    for post in posts_with_media:
        for media in post.media_items:
            all_media.append({
                'id': media.id,
                'url': media.media_url,
                'type': media.media_type,
                'post_id': post.id,
                'timestamp': post.timestamp
            })

    return render_template('user_media.html', title=f"{user.username}'s Media",
                           user=user, media_items=all_media)

@bp.route('/add_story', methods=['POST'])
@login_required
def add_story():
    media = request.files.get('media')
    caption = request.form.get('caption', '')

    if not media or not media.filename:
        flash('Please select a file.', 'warning')
        return redirect(url_for('main.index'))

    media_filename, media_type = save_media(media, 'stories')

    if not media_filename:
        flash('Failed to upload media. Please check file format and size.', 'danger')
        return redirect(url_for('main.index'))

    story = Story(
        user_id=current_user.id,
        media_url=media_filename,
        media_type=media_type,
        caption=caption,
        timestamp=datetime.now(timezone.utc),
        expires_at=datetime.now(timezone.utc) + timedelta(hours=24)
    )
    db.session.add(story)
    db.session.commit()

    flash('Story added! It will disappear in 24 hours.', 'success')
    return redirect(url_for('main.index'))


@bp.route('/for-you')
@login_required
def for_you():
    page = request.args.get('page', 1, type=int)
    limit = current_app.config.get('POSTS_PER_PAGE', 25)

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

    return render_template('for_you.html', title='For You', posts=posts,
                           is_personalized=is_personalized, next_url=next_url, prev_url=prev_url)


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

    return render_template('discover.html', title='Discover', posts=posts,
                           suggested_users=suggested, next_url=next_url, prev_url=prev_url)


@bp.route('/trending')
@login_required
def trending_feed():
    page = request.args.get('page', 1, type=int)
    limit = current_app.config.get('POSTS_PER_PAGE', 25)

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

    return render_template('trending_feed.html', title='Trending', posts=posts,
                           next_url=next_url, prev_url=prev_url)


@bp.route('/trending-feed')
@login_required
def trending_feed_smart():
    page = request.args.get('page', 1, type=int)
    limit = current_app.config.get('POSTS_PER_PAGE', 25)

    week_ago = datetime.now(timezone.utc) - timedelta(days=7)

    posts = db.session.query(Post).filter(
        Post.timestamp > week_ago,
        Post.privacy == 'public',
        Post.scheduled_for == None
    ).all()

    for post in posts:
        post.trending_score()

    posts.sort(key=lambda p: p.trending_score_cache, reverse=True)

    start = (page - 1) * limit
    end = start + limit
    paginated_posts = posts[start:end]

    next_url = url_for('main.trending_feed_smart', page=page + 1) if len(posts) > end else None
    prev_url = url_for('main.trending_feed_smart', page=page - 1) if page > 1 else None

    return render_template('trending_feed.html', title='Trending (Smart)',
                           posts=paginated_posts, next_url=next_url, prev_url=prev_url)


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

    return render_template('following_feed.html', title='Following', posts=posts,
                           next_url=next_url, prev_url=prev_url)


@bp.route('/search')
@login_required
def search():
    if not g.search_form.validate():
        return redirect(url_for('main.explore'))

    query = g.search_form.q.data
    page = request.args.get('page', 1, type=int)

    search_query = sa.select(Post).where(
        sa.or_(Post.body.ilike(f'%{query}%'), Post.body.contains(query)),
        Post.scheduled_for == None
    ).order_by(Post.timestamp.desc())

    posts = db.paginate(search_query, page=page,
                        per_page=current_app.config['POSTS_PER_PAGE'],
                        error_out=False)

    next_url = url_for('main.search', q=query, page=posts.next_num) if posts.has_next else None
    prev_url = url_for('main.search', q=query, page=posts.prev_num) if posts.has_prev else None

    users = db.session.scalars(
        sa.select(User).where(
            sa.or_(User.username.ilike(f'%{query}%'), User.about_me.ilike(f'%{query}%'))
        ).limit(10)
    ).all()

    return render_template('search.html', title='Search', posts=posts.items, users=users,
                           query=query, next_url=next_url, prev_url=prev_url)


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

    media_items = []
    posts_with_media = Post.query.filter(
        Post.user_id == user.id,
        Post.media_items.any()
    ).order_by(Post.timestamp.desc()).all()

    for post in posts_with_media:
        for media in post.media_items:
            media_items.append({
                'id': media.id,
                'url': media.media_url,
                'type': media.media_type,
                'post_id': post.id,
                'likes_count': post.like_count(),
                'comments_count': post.comment_count()
            })

    liked_posts = []
    user_likes = Like.query.filter_by(user_id=user.id).order_by(Like.timestamp.desc()).all()

    for like in user_likes:
        post = Post.query.get(like.post_id)
        if post:
            liked_posts.append(post)

    next_url = url_for('main.user', username=user.username, page=posts.next_num) if posts.has_next else None
    prev_url = url_for('main.user', username=user.username, page=posts.prev_num) if posts.has_prev else None
    form = EmptyForm()

    return render_template('user.html',
                           user=user,
                           posts=posts.items,
                           media_items=media_items,
                           liked_posts=liked_posts,
                           next_url=next_url,
                           prev_url=prev_url,
                           form=form)

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

    if request.method == 'POST':
        print("=== DEBUG: Edit Profile POST ===")
        print(f"Profile pic file: {request.files.get('profile_pic')}")
        print(f"Cover pic file: {request.files.get('cover_pic')}")

    if form.validate_on_submit():
        print("=== DEBUG: Form validated ===")

        current_user.username = form.username.data
        current_user.about_me = form.about_me.data
        current_user.is_private = form.is_private.data == 'True'

        current_user.relationship_status = form.relationship_status.data
        current_user.work = form.work.data
        current_user.education = form.education.data
        current_user.location = form.location.data
        current_user.website = form.website.data
        current_user.birthday = form.birthday.data
        current_user.gender = form.gender.data
        current_user.interested_in = form.interested_in.data
        current_user.phone = form.phone.data

        if form.profile_pic.data and form.profile_pic.data.filename:
            print(f"Profile pic filename: {form.profile_pic.data.filename}")
            old_pic = current_user.profile_pic
            new_pic = save_profile_picture(form.profile_pic.data, old_pic)
            if new_pic:
                current_user.profile_pic = new_pic
                print(f"Profile pic saved as: {new_pic}")
            else:
                print("ERROR: Failed to save profile picture")

        if form.cover_pic.data and form.cover_pic.data.filename:
            print(f"Cover pic filename: {form.cover_pic.data.filename}")
            old_cover = current_user.cover_pic
            new_cover = save_cover_picture(form.cover_pic.data, old_cover)
            if new_cover:
                current_user.cover_pic = new_cover
                print(f"Cover pic saved as: {new_cover}")
            else:
                print("ERROR: Failed to save cover picture")

        db.session.commit()
        print("=== DEBUG: Changes committed ===")
        flash('Your changes have been saved.', 'success')
        return redirect(url_for('main.user', username=current_user.username))

    elif request.method == 'GET':
        form.username.data = current_user.username
        form.about_me.data = current_user.about_me
        form.is_private.data = str(current_user.is_private)

        form.relationship_status.data = current_user.relationship_status
        form.work.data = current_user.work
        form.education.data = current_user.education
        form.location.data = current_user.location
        form.website.data = current_user.website
        form.birthday.data = current_user.birthday
        form.gender.data = current_user.gender
        form.interested_in.data = current_user.interested_in
        form.phone.data = current_user.phone

    return render_template('edit_profile.html', title='Edit Profile', form=form)

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

        from app.notification_helper import create_notification
        create_notification(
            user.id,
            'follow',
            {
                'from_user': current_user.username,
                'user_id': current_user.id,
                'message': f'{current_user.username} started following you'
            }
        )
        print(f"Created follow notification for user {user.id} from {current_user.username}")

        flash(f'You are following {username}!')
        return redirect(url_for('main.user', username=username))
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
    return redirect(url_for('main.index'))


@bp.route('/like/<int:post_id>')
@login_required
def like_post(post_id):
    post = db.session.get(Post, post_id)
    if post is None:
        return jsonify({'error': 'Post not found'}), 404

    existing = db.session.scalar(
        sa.select(Like).where(Like.user_id == current_user.id, Like.post_id == post_id)
    )

    liked = False

    if not existing:
        like = Like(user_id=current_user.id, post_id=post_id)
        db.session.add(like)
        post.author.points += 1
        liked = True
        if post.author.id != current_user.id:
            from app.notification_helper import create_notification
            create_notification(
                post.author.id,
                'like',
                {
                    'from_user': current_user.username,
                    'user_id': current_user.id,
                    'post_id': post.id,
                    'message': f'{current_user.username} liked your post'
                }
            )
    else:
        db.session.delete(existing)
        liked = False

    db.session.commit()
    like_count = post.like_count()
    return jsonify({'liked': liked, 'count': like_count})

@bp.route('/post/<int:post_id>')
@login_required
def view_post(post_id):
    post = db.session.get(Post, post_id)
    if post is None:
        flash('Post not found.')
        return redirect(url_for('main.index'))

    return render_template('post_detail.html', title='Post', post=post)


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


@bp.route('/share_post/<int:post_id>', methods=['POST'])
@login_required
def share_post(post_id):
    original_post = db.session.get(Post, post_id)
    if original_post is None:
        flash('Post not found.')
        return redirect(url_for('main.index'))

    shared_post = SharedPost(original_post_id=post_id, shared_by_id=current_user.id)
    db.session.add(shared_post)
    original_post.share_count += 1

    share_post = Post(body=f"Shared a post from @{original_post.author.username}",
                      author=current_user, privacy='public')
    db.session.add(share_post)
    db.session.commit()
    flash('Post shared!', 'success')
    return redirect(url_for('main.index'))


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

    reaction_set = False

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
        if reaction == 'like':
            existing_like = Like.query.filter_by(user_id=current_user.id, post_id=post_id).first()
            if not existing_like:
                new_like = Like(user_id=current_user.id, post_id=post_id)
                db.session.add(new_like)

    db.session.commit()

    reaction_counts = post.get_reaction_counts()
    return jsonify({
        'reaction_set': reaction_set,
        'reaction': reaction if reaction_set else None,
        'counts': reaction_counts,
        'total': sum(reaction_counts.values())
    })

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


@bp.route('/delete_post/<int:post_id>', methods=['POST'])
@login_required
def delete_post(post_id):
    post = db.session.get(Post, post_id)
    if post is None:
        flash('Post not found.')
        return redirect(url_for('main.index'))

    if post.author != current_user and not current_user.is_admin:
        flash('You cannot delete this post.')
        return redirect(url_for('main.index'))

    Like.query.filter_by(post_id=post_id).delete()

    PostReaction.query.filter_by(post_id=post_id).delete()

    Comment.query.filter_by(post_id=post_id).delete()

    SavedPost.query.filter_by(post_id=post_id).delete()

    SharedPost.query.filter_by(original_post_id=post_id).delete()

    NotInterestedPost.query.filter_by(post_id=post_id).delete()
    InterestedPost.query.filter_by(post_id=post_id).delete()

    HiddenPost.query.filter_by(post_id=post_id).delete()

    SpamReport.query.filter_by(post_id=post_id).delete()

    for media in post.media_items.all():
        delete_media(media.media_url, 'posts')
        db.session.delete(media)

    db.session.delete(post)
    db.session.commit()
    flash('Your post has been deleted.', 'info')
    return redirect(url_for('main.index'))


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

        media_to_keep = request.form.getlist('keep_media')
        for media in post.media_items.all():
            if str(media.id) not in media_to_keep:
                delete_media(media.media_url, 'posts')
                db.session.delete(media)

        if 'media_files' in request.files:
            files = request.files.getlist('media_files')
            saved_media = save_multiple_media(files, 'posts')
            current_order = post.media_items.count()
            for idx, media in enumerate(saved_media):
                post_media = PostMedia(
                    post_id=post.id,
                    media_url=media['filename'],
                    media_type=media['media_type'],
                    order=current_order + idx
                )
                db.session.add(post_media)

        db.session.commit()
        flash('Post updated!', 'success')
        return redirect(url_for('main.index'))

    form.post.data = post.body
    return render_template('edit_post.html', title='Edit Post', form=form, post=post)


@bp.route('/send_chat_message', methods=['POST'])
@login_required
def send_chat_message():
    try:
        recipient_id = request.form.get('recipient_id', type=int)
        message = request.form.get('message', '').strip()
        reply_to_id = request.form.get('reply_to_id', type=int)

        if not recipient_id:
            return jsonify({'error': 'Recipient not specified'}), 400

        recipient = db.session.get(User, recipient_id)
        if recipient is None:
            return jsonify({'error': 'User not found'}), 404

        image_url = None
        if 'image' in request.files:
            file = request.files['image']
            if file and file.filename:
                import os
                import uuid
                from flask import current_app

                filename = str(uuid.uuid4()) + '.' + file.filename.rsplit('.', 1)[1].lower()
                upload_path = os.path.join(current_app.config['UPLOAD_FOLDER'], 'chat')
                os.makedirs(upload_path, exist_ok=True)
                file_path = os.path.join(upload_path, filename)
                file.save(file_path)
                image_url = f'/static/uploads/chat/{filename}'

        audio_url = None
        if 'audio' in request.files:
            audio_file = request.files['audio']
            if audio_file and audio_file.filename:
                import os
                import uuid
                from flask import current_app

                ext = audio_file.filename.rsplit('.', 1)[1].lower() if '.' in audio_file.filename else 'webm'
                filename = str(uuid.uuid4()) + '.' + ext

                audio_path = os.path.join(current_app.config['UPLOAD_FOLDER'], 'chat', 'audio')
                os.makedirs(audio_path, exist_ok=True)

                file_path = os.path.join(audio_path, filename)
                audio_file.save(file_path)
                audio_url = f'/static/uploads/chat/audio/{filename}'

        chat_message = ChatMessage(
            sender_id=current_user.id,
            recipient_id=recipient_id,
            message=message,
            image_url=image_url,
            audio_url=audio_url,
            is_read=False,
            is_delivered=False,
            reply_to_id=reply_to_id,
            reactions='{}',
            timestamp=datetime.now(timezone.utc)
        )
        db.session.add(chat_message)
        db.session.commit()

        return jsonify({
            'success': True,
            'message': message,
            'image_url': image_url,
            'audio_url': audio_url,  # <-- ADDED
            'timestamp': chat_message.timestamp.timestamp(),
            'message_id': chat_message.id,
            'reply_to_id': reply_to_id
        })
    except Exception as e:
        current_app.logger.error(f"Send message error: {e}")
        return jsonify({'error': str(e)}), 500


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

    import json
    result = []
    for m in messages:
        result.append({
            'id': m.id,
            'sender_id': m.sender_id,
            'message': m.message,
            'image_url': m.image_url,
            'audio_url': m.audio_url,
            'timestamp': m.timestamp.timestamp(),
            'is_mine': m.sender_id == current_user.id,
            'status': 'seen' if m.is_read else ('delivered' if m.is_delivered else 'sent'),
            'reply_to_id': m.reply_to_id,
            'reactions': json.loads(m.reactions) if m.reactions else {}
        })

    db.session.execute(
        sa.update(ChatMessage)
        .where(
            ChatMessage.sender_id == other_user_id,
            ChatMessage.recipient_id == current_user.id,
            ChatMessage.is_read == False
        )
        .values(is_read=True, is_delivered=True)
    )
    db.session.commit()

    return jsonify(result)

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


@bp.route('/view_story/<int:story_id>')
@login_required
def view_story(story_id):
    story = db.session.get(Story, story_id)
    if story is None:
        flash('Story not found.')
        return redirect(url_for('main.index'))

    expires_at = story.expires_at
    if expires_at.tzinfo is None:
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


@bp.route('/notifications')
@login_required
def notifications():
    try:
        query = current_user.notifications.select().where(Notification.read == False)
        unread_count = db.session.scalar(sa.select(sa.func.count()).select_from(query.subquery()))
        return jsonify({'count': unread_count or 0})
    except Exception as e:
        current_app.logger.error(f"Notification count error: {e}")
        return jsonify({'count': 0})
@bp.route('/notifications-list')
@login_required
def notifications_list():
    try:
        notifications = db.session.scalars(
            current_user.notifications.select().order_by(Notification.timestamp.desc()).limit(50)
        ).all()

        result = []
        for n in notifications:
            data = n.get_data()

            if not isinstance(data, dict):
                data = {}

            from_user = data.get('from_user') or data.get('username') or 'Someone'
            post_id = data.get('post_id')
            comment = data.get('comment', '')
            message = data.get('message', '')

            result.append({
                'id': n.id,
                'name': n.name,
                'from_user': str(from_user),
                'post_id': post_id if isinstance(post_id, int) else None,
                'comment': str(comment)[:100] if comment else '',
                'message': str(message)[:100] if message else '',
                'timestamp': n.timestamp
            })

        return jsonify(result)
    except Exception as e:
        current_app.logger.error(f"Notifications list error: {e}")
        return jsonify([])

@bp.route('/clear-notifications', methods=['POST'])
@login_required
def clear_notifications():
    try:
        from datetime import datetime, timedelta
        week_ago = datetime.now().timestamp() - (7 * 24 * 60 * 60)

        current_user.notifications.delete().where(
            Notification.timestamp < week_ago
        )
        db.session.commit()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False})


@bp.route('/mark-notification-read/<int:notification_id>', methods=['POST'])
@login_required
def mark_notification_read(notification_id):
    try:
        notification = Notification.query.get(notification_id)
        if notification and notification.user_id == current_user.id:
            setattr(notification, 'read', True)
            db.session.commit()
            return jsonify({'success': True})
    except Exception as e:
        current_app.logger.error(f"Error marking notification read: {e}")
    return jsonify({'success': False})


@bp.route('/mark-all-notifications-read', methods=['POST'])
@login_required
def mark_all_notifications_read():
    try:
        for notification in current_user.notifications.all():
            setattr(notification, 'read', True)
        db.session.commit()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False})


@bp.route('/notifications-page')
@login_required
def notifications_page():
    try:
        query = current_user.notifications.select().where(Notification.read == False)
        notifications = db.session.scalars(query).all()
        for notif in notifications:
            notif.read = True
        db.session.commit()
    except Exception as e:
        current_app.logger.error(f"Error marking notifications as read: {e}")

    return render_template('notifications.html', title='Activity')

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


@bp.route('/report_post/<int:post_id>', methods=['GET', 'POST'])
@login_required
def report_post(post_id):
    post = db.session.get(Post, post_id)
    if post is None:
        flash('Post not found.')
        return redirect(url_for('main.index'))

    form = ReportForm()
    if form.validate_on_submit():
        existing_report = SpamReport.query.filter_by(post_id=post_id, reporter_id=current_user.id).first()
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
        report_service.generate_reports_summary()
        report_service.generate_users_report()
        report_service.generate_posts_report()

        flash('Thank you for your report. An admin will review it.', 'success')
        return redirect(url_for('main.index'))

    return render_template('report_post.html', title='Report Post', form=form, post=post)


@bp.route('/admin/reports')
@login_required
@admin_required
def view_reports():
    page = request.args.get('page', 1, type=int)
    reports = db.session.query(SpamReport).filter(
        SpamReport.reviewed == False
    ).order_by(SpamReport.timestamp.desc()).paginate(page=page, per_page=20, error_out=False)
    return render_template('admin/reports.html', title='User Reports', reports=reports)


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


@bp.route('/admin/reports/csv/users')
@login_required
@admin_required
def download_users_report():
    filepath, filename = report_service.generate_users_report()
    return send_file(filepath, as_attachment=True, download_name=filename, mimetype='text/csv')


@bp.route('/admin/reports/csv/posts')
@login_required
@admin_required
def download_posts_report():
    filepath, filename = report_service.generate_posts_report()
    return send_file(filepath, as_attachment=True, download_name=filename, mimetype='text/csv')


@bp.route('/admin/reports/csv/reports')
@login_required
@admin_required
def download_reports_summary():
    filepath, filename = report_service.generate_reports_summary()
    return send_file(filepath, as_attachment=True, download_name=filename, mimetype='text/csv')


@bp.route('/admin/reports/csv/engagement')
@login_required
@admin_required
def download_engagement_report():
    filepath, filename = report_service.generate_engagement_report()
    return send_file(filepath, as_attachment=True, download_name=filename, mimetype='text/csv')


@bp.route('/admin/report-dashboard')
@login_required
@admin_required
def report_dashboard():
    reports = report_service.get_all_reports()
    return render_template('admin/report_dashboard.html', title='Reports', reports=reports)


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
    for media in post.media_items.all():
        delete_media(media.media_url, 'posts')

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
    return render_template('admin/flagged.html', title='Flagged Posts History', posts=posts.items,
                           next_url=next_url, prev_url=prev_url)


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


@bp.route('/trending-hashtags')
def trending_hashtags():
    trending_hashtags = db.session.scalars(
        sa.select(Hashtag).order_by(Hashtag.post_count.desc()).limit(10)
    ).all()
    return jsonify([{'name': h.name, 'post_count': h.post_count} for h in trending_hashtags])

@bp.route('/translate', methods=['POST'])
@login_required
def translate_text():
    data = request.get_json()
    return {'text': translate(data['text'], data['source_language'], data['dest_language'])}


@bp.route('/export_posts')
@login_required
def export_posts():
    if current_user.get_task_in_progress('export_posts'):
        flash('An export task is currently in progress')
    else:
        current_user.launch_task('export_posts', 'Exporting posts...')
        db.session.commit()
    return redirect(url_for('main.user', username=current_user.username))


from datetime import datetime, timezone


@bp.route('/react_story/<int:story_id>/<reaction>', methods=['POST'])
@login_required
def react_story(story_id, reaction):
    story = db.session.get(Story, story_id)
    if not story:
        return jsonify({'success': False, 'error': 'Story not found'}), 404

    existing = db.session.scalar(
        sa.select(StoryReaction).where(
            StoryReaction.user_id == current_user.id,
            StoryReaction.story_id == story_id
        )
    )

    if existing:
        if existing.reaction == reaction:
            db.session.delete(existing)
        else:
            existing.reaction = reaction
    else:
        new_reaction = StoryReaction(
            user_id=current_user.id,
            story_id=story_id,
            reaction=reaction
        )
        db.session.add(new_reaction)

    db.session.commit()

    reaction_count = db.session.query(StoryReaction).filter_by(story_id=story_id).count()

    return jsonify({'success': True, 'reaction_count': reaction_count})

@bp.route('/send_story_comment', methods=['POST'])
@login_required
def send_story_comment():
    data = request.get_json()
    story_id = data.get('story_id')
    message = data.get('message', '').strip()

    if not message:
        return jsonify({'success': False, 'error': 'Message cannot be empty'}), 400

    story = db.session.get(Story, story_id)
    if not story:
        return jsonify({'success': False, 'error': 'Story not found'}), 404

    comment = StoryComment(
        story_id=story_id,
        user_id=current_user.id,
        message=message
    )
    db.session.add(comment)
    db.session.commit()

    return jsonify({'success': True})


@bp.route('/get_story_comments/<int:story_id>')
@login_required
def get_story_comments(story_id):
    comments = db.session.scalars(
        sa.select(StoryComment)
        .where(StoryComment.story_id == story_id)
        .order_by(StoryComment.timestamp.asc())
    ).all()

    def time_ago(dt):
        now = datetime.now(timezone.utc)
        diff = now - dt

        if diff.days > 0:
            return f'{diff.days}d ago'
        if diff.seconds > 3600:
            return f'{diff.seconds // 3600}h ago'
        if diff.seconds > 60:
            return f'{diff.seconds // 60}m ago'
        return 'Just now'

    return jsonify([{
        'id': c.id,
        'author_name': c.author.username,
        'author_avatar': c.author.avatar(32),
        'message': c.message,
        'time_ago': time_ago(c.timestamp)
    } for c in comments])


@bp.route('/send-friend-request/<int:user_id>', methods=['POST'])
@login_required
def send_friend_request(user_id):
    user = db.session.get(User, user_id)
    if not user or user == current_user:
        flash('Invalid user', 'danger')
        return redirect(url_for('main.index'))

    if current_user.is_friend_with(user):
        flash(f'You are already friends with {user.username}', 'warning')
        return redirect(url_for('main.user', username=user.username))

    existing_request = FriendRequest.query.filter(
        ((FriendRequest.from_user_id == current_user.id) & (FriendRequest.to_user_id == user.id)) |
        ((FriendRequest.from_user_id == user.id) & (FriendRequest.to_user_id == current_user.id))
    ).first()

    if existing_request:
        if existing_request.status == 'pending':
            flash(f'Friend request already pending', 'warning')
        elif existing_request.status == 'accepted':
            flash(f'You are already friends with {user.username}', 'warning')
        else:
            flash(f'Friend request was rejected', 'info')
        return redirect(url_for('main.user', username=user.username))

    if current_user.send_friend_request(user):
        from app.notification_helper import create_notification
        create_notification(
            user_id=user.id,
            type='friend_request',
            message=f'{current_user.username} sent you a friend request',
            link=url_for('main.friend_requests_page')
        )
        flash(f'Friend request sent to {user.username}', 'success')
    else:
        flash('Unable to send friend request', 'danger')

    return redirect(url_for('main.user', username=user.username))

@bp.route('/accept-friend-request/<int:request_id>', methods=['POST'])
@login_required
def accept_friend_request(request_id):
    try:
        friend_request = db.session.get(FriendRequest, request_id)
        if friend_request and friend_request.to_user_id == current_user.id:
            current_user.accept_friend_request(friend_request)
            friend_request.from_user.add_notification('friend_accepted', {
                'from_user': current_user.username,
                'user_id': current_user.id,
                'message': f'{current_user.username} accepted your friend request'
            })
            db.session.commit()
            return jsonify({'success': True, 'message': 'Friend request accepted!'})
        return jsonify({'error': 'Invalid request'}), 400
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@bp.route('/reject-friend-request/<int:request_id>', methods=['POST'])
@login_required
def reject_friend_request(request_id):
    try:
        friend_request = db.session.get(FriendRequest, request_id)
        if friend_request and friend_request.to_user_id == current_user.id:
            current_user.reject_friend_request(friend_request)
            db.session.commit()
            return jsonify({'success': True, 'message': 'Friend request rejected'})
        return jsonify({'error': 'Invalid request'}), 400
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/remove-friend/<int:user_id>', methods=['POST'])
@login_required
def remove_friend(user_id):
    user = db.session.get(User, user_id)
    if user and current_user.is_friend_with(user):
        current_user.friends.remove(user)
        user.friends.remove(current_user)
        db.session.commit()
        flash(f'Removed {user.username} from friends', 'success')
    return redirect(url_for('main.friends'))


@bp.route('/friends')
@login_required
def friends():
    page = request.args.get('page', 1, type=int)
    friends_list = current_user.get_friends()

    # Manual pagination
    per_page = 20
    total = len(friends_list)
    start = (page - 1) * per_page
    end = start + per_page
    paginated_friends = friends_list[start:end]

    has_next = total > end
    has_prev = page > 1

    form = EmptyForm()

    return render_template('friends.html', title='Friends',
                           friends=paginated_friends,
                           form=form,
                           page=page,
                           has_next=has_next,
                           has_prev=has_prev)

@bp.route('/friend-requests')
@login_required
def friend_requests_page():
    pending_requests = current_user.get_pending_friend_requests()
    return render_template('friend_requests.html', title='Friend Requests', requests=pending_requests)
@bp.route('/feeds')
@login_required
def feeds():
    page = request.args.get('page', 1, type=int)
    friends_ids = [f.id for f in current_user.get_friends()]
    posts_query = sa.select(Post).where(
        Post.user_id.in_(friends_ids),
        Post.is_spam == False,
        Post.approved == True
    ).order_by(Post.timestamp.desc())
    posts = db.paginate(posts_query, page=page, per_page=20, error_out=False)
    return render_template('feeds.html', title='Friends Feed', posts=posts)


@bp.route('/memories')
@login_required
def memories():
    from datetime import datetime
    today = datetime.utcnow().date()

    posts = db.session.scalars(
        sa.select(Post).where(
            Post.user_id == current_user.id,
            sa.extract('day', Post.timestamp) == today.day,
            sa.extract('month', Post.timestamp) == today.month
        ).order_by(Post.timestamp.desc())
    ).all()

    return render_template('memories.html', title='Memories', posts=posts)


@bp.route('/active-contacts')
@login_required
def get_active_contacts():
    active_friends = current_user.get_active_friends_online()
    contacts_data = [{
        'id': f.id,
        'username': f.username,
        'avatar': f.avatar(32),
        'last_seen': f.last_seen.isoformat() if f.last_seen else None
    } for f in active_friends]
    return jsonify(contacts_data)


@bp.route('/groups')
@login_required
def groups():
    return render_template('groups.html', title='Groups')


@bp.route('/events')
@login_required
def events():
    return render_template('events.html', title='Events')


@bp.route('/reels')
@login_required
def reels():
    return render_template('reels.html', title='Reels')


@bp.route('/gaming')
@login_required
def gaming():
    return render_template('gaming.html', title='Gaming Video')


@bp.route('/ads-manager')
@login_required
def ads_manager():
    return render_template('ads_manager.html', title='Ads Manager')


@bp.route('/birthdays')
@login_required
def birthdays():
    from datetime import datetime, timedelta

    today = datetime.now(timezone.utc).date()
    next_week = today + timedelta(days=7)

    all_users = db.session.execute(
        sa.select(User).where(User.id != current_user.id)
    ).scalars().all()

    upcoming_birthdays = []
    for user in all_users:
        if user.birthday:
            try:
                birthday_date = datetime.strptime(user.birthday, '%Y-%m-%d').date()
                birthday_this_year = birthday_date.replace(year=today.year)
                if birthday_this_year < today:
                    birthday_this_year = birthday_date.replace(year=today.year + 1)

                days_until = (birthday_this_year - today).days
                if 0 <= days_until <= 7:
                    upcoming_birthdays.append({
                        'user': user,
                        'days_until': days_until,
                        'birthday': birthday_date
                    })
            except:
                pass

    upcoming_birthdays.sort(key=lambda x: x['days_until'])

    return render_template('birthdays.html', title='Birthdays', birthdays=upcoming_birthdays)


@bp.route('/share-post-to-story/<int:post_id>', methods=['POST'])
@login_required
def share_post_to_story(post_id):
    post = db.session.get(Post, post_id)
    if not post:
        flash('Post not found.', 'danger')
        return redirect(url_for('main.index'))

    caption = request.form.get('caption', '')
    bg_color = request.form.get('bg_color', 'gradient-purple')

    story_caption = f"📌 Shared @{post.author.username}'s post\n\n"
    story_caption += f'"{post.body[:150]}"'
    if caption:
        story_caption += f"\n\n💭 {caption}"

    story = Story(
        user_id=current_user.id,
        media_url='',
        media_type='text',
        caption=story_caption,
        bg_color=bg_color,
        shared_post_id=post_id,
        timestamp=datetime.now(timezone.utc),
        expires_at=datetime.now(timezone.utc) + timedelta(hours=24)
    )

    db.session.add(story)
    db.session.commit()

    flash('Post shared to your story!', 'success')
    return redirect(url_for('main.index'))


@bp.route('/story-data/<int:story_id>')
@login_required
def get_story_data(story_id):
    story = db.session.get(Story, story_id)
    if not story:
        return jsonify({'error': 'Story not found'}), 404

    def time_ago(dt):
        now = datetime.now(timezone.utc)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        diff = now - dt
        if diff.days > 0:
            return f'{diff.days}d ago'
        if diff.seconds > 3600:
            return f'{diff.seconds // 3600}h ago'
        if diff.seconds > 60:
            return f'{diff.seconds // 60}m ago'
        return 'Just now'

    return jsonify({
        'id': story.id,
        'media_url': story.media_url,
        'media_type': story.media_type,
        'caption': story.caption or '',
        'author_name': story.author.username,
        'author_avatar': story.author.avatar(48),
        'time_ago': time_ago(story.timestamp),
        'reaction_count': db.session.query(StoryReaction).filter_by(story_id=story.id).count(),
        'bg_color': getattr(story, 'bg_color', 'gradient-purple'),
        'shared_post_id': getattr(story, 'shared_post_id', None)
    })
@bp.route('/settings/security')
@login_required
def security_settings():
    return render_template('security/security.html', title='Security Settings')


@bp.route('/settings/privacy')
@login_required
def privacy_settings():
    return render_template('security/privacy.html', title='Privacy Settings')


@bp.route('/settings/change-password', methods=['POST'])
@login_required
def change_password():
    current_password = request.form.get('current_password')
    new_password = request.form.get('new_password')
    confirm_password = request.form.get('confirm_password')

    if not current_user.check_password(current_password):
        flash('Current password is incorrect.', 'danger')
        return redirect(url_for('main.security_settings'))

    if new_password != confirm_password:
        flash('New passwords do not match.', 'danger')
        return redirect(url_for('main.security_settings'))

    if len(new_password) < 6:
        flash('Password must be at least 6 characters.', 'danger')
        return redirect(url_for('main.security_settings'))

    current_user.set_password(new_password)
    db.session.commit()
    flash('Your password has been changed.', 'success')
    return redirect(url_for('main.security_settings'))

@bp.route('/settings/disable-2fa', methods=['POST'])
@login_required
def disable_2fa():
    otp_code = request.form.get('otp_code')

    import pyotp
    if current_user.otp_secret and pyotp.TOTP(current_user.otp_secret).verify(otp_code):
        current_user.two_factor_enabled = False
        current_user.otp_secret = None
        db.session.commit()
        flash('Two-factor authentication has been disabled.', 'success')
    else:
        flash('Invalid OTP code.', 'danger')

    return redirect(url_for('main.security_settings'))


@bp.route('/settings/sessions')
@login_required
def session_management():
    from app.models import UserSession
    active_sessions = UserSession.query.filter_by(user_id=current_user.id, is_active=True).all()
    return render_template('security/sessions.html', title='Session Management', sessions=active_sessions)


@bp.route('/settings/login-history')
@login_required
def login_history():
    from app.models import LoginHistory
    page = request.args.get('page', 1, type=int)
    history = LoginHistory.query.filter_by(user_id=current_user.id).order_by(LoginHistory.timestamp.desc()).paginate(
        page=page, per_page=20)
    return render_template('security/login_history.html', title='Login History', history=history)


@bp.route('/settings/account', methods=['GET', 'POST'])
@login_required
def account_settings():
    if request.method == 'POST':
        current_user.username = request.form.get('username')
        current_user.about_me = request.form.get('about_me')
        current_user.work = request.form.get('work')
        current_user.education = request.form.get('education')
        current_user.location = request.form.get('location')
        current_user.website = request.form.get('website')
        current_user.phone = request.form.get('phone')
        current_user.birthday = request.form.get('birthday')
        current_user.gender = request.form.get('gender')
        current_user.relationship_status = request.form.get('relationship_status')
        current_user.interested_in = request.form.get('interested_in')

        if request.files.get('profile_pic') and request.files['profile_pic'].filename:
            from app.profile_helpers import save_profile_picture
            old_pic = current_user.profile_pic
            current_user.profile_pic = save_profile_picture(request.files['profile_pic'], old_pic)

        db.session.commit()
        flash('Your changes have been saved.', 'success')
        return redirect(url_for('main.account_settings'))

    return render_template('security/account.html', title='Account Settings')


@bp.route('/settings/blocked-users')
@login_required
def blocked_users_page():
    blocked_list = BlockedUser.query.filter_by(blocker_id=current_user.id).all()
    blocked_users = []
    for b in blocked_list:
        user = db.session.get(User, b.blocked_id)
        if user:
            user.blocked_at = b.timestamp
            blocked_users.append(user)
    return render_template('security/blocked_users.html', title='Blocked Users', blocked_users=blocked_users)


@bp.route('/settings/appearance')
@login_required
def appearance_settings():
    return render_template('security/appearance.html', title='Appearance Settings')


@bp.route('/settings/screen-protection')
@login_required
def screen_protection():
    return render_template('security/screen_protection.html', title='Screen Protection')


@bp.route('/settings/export-data')
@login_required
def export_data():
    import json
    from datetime import datetime

    user_data = {
        'username': current_user.username,
        'email': current_user.email,
        'about_me': current_user.about_me,
        'joined': current_user.last_seen.isoformat() if current_user.last_seen else None,
        'posts': [{'body': p.body, 'timestamp': p.timestamp.isoformat()} for p in current_user.posts.select().all()],
        'connections': [{'username': f.username} for f in current_user.get_friends()]
    }

    response = jsonify(user_data)
    response.headers[
        'Content-Disposition'] = f'attachment; filename=Zetravox_export_{datetime.now().strftime("%Y%m%d")}.json'
    return response


@bp.route('/settings/request-deletion', methods=['POST'])
@login_required
def request_deletion():
    from app.models import DataDeletionRequest

    existing = DataDeletionRequest.query.filter_by(user_id=current_user.id, status='pending').first()
    if existing:
        return jsonify({'status': 'pending', 'message': 'Deletion request already pending'})

    request_obj = DataDeletionRequest(
        user_id=current_user.id,
        request_ip=request.remote_addr,
        status='pending'
    )
    db.session.add(request_obj)
    db.session.commit()

    return jsonify({'status': 'pending', 'message': 'Deletion request submitted. You will be notified once processed.'})


@bp.route('/set-theme', methods=['POST'])
@login_required
def set_theme():
    data = request.get_json()
    theme = data.get('theme', 'light')
    current_user.theme_preference = theme
    db.session.commit()
    return jsonify({'success': True})

@bp.route('/settings/delete-account', methods=['POST'])
@login_required
def delete_account():
    from app.models import DataDeletionRequest

    existing = DataDeletionRequest.query.filter_by(user_id=current_user.id, status='pending').first()
    if existing:
        flash('Deletion request already pending.', 'warning')
        return redirect(url_for('main.security_settings'))

    request_obj = DataDeletionRequest(
        user_id=current_user.id,
        request_ip=request.remote_addr,
        status='pending'
    )
    db.session.add(request_obj)
    db.session.commit()

    flash('Your account deletion request has been submitted. An admin will review it.', 'info')
    return redirect(url_for('main.index'))


@bp.route('/settings/update-privacy', methods=['POST'])
@login_required
def update_privacy_settings():
    current_user.is_private = request.form.get('is_private') == 'on'
    current_user.show_email = request.form.get('show_email') == 'on'
    current_user.show_last_seen = request.form.get('show_last_seen') == 'on'
    current_user.allow_comments = request.form.get('allow_comments') == 'on'
    current_user.allow_messages = request.form.get('allow_messages') == 'on'

    db.session.commit()
    flash('Privacy settings updated successfully.', 'success')
    return redirect(url_for('main.privacy_settings'))


@bp.route('/settings/revoke-all-sessions', methods=['POST'])
@login_required
def revoke_all_sessions():
    from app.models import UserSession
    current_session_id = request.cookies.get('session')

    sessions = UserSession.query.filter_by(user_id=current_user.id, is_active=True).all()
    for session in sessions:
        if session.id != current_session_id:
            session.is_active = False

    db.session.commit()
    flash('All other sessions have been revoked.', 'success')
    return jsonify({'success': True})

@bp.route('/mark-messages-delivered/<int:sender_id>', methods=['POST'])
@login_required
def mark_messages_delivered(sender_id):
    db.session.execute(
        sa.update(ChatMessage)
        .where(
            ChatMessage.sender_id == sender_id,
            ChatMessage.recipient_id == current_user.id,
            ChatMessage.is_delivered == False
        )
        .values(is_delivered=True)
    )
    db.session.commit()
    return jsonify({'success': True})


@bp.route('/mark-messages-seen/<int:sender_id>', methods=['POST'])
@login_required
def mark_messages_seen(sender_id):
    db.session.execute(
        sa.update(ChatMessage)
        .where(
            ChatMessage.sender_id == sender_id,
            ChatMessage.recipient_id == current_user.id,
            ChatMessage.is_read == False
        )
        .values(is_read=True)
    )
    db.session.commit()
    return jsonify({'success': True})

@bp.route('/conversations-list-api')
@login_required
def conversations_list_api():
    try:
        sent = db.session.execute(
            sa.select(ChatMessage.recipient_id)
            .where(ChatMessage.sender_id == current_user.id)
            .distinct()
        ).scalars().all()

        received = db.session.execute(
            sa.select(ChatMessage.sender_id)
            .where(ChatMessage.recipient_id == current_user.id)
            .distinct()
        ).scalars().all()

        user_ids = set(sent) | set(received)

        conversations = []
        for uid in user_ids:
            user = db.session.get(User, uid)
            if user:
                last_msg = db.session.scalar(
                    sa.select(ChatMessage)
                    .where(
                        ((ChatMessage.sender_id == current_user.id) & (ChatMessage.recipient_id == uid)) |
                        ((ChatMessage.sender_id == uid) & (ChatMessage.recipient_id == current_user.id))
                    )
                    .order_by(ChatMessage.timestamp.desc())
                    .limit(1)
                )

                unread = db.session.scalar(
                    sa.select(sa.func.count())
                    .select_from(ChatMessage)
                    .where(
                        ChatMessage.sender_id == uid,
                        ChatMessage.recipient_id == current_user.id,
                        ChatMessage.is_read == False
                    )
                ) or 0

                conversations.append({
                    'user_id': user.id,
                    'username': user.username,
                    'avatar': user.avatar(50),
                    'is_online': user.is_online,
                    'last_message': last_msg.message[:50] if last_msg else 'No messages yet',
                    'last_message_time': last_msg.timestamp.timestamp() if last_msg else 0,
                    'unread_count': unread
                })

        # Sort by last message time (most recent first)
        conversations.sort(key=lambda x: x['last_message_time'], reverse=True)

        return jsonify(conversations)
    except Exception as e:
        current_app.logger.error(f"Conversations API error: {e}")
        return jsonify([])

@bp.route('/clear-chat/<int:user_id>', methods=['POST'])
@login_required
def clear_chat(user_id):
    try:
        db.session.execute(
            sa.delete(ChatMessage)
            .where(
                ((ChatMessage.sender_id == current_user.id) & (ChatMessage.recipient_id == user_id)) |
                ((ChatMessage.sender_id == user_id) & (ChatMessage.recipient_id == current_user.id))
            )
        )
        db.session.commit()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@bp.route('/unread-messages-count')
@login_required
def unread_messages_count():
    try:
        count = db.session.scalar(
            sa.select(sa.func.count())
            .select_from(ChatMessage)
            .where(
                ChatMessage.recipient_id == current_user.id,
                ChatMessage.is_read == False
            )
        ) or 0
        return jsonify({'count': count})
    except Exception as e:
        return jsonify({'count': 0})


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


@bp.route('/conversations')
@login_required
def conversations():
    sent = db.session.execute(
        sa.select(ChatMessage.recipient_id)
        .where(ChatMessage.sender_id == current_user.id)
        .distinct()
    ).scalars().all()

    received = db.session.execute(
        sa.select(ChatMessage.sender_id)
        .where(ChatMessage.recipient_id == current_user.id)
        .distinct()
    ).scalars().all()

    user_ids = set(sent) | set(received)

    conversation_list = []
    for uid in user_ids:
        user = db.session.get(User, uid)
        if user:
            last_msg = db.session.scalar(
                sa.select(ChatMessage)
                .where(
                    ((ChatMessage.sender_id == current_user.id) & (ChatMessage.recipient_id == uid)) |
                    ((ChatMessage.sender_id == uid) & (ChatMessage.recipient_id == current_user.id))
                )
                .order_by(ChatMessage.timestamp.desc())
                .limit(1)
            )

            unread = db.session.scalar(
                sa.select(sa.func.count())
                .select_from(ChatMessage)
                .where(
                    ChatMessage.sender_id == uid,
                    ChatMessage.recipient_id == current_user.id,
                    ChatMessage.is_read == False
                )
            ) or 0

            conversation_list.append({
                'user': user,
                'last_message': last_msg,
                'unread_count': unread
            })

    conversation_list.sort(key=lambda x: x['last_message'].timestamp if x['last_message'] else datetime.min,
                           reverse=True)

    return render_template('conversations.html', title='Messages', conversations=conversation_list)


@bp.route('/react-to-message/<int:message_id>', methods=['POST'])
@login_required
def react_to_message(message_id):
    try:
        data = request.get_json()
        reaction = data.get('reaction')
        valid_reactions = ['❤️', '👍', '😂', '😮']

        if not reaction or reaction not in valid_reactions:
            return jsonify({'success': False, 'error': 'Invalid reaction'}), 400

        message = db.session.get(ChatMessage, message_id)
        if not message:
            return jsonify({'success': False, 'error': 'Message not found'}), 404
        if message.sender_id != current_user.id and message.recipient_id != current_user.id:
            return jsonify({'success': False, 'error': 'Unauthorized'}), 403

        result = message.add_reaction(current_user.id, reaction)
        reaction_summary = message.reaction_summary

        if result['action'] in ['added', 'updated'] and message.sender_id != current_user.id:
            from app.notification_helper import create_notification
            create_notification(
                user_id=message.sender_id,
                type='message_reaction',
                message=f"{current_user.username} reacted {reaction} to your message",
                link=f"/chat/{message.sender_id if message.sender_id != current_user.id else message.recipient_id}"
            )

        return jsonify({
            'success': True,
            'action': result['action'],
            'reaction': reaction,
            'message_id': message_id,
            'reaction_summary': reaction_summary,
            'user_reaction': reaction if result['action'] != 'removed' else None
        })

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Message reaction error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@bp.route('/delete-message/<int:message_id>', methods=['DELETE'])
@login_required
def delete_message(message_id):
    try:
        message = db.session.get(ChatMessage, message_id)
        if not message:
            return jsonify({'success': False, 'error': 'Message not found'})

        if message.sender_id != current_user.id:
            return jsonify({'success': False, 'error': 'Unauthorized'})

        if message.image_url:
            import os
            file_path = os.path.join('app/static', message.image_url.lstrip('/'))
            if os.path.exists(file_path):
                os.remove(file_path)

        db.session.delete(message)
        db.session.commit()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@bp.route('/test-react/<int:message_id>')
@login_required
def test_react(message_id):
    return jsonify({'success': True, 'message': f'Test works for message {message_id}'})



@bp.route('/comment/<int:comment_id>/replies', methods=['GET'])
@login_required
def get_comment_replies(comment_id):
    try:
        comment = db.session.get(Comment, comment_id)
        if not comment:
            return jsonify({'error': 'Comment not found'}), 404

        replies = comment.replies.order_by(Comment.timestamp.asc()).all()

        replies_data = []
        for reply in replies:
            replies_data.append({
                'id': reply.id,
                'body': reply.body,
                'timestamp': reply.timestamp.isoformat(),
                'author': {
                    'id': reply.author.id,
                    'username': reply.author.username,
                    'avatar': reply.author.avatar(32)
                },
                'reaction_summary': reply.reaction_summary,
                'user_reaction': reply.get_user_reaction(current_user.id)
            })

        return jsonify({'success': True, 'replies': replies_data})

    except Exception as e:
        current_app.logger.error(f"Get comment replies error: {str(e)}")
        return jsonify({'error': str(e)}), 500


@bp.route('/add_comment/<int:post_id>', methods=['POST'])
@login_required
def add_comment(post_id):
    post = db.session.get(Post, post_id)
    if post is None:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'error': 'Post not found'}), 404
        flash('Post not found.')
        return redirect(url_for('main.index'))

    body = request.form.get('body', '').strip()
    if body:
        comment = Comment(body=body, user_id=current_user.id, post_id=post_id)
        db.session.add(comment)
        db.session.commit()

        if post.author.id != current_user.id:
            from app.notification_helper import create_notification
            create_notification(
                post.author.id,
                'comment',
                {
                    'from_user': current_user.username,
                    'user_id': current_user.id,
                    'post_id': post.id,
                    'comment': body[:100],
                    'message': f'{current_user.username} commented on your post'
                }
            )

        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({
                'success': True,
                'comment': {
                    'id': comment.id,
                    'body': comment.body,
                    'author': {
                        'username': comment.author.username,
                        'avatar': comment.author.avatar(32)
                    },
                    'timestamp': comment.timestamp.isoformat()
                }
            })

        flash('Comment added.', 'success')

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({'error': 'Comment body is empty'}), 400

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


@bp.route('/comment/<int:comment_id>/react', methods=['POST'])
@login_required
def comment_react(comment_id):
    try:
        data = request.get_json()
        reaction = data.get('reaction')

        valid_reactions = ['❤️', '👍', '😂', '😮', '😡']

        if not reaction or reaction not in valid_reactions:
            return jsonify({'success': False, 'error': 'Invalid reaction'}), 400

        comment = db.session.get(Comment, comment_id)
        if not comment:
            return jsonify({'success': False, 'error': 'Comment not found'}), 404

        result = comment.add_reaction(current_user.id, reaction)
        reaction_summary = comment.reaction_summary

        return jsonify({
            'success': True,
            'action': result['action'],
            'reaction': reaction,
            'comment_id': comment_id,
            'reaction_summary': reaction_summary,
            'user_reaction': reaction if result['action'] != 'removed' else None
        })

    except Exception as e:
        db.session.rollback()
        print(f"Comment reaction error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500


@bp.route('/comment/<int:comment_id>/reply', methods=['POST'])
@login_required
def comment_reply(comment_id):
    try:
        data = request.get_json()
        body = data.get('body', '').strip()

        if not body:
            return jsonify({'success': False, 'error': 'Reply cannot be empty'}), 400

        parent_comment = db.session.get(Comment, comment_id)
        if not parent_comment:
            return jsonify({'success': False, 'error': 'Comment not found'}), 404

        reply = Comment(
            body=body,
            user_id=current_user.id,
            post_id=parent_comment.post_id,
            parent_id=comment_id,
            timestamp=datetime.now(timezone.utc)
        )

        db.session.add(reply)
        db.session.commit()

        return jsonify({
            'success': True,
            'reply': {
                'id': reply.id,
                'body': reply.body,
                'timestamp': reply.timestamp.isoformat(),
                'author': {
                    'id': reply.author.id,
                    'username': reply.author.username,
                    'avatar': reply.author.avatar(32)
                }
            }
        })

    except Exception as e:
        db.session.rollback()
        print(f"Comment reply error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500


@bp.route('/comment/<int:comment_id>/delete', methods=['DELETE'])
@login_required
def delete_comment_api(comment_id):
    try:
        comment = db.session.get(Comment, comment_id)
        if not comment:
            return jsonify({'success': False, 'error': 'Comment not found'}), 404

        if comment.author.id != current_user.id and not current_user.is_admin:
            return jsonify({'success': False, 'error': 'Unauthorized'}), 403

        for reply in comment.replies.all():
            db.session.delete(reply)

        db.session.delete(comment)
        db.session.commit()

        return jsonify({'success': True})

    except Exception as e:
        db.session.rollback()
        print(f"Delete comment error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@bp.route('/api/users/<int:user_id>/followers')
@login_required
def api_get_followers(user_id):
    user = db.session.get(User, user_id)
    if not user:
        return jsonify({'error': 'User not found'}), 404

    followers_list = []
    query = user.followers.select()
    followers = db.session.scalars(query).all()

    for follower in followers:
        followers_list.append({
            'id': follower.id,
            'username': follower.username,
            'avatar': follower.avatar(48),
            'bio': follower.about_me or '',
            'is_following': current_user.is_following(follower)
        })

    return jsonify({'followers': followers_list})


@bp.route('/api/users/<int:user_id>/following')
@login_required
def api_get_following(user_id):
    user = db.session.get(User, user_id)
    if not user:
        return jsonify({'error': 'User not found'}), 404

    following_list = []
    query = user.following.select()
    following = db.session.scalars(query).all()

    for followed in following:
        following_list.append({
            'id': followed.id,
            'username': followed.username,
            'avatar': followed.avatar(48),
            'bio': followed.about_me or '',
            'is_following': current_user.is_following(followed)
        })

    return jsonify({'following': following_list})


@bp.route('/follow-from-modal/<int:user_id>', methods=['POST'])
@login_required
def follow_from_modal(user_id):
    user_to_follow = db.session.get(User, user_id)
    if not user_to_follow:
        return jsonify({'error': 'User not found'}), 404

    if user_to_follow.id == current_user.id:
        return jsonify({'error': 'Cannot follow yourself'}), 400

    if current_user.is_following(user_to_follow):
        current_user.unfollow(user_to_follow)
        action = 'unfollowed'
    else:
        current_user.follow(user_to_follow)
        action = 'followed'

    db.session.commit()

    return jsonify({'success': True, 'action': action})


@bp.route('/api/users/<int:user_id>/media')
@login_required
def api_get_user_media(user_id):
    user = db.session.get(User, user_id)
    if not user:
        return jsonify({'error': 'User not found'}), 404

    media_items = []
    posts = Post.query.filter(
        Post.user_id == user_id,
        Post.media_items.any()
    ).order_by(Post.timestamp.desc()).all()

    for post in posts:
        for media in post.media_items:
            media_items.append({
                'id': media.id,
                'url': media.media_url,
                'type': media.media_type,
                'post_id': post.id,
                'likes_count': post.like_count(),
                'comments_count': post.comment_count(),
                'timestamp': post.timestamp.isoformat()
            })

    return jsonify({'media': media_items})


@bp.route('/api/users/<int:user_id>/liked-posts')
@login_required
def api_get_liked_posts(user_id):
    user = db.session.get(User, user_id)
    if not user:
        return jsonify({'error': 'User not found'}), 404

    liked_posts = db.session.query(Post).join(
        Like, Like.post_id == Post.id
    ).filter(
        Like.user_id == user_id,
        Post.is_spam == False,
        Post.approved == True
    ).order_by(Like.timestamp.desc()).all()

    posts_data = []
    for post in liked_posts:
        posts_data.append({
            'id': post.id,
            'body': post.body,
            'timestamp': post.timestamp.isoformat(),
            'author': {
                'id': post.author.id,
                'username': post.author.username,
                'avatar': post.author.avatar(48),
                'is_verified': post.author.is_verified
            },
            'likes_count': post.like_count(),
            'comments_count': post.comment_count(),
            'media_items': [{
                'url': m.media_url,
                'type': m.media_type
            } for m in post.media_items.all()] if post.media_items.count() > 0 else [],
            'user_reaction': post.user_reaction(current_user.id) if current_user.is_authenticated else None,
            'reaction_counts': post.get_reaction_counts()
        })

    return jsonify({'liked_posts': posts_data})


@bp.route('/follow-user/<int:user_id>', methods=['POST'])
@login_required
def follow_user(user_id):
    user_to_follow = db.session.get(User, user_id)
    if not user_to_follow:
        return jsonify({'error': 'User not found'}), 404

    if user_to_follow.id == current_user.id:
        return jsonify({'error': 'Cannot follow yourself'}), 400

    current_user.follow(user_to_follow)
    db.session.commit()

    return jsonify({'success': True})


@bp.route('/api/debug/followers/<int:user_id>')
@login_required
def debug_followers(user_id):
    user = db.session.get(User, user_id)
    if not user:
        return jsonify({'error': 'User not found'}), 404

    followers_count = user.followers_count()
    following_count = user.following_count()

    followers_list = []
    for follower in user.followers.all():
        followers_list.append(follower.username)

    following_list = []
    for followed in user.following.all():
        following_list.append(followed.username)

    return jsonify({
        'username': user.username,
        'followers_count': followers_count,
        'following_count': following_count,
        'followers': followers_list,
        'following': following_list
    })


@bp.route('/api/debug/likes/<int:user_id>')
@login_required
def debug_likes(user_id):
    from app.models import Like
    user = db.session.get(User, user_id)
    if not user:
        return jsonify({'error': 'User not found'}), 404

    likes = Like.query.filter_by(user_id=user_id).all()

    liked_posts_data = []
    for like in likes:
        post = like.post
        liked_posts_data.append({
            'post_id': post.id if post else None,
            'post_body': post.body[:100] if post else 'Post deleted',
            'liked_at': like.timestamp.isoformat() if like.timestamp else None
        })

    return jsonify({
        'username': user.username,
        'total_likes': len(likes),
        'liked_posts': liked_posts_data
    })


@bp.route('/api/debug/all-likes')
@login_required
def debug_all_likes():
    all_likes = Like.query.all()
    likes_data = []
    for like in all_likes:
        likes_data.append({
            'id': like.id,
            'user_id': like.user_id,
            'username': like.user.username if like.user else 'Unknown',
            'post_id': like.post_id,
            'timestamp': like.timestamp.isoformat() if like.timestamp else None
        })

    return jsonify({
        'total_likes_in_system': len(all_likes),
        'likes': likes_data
    })

@bp.route('/api/analytics/stats')
@login_required
@admin_required
def api_analytics_stats():
    from datetime import datetime, timedelta

    total_users = User.query.count()
    total_posts = Post.query.filter_by(is_spam=False).count()
    total_likes = Like.query.count()
    total_comments = Comment.query.count()

    week_ago = datetime.now(timezone.utc) - timedelta(days=7)
    new_users_this_week = User.query.filter(User.last_seen >= week_ago).count()

    today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    active_today = User.query.filter(User.last_seen >= today_start).count()

    return jsonify({
        'total_users': total_users,
        'total_posts': total_posts,
        'total_likes': total_likes,
        'total_comments': total_comments,
        'new_users_this_week': new_users_this_week,
        'active_today': active_today
    })


@bp.route('/api/analytics/user-growth')
@login_required
@admin_required
def api_user_growth():
    from datetime import datetime, timedelta

    growth_data = []
    for i in range(30, -1, -1):
        date = datetime.now(timezone.utc).date() - timedelta(days=i)
        next_date = date + timedelta(days=1)

        count = User.query.filter(
            User.last_seen >= datetime.combine(date, datetime.min.time()),
            User.last_seen < datetime.combine(next_date, datetime.min.time())
        ).count()

        growth_data.append({
            'date': date.strftime('%Y-%m-%d'),
            'count': count
        })

    return jsonify(growth_data)

@bp.route('/api/analytics/top-users')
@login_required
@admin_required
def api_top_users():
    from sqlalchemy import func

    top_users = db.session.query(
        User.id,
        User.username,
        func.count(Post.id).label('post_count')
    ).join(Post, Post.user_id == User.id) \
        .group_by(User.id, User.username) \
        .order_by(func.count(Post.id).desc()) \
        .limit(5).all()

    result = []
    for user in top_users:
        user_obj = User.query.get(user.id)
        result.append({
            'username': user.username,
            'avatar': user_obj.avatar(40) if user_obj else None,
            'post_count': user.post_count
        })

    return jsonify(result)


@bp.route('/api/analytics/activity')
@login_required
@admin_required
def api_activity():
    from datetime import datetime, timedelta

    days = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
    posts_data = []
    comments_data = []

    for i in range(6, -1, -1):
        date = datetime.now(timezone.utc).date() - timedelta(days=i)
        next_date = date + timedelta(days=1)

        posts_count = Post.query.filter(
            Post.timestamp >= datetime.combine(date, datetime.min.time()),
            Post.timestamp < datetime.combine(next_date, datetime.min.time())
        ).count()

        comments_count = Comment.query.filter(
            Comment.timestamp >= datetime.combine(date, datetime.min.time()),
            Comment.timestamp < datetime.combine(next_date, datetime.min.time())
        ).count()

        posts_data.append(posts_count)
        comments_data.append(comments_count)

    return jsonify({
        'labels': days,
        'posts': posts_data,
        'comments': comments_data
    })


@bp.route('/api/analytics/engagement')
@login_required
@admin_required
def api_engagement():
    total_likes = Like.query.count()
    total_comments = Comment.query.count()
    total_shares = SharedPost.query.count()
    total_bookmarks = SavedPost.query.count()

    return jsonify({
        'likes': total_likes,
        'comments': total_comments,
        'shares': total_shares,
        'bookmarks': total_bookmarks
    })


@bp.route('/api/ai/chat', methods=['POST'])
@login_required
def ai_chat_api():
    try:
        data = request.get_json()
        message = data.get('message', '')

        if not message:
            return jsonify({'error': 'Message is required'}), 400

        from app.services.deepseek_service import DeepSeekService
        ai_service = DeepSeekService()
        reply = ai_service.chat(message)

        if not current_user.is_vip:
            current_user.increment_ai_chat_usage()

        remaining = current_user.ai_chat_remaining if not current_user.is_vip else '∞'

        return jsonify({
            'success': True,
            'reply': reply,
            'remaining': remaining,
            'is_vip': current_user.is_vip
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@bp.route('/ai-chat')
@login_required
def ai_chat():
    return render_template('ai_chat.html',
                           title='AI Assistant',
                           is_vip=True,
                           limited=False)


@bp.route('/inner-circle')
@login_required
def inner_circle():

    memberships = InnerCircleMembership.query.filter_by(
        user_id=current_user.id,
        is_active=True
    ).all()
    members = [User.query.get(m.member_id) for m in memberships if User.query.get(m.member_id)]

    member_ids = [m.id for m in members]
    suggestions = User.query.filter(
        User.id != current_user.id
    )
    if member_ids:
        suggestions = suggestions.filter(~User.id.in_(member_ids))
    suggestions = suggestions.limit(10).all()

    return render_template('inner_circle.html',
                           members=members,
                           suggestions=suggestions)

@bp.route('/inner-circle/add/<int:user_id>', methods=['POST'])
@login_required
def add_inner_circle(user_id):
    from flask_wtf.csrf import validate_csrf
    try:
        validate_csrf(request.form.get('csrf_token'))
    except:
        flash('CSRF token missing or invalid. Please try again.', 'danger')
        return redirect(url_for('main.inner_circle'))

    user = User.query.get_or_404(user_id)

    if current_user.id == user_id:
        flash('You cannot add yourself to inner circle.', 'warning')
        return redirect(url_for('main.inner_circle'))

    existing = InnerCircleMembership.query.filter_by(
        user_id=current_user.id,
        member_id=user_id
    ).first()

    if existing:
        flash('User is already in your inner circle.', 'info')
        return redirect(url_for('main.inner_circle'))

    if not current_user.is_vip:
        current_count = InnerCircleMembership.query.filter_by(
            user_id=current_user.id,
            is_active=True
        ).count()
        if current_count >= 5:
            flash('You have reached the free limit of 5 Inner Circle members. Upgrade to VIP for unlimited members.', 'warning')
            return redirect(url_for('main.vip'))

    membership = InnerCircleMembership(
        user_id=current_user.id,
        member_id=user_id,
        is_active=True
    )
    db.session.add(membership)
    db.session.commit()
    flash(f'{user.username} added to your inner circle!', 'success')
    return redirect(url_for('main.inner_circle'))

@bp.route('/inner-circle/remove/<int:user_id>', methods=['POST'])
@login_required
def remove_inner_circle(user_id):
    from flask_wtf.csrf import validate_csrf
    try:
        validate_csrf(request.form.get('csrf_token'))
    except:
        flash('CSRF token missing or invalid. Please try again.', 'danger')
        return redirect(url_for('main.inner_circle'))

    membership = InnerCircleMembership.query.filter_by(
        user_id=current_user.id,
        member_id=user_id
    ).first()

    if membership:
        db.session.delete(membership)
        db.session.commit()
        flash('Member removed from inner circle.', 'success')
    else:
        flash('Member not found in inner circle.', 'warning')

    return redirect(url_for('main.inner_circle'))


@bp.route('/save_story/<int:story_id>', methods=['POST'])
@login_required
def save_story(story_id):
    story = db.session.get(Story, story_id)
    if not story:
        return jsonify({'success': False, 'error': 'Story not found'}), 404
    return jsonify({'success': True, 'message': 'Story saved'})


@bp.route('/report_story/<int:story_id>', methods=['POST'])
@login_required
def report_story(story_id):
    story = db.session.get(Story, story_id)
    if not story:
        return jsonify({'success': False, 'error': 'Story not found'}), 404
    return jsonify({'success': True, 'message': 'Story reported'})

@bp.route('/set-locale/<lang>')
@login_required
def set_locale(lang):
    supported_languages = current_app.config.get('LANGUAGES', ['en'])
    if lang in supported_languages:
        session['locale'] = lang
        flash(f'Language changed to {lang}', 'success')
    else:
        flash(f'Language {lang} not supported. Supported: {supported_languages}', 'danger')
    return redirect(request.referrer or url_for('main.index'))


# ========== VIP/PREMIUM ROUTES ==========

@bp.route('/vip')
@login_required
def vip():
    form = VIPUpgradeForm()

    is_vip = current_user.is_vip
    vip_level = current_user.vip_level if is_vip else 'free'
    vip_membership = current_user.vip_membership if is_vip else None

    return render_template('vip.html',
                           title='VIP Membership',
                           form=form,
                           is_vip=is_vip,
                           vip_level=vip_level,
                           vip_membership=vip_membership)


@bp.route('/vip/upgrade', methods=['POST'])
@login_required
def vip_upgrade():
    form = VIPUpgradeForm()
    if form.validate_on_submit():
        plan = form.plan.data
        payment_method = request.form.get('payment_method', 'alipay')

        session['vip_plan'] = plan
        session['vip_payment_method'] = payment_method

        return redirect(url_for('main.vip_payment'))

    flash('Please select a plan.', 'warning')
    return redirect(url_for('main.vip'))


@bp.route('/vip/payment')
@login_required
def vip_payment():
    plan = session.get('vip_plan', 'premium')
    payment_method = session.get('vip_payment_method', 'alipay')

    plan_details = {
        'premium': {'price': '¥18', 'monthly': '¥18', 'yearly': '¥128', 'label': 'Premium'},
        'elite': {'price': '¥38', 'monthly': '¥38', 'yearly': '¥268', 'label': 'Elite'},
        'ultimate': {'price': '¥68', 'monthly': '¥68', 'yearly': '¥468', 'label': 'Ultimate'}
    }

    return render_template('vip_payment.html',
                           plan=plan,
                           plan_details=plan_details[plan],
                           payment_method=payment_method)


@bp.route('/vip/payment/verify', methods=['POST'])
@login_required
def vip_payment_verify():
    plan = session.get('vip_plan', 'premium')
    payment_method = session.get('vip_payment_method', 'alipay')
    transaction_id = request.form.get('transaction_id', '').strip()

    if not transaction_id:
        flash('Please enter the transaction ID from your payment app.', 'warning')
        return redirect(url_for('main.vip_payment'))

    existing = VIPUser.query.filter_by(user_id=current_user.id).first()
    if existing and existing.is_active:
        flash('You are already a VIP member!', 'warning')
        return redirect(url_for('main.vip'))

    from datetime import datetime, timedelta

    if existing:
        existing.vip_level = plan
        existing.payment_id = transaction_id
        existing.payment_method = payment_method
        existing.is_active = False
        existing.started_at = datetime.utcnow()
        db.session.commit()
    else:
        vip = VIPUser(
            user_id=current_user.id,
            vip_level=plan,
            started_at=datetime.utcnow(),
            expires_at=datetime.utcnow() + timedelta(days=30),
            is_active=False,
            payment_method=payment_method,
            payment_id=transaction_id
        )
        db.session.add(vip)
        db.session.commit()

    session.pop('vip_plan', None)
    session.pop('vip_payment_method', None)

    flash('📩 Payment submitted! Admin will verify and activate your VIP membership within 24 hours.', 'success')
    return redirect(url_for('main.vip'))


@bp.route('/vip/payment/qr/<plan>')
@login_required
def vip_payment_qr(plan):
    plan_details = {
        'premium': {'price': '18', 'label': 'Premium'},
        'elite': {'price': '38', 'label': 'Elite'},
        'ultimate': {'price': '68', 'label': 'Ultimate'}
    }

    return render_template('vip_payment_qr.html',
                           plan=plan,
                           plan_details=plan_details[plan],
                           payment_method=request.args.get('method', 'alipay'))


@bp.route('/vip/cancel')
@login_required
def vip_cancel():
    vip = VIPUser.query.filter_by(user_id=current_user.id, is_active=True).first()
    if vip:
        vip.is_active = False
        db.session.commit()
        flash('VIP membership cancelled.', 'info')
    return redirect(url_for('main.vip'))


# ========== VIP WEBHOOK (For payment callback) ==========

@bp.route('/vip/webhook', methods=['POST'])
def vip_webhook():
    data = request.get_json()

    transaction_id = data.get('transaction_id')
    user_id = data.get('user_id')
    plan = data.get('plan')
    payment_method = data.get('payment_method', 'unknown')

    if not all([transaction_id, user_id, plan]):
        return jsonify({'error': 'Missing required fields'}), 400

    user = db.session.get(User, user_id)
    if not user:
        return jsonify({'error': 'User not found'}), 404

    from datetime import datetime, timedelta
    existing = VIPUser.query.filter_by(user_id=user_id).first()
    if existing:
        existing.expires_at = existing.expires_at + timedelta(days=30)
        existing.is_active = True
        existing.vip_level = plan
        existing.payment_id = transaction_id
        db.session.commit()
    else:
        vip = VIPUser(
            user_id=user_id,
            vip_level=plan,
            started_at=datetime.utcnow(),
            expires_at=datetime.utcnow() + timedelta(days=30),
            is_active=True,
            payment_method=payment_method,
            payment_id=transaction_id
        )
        db.session.add(vip)
        db.session.commit()

    user.is_human_verified = True
    db.session.commit()

    return jsonify({'success': True, 'message': 'VIP upgraded successfully'})


@bp.route('/vip/check-expiry')
@login_required
def vip_check_expiry():
    vip = VIPUser.query.filter_by(user_id=current_user.id, is_active=True).first()
    if not vip:
        return jsonify({'is_vip': False})

    from datetime import datetime
    days_left = (vip.expires_at - datetime.utcnow()).days if vip.expires_at else 0

    return jsonify({
        'is_vip': True,
        'level': vip.vip_level,
        'expires_at': vip.expires_at.isoformat() if vip.expires_at else None,
        'days_left': max(0, days_left)
    })

# ========== FEEDBACK ROUTES ==========

@bp.route('/feedback', methods=['GET', 'POST'])
@login_required
def feedback():
    form = FeedbackForm()
    if form.validate_on_submit():
        feedback = Feedback(
            user_id=current_user.id,
            category=form.category.data,
            message=form.message.data,
            rating=int(form.rating.data)
        )
        db.session.add(feedback)
        db.session.commit()

        flash('Thank you for your valuable feedback! 🙏', 'success')
        return redirect(url_for('main.feedback'))

    return render_template('feedback.html', title='Feedback', form=form)


# ========== HELP ROUTES ==========

@bp.route('/help', methods=['GET', 'POST'])
@login_required
def help():
    """Submit help request"""
    form = HelpForm()
    if form.validate_on_submit():
        help_request = HelpRequest(
            user_id=current_user.id,
            subject=form.subject.data,
            message=form.message.data,
            priority=form.priority.data
        )
        db.session.add(help_request)
        db.session.commit()

        flash('Your help request has been sent! Our team will contact you soon. 📩', 'success')
        return redirect(url_for('main.help'))

    return render_template('help.html', title='Help & Support', form=form)

