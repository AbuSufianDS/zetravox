from datetime import datetime, timezone, timedelta
from hashlib import md5
import json
import secrets
from time import time
from typing import Optional
import sqlalchemy as sa
import sqlalchemy.orm as so
from flask import current_app, url_for
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
import jwt
import redis
import rq
from app import db, login
from app.search import add_to_index, remove_from_index, query_index


class SearchableMixin:
    @classmethod
    def search(cls, expression, page, per_page):
        ids, total = query_index(cls.__tablename__, expression, page, per_page)
        if total == 0:
            return [], 0
        when = []
        for i in range(len(ids)):
            when.append((ids[i], i))
        query = sa.select(cls).where(cls.id.in_(ids)).order_by(
            db.case(*when, value=cls.id))
        return db.session.scalars(query), total

    @classmethod
    def before_commit(cls, session):
        session._changes = {
            'add': list(session.new),
            'update': list(session.dirty),
            'delete': list(session.deleted)
        }

    @classmethod
    def after_commit(cls, session):
        for obj in session._changes['add']:
            if isinstance(obj, SearchableMixin):
                add_to_index(obj.__tablename__, obj)
        for obj in session._changes['update']:
            if isinstance(obj, SearchableMixin):
                add_to_index(obj.__tablename__, obj)
        for obj in session._changes['delete']:
            if isinstance(obj, SearchableMixin):
                remove_from_index(obj.__tablename__, obj)
        session._changes = None

    @classmethod
    def reindex(cls):
        for obj in db.session.scalars(sa.select(cls)):
            add_to_index(cls.__tablename__, obj)


db.event.listen(db.session, 'before_commit', SearchableMixin.before_commit)
db.event.listen(db.session, 'after_commit', SearchableMixin.after_commit)


class PaginatedAPIMixin(object):
    @staticmethod
    def to_collection_dict(query, page, per_page, endpoint, **kwargs):
        resources = db.paginate(query, page=page, per_page=per_page,
                                error_out=False)
        data = {
            'items': [item.to_dict() for item in resources.items],
            '_meta': {
                'page': page,
                'per_page': per_page,
                'total_pages': resources.pages,
                'total_items': resources.total
            },
            '_links': {
                'self': url_for(endpoint, page=page, per_page=per_page,
                                **kwargs),
                'next': url_for(endpoint, page=page + 1, per_page=per_page,
                                **kwargs) if resources.has_next else None,
                'prev': url_for(endpoint, page=page - 1, per_page=per_page,
                                **kwargs) if resources.has_prev else None
            }
        }
        return data


followers = sa.Table(
    'followers',
    db.metadata,
    sa.Column('follower_id', sa.Integer, sa.ForeignKey('user.id'),
              primary_key=True),
    sa.Column('followed_id', sa.Integer, sa.ForeignKey('user.id'),
              primary_key=True)
)
friends = db.Table('friends',
                   db.Column('user_id', db.Integer, db.ForeignKey('user.id'), primary_key=True),
                   db.Column('friend_id', db.Integer, db.ForeignKey('user.id'), primary_key=True),
                   db.Column('created_at', db.DateTime, default=datetime.utcnow)
                   )


class User(PaginatedAPIMixin, UserMixin, db.Model):
    id: so.Mapped[int] = so.mapped_column(primary_key=True)
    username: so.Mapped[str] = so.mapped_column(sa.String(64), index=True, unique=True)
    email: so.Mapped[str] = so.mapped_column(sa.String(120), index=True, unique=True)
    password_hash: so.Mapped[Optional[str]] = so.mapped_column(sa.String(256))
    about_me: so.Mapped[Optional[str]] = so.mapped_column(sa.String(140))
    last_seen: so.Mapped[Optional[datetime]] = so.mapped_column(
        default=lambda: datetime.now(timezone.utc))
    last_message_read_time: so.Mapped[Optional[datetime]]
    token: so.Mapped[Optional[str]] = so.mapped_column(sa.String(32), index=True, unique=True)
    token_expiration: so.Mapped[Optional[datetime]]
    is_admin: so.Mapped[bool] = so.mapped_column(sa.Boolean, default=False)
    profile_pic: so.Mapped[Optional[str]] = so.mapped_column(sa.String(200), default='default.jpg')
    cover_pic: so.Mapped[Optional[str]] = so.mapped_column(sa.String(200), default='default_cover.jpg')
    is_verified: so.Mapped[bool] = so.mapped_column(sa.Boolean, default=False)
    is_private: so.Mapped[bool] = so.mapped_column(sa.Boolean, default=False)
    points: so.Mapped[int] = so.mapped_column(sa.Integer, default=0)
    relationship_status: so.Mapped[Optional[str]] = so.mapped_column(sa.String(50))
    work: so.Mapped[Optional[str]] = so.mapped_column(sa.String(100))
    education: so.Mapped[Optional[str]] = so.mapped_column(sa.String(100))
    location: so.Mapped[Optional[str]] = so.mapped_column(sa.String(100))
    website: so.Mapped[Optional[str]] = so.mapped_column(sa.String(200))
    birthday: so.Mapped[Optional[str]] = so.mapped_column(sa.String(20))
    gender: so.Mapped[Optional[str]] = so.mapped_column(sa.String(20))
    interested_in: so.Mapped[Optional[str]] = so.mapped_column(sa.String(100))
    phone: so.Mapped[Optional[str]] = so.mapped_column(sa.String(20))

    posts: so.WriteOnlyMapped['Post'] = so.relationship(back_populates='author')
    following: so.WriteOnlyMapped['User'] = so.relationship(
        secondary=followers, primaryjoin=(followers.c.follower_id == id),
        secondaryjoin=(followers.c.followed_id == id),
        back_populates='followers')
    followers: so.WriteOnlyMapped['User'] = so.relationship(
        secondary=followers, primaryjoin=(followers.c.followed_id == id),
        secondaryjoin=(followers.c.follower_id == id),
        back_populates='following')
    messages_sent: so.WriteOnlyMapped['Message'] = so.relationship(
        foreign_keys='Message.sender_id', back_populates='author')
    messages_received: so.WriteOnlyMapped['Message'] = so.relationship(
        foreign_keys='Message.recipient_id', back_populates='recipient')
    notifications: so.WriteOnlyMapped['Notification'] = so.relationship(
        back_populates='user')
    tasks: so.WriteOnlyMapped['Task'] = so.relationship(back_populates='user')
    saved_posts: so.WriteOnlyMapped['SavedPost'] = so.relationship(back_populates='user')
    blocked_users: so.WriteOnlyMapped['BlockedUser'] = so.relationship(
        foreign_keys='BlockedUser.blocker_id', back_populates='blocker')
    blocked_by: so.WriteOnlyMapped['BlockedUser'] = so.relationship(
        foreign_keys='BlockedUser.blocked_id', back_populates='blocked')
    last_active: so.Mapped[Optional[datetime]] = so.mapped_column(default=lambda: datetime.now(timezone.utc))
    friends = db.relationship(
        'User', secondary='friends',
        primaryjoin=(id == friends.c.user_id),
        secondaryjoin=(id == friends.c.friend_id),
        lazy='dynamic'
    )

    friend_requests_sent = db.relationship(
        'FriendRequest',
        foreign_keys='FriendRequest.from_user_id',
        backref='sender', lazy='dynamic'
    )

    friend_requests_received = db.relationship(
        'FriendRequest',
        foreign_keys='FriendRequest.to_user_id',
        backref='receiver', lazy='dynamic'
    )
    otp_secret = db.Column(db.String(32), nullable=True)
    two_factor_enabled = db.Column(db.Boolean, default=False)
    backup_codes = db.Column(db.String(500), nullable=True)

    gdpr_consent = db.Column(db.Boolean, default=False)
    gdpr_consent_date = db.Column(db.DateTime)
    data_anonymized = db.Column(db.Boolean, default=False)

    login_attempts = db.Column(db.Integer, default=0)
    locked_until = db.Column(db.DateTime)
    last_login_ip = db.Column(db.String(45))
    last_login_time = db.Column(db.DateTime)
    account_created_ip = db.Column(db.String(45))
    rate_limit_reset = db.Column(db.DateTime)

    login_history = db.relationship('LoginHistory', backref='user_rel', lazy='dynamic',
                                    foreign_keys='LoginHistory.user_id')
    security_events = db.relationship('SecurityEvent', backref='user_rel', lazy='dynamic',
                                      foreign_keys='SecurityEvent.user_id')
    active_sessions = db.relationship('UserSession', backref='user_rel', lazy='dynamic',
                                      foreign_keys='UserSession.user_id')
    notify_email_likes = db.Column(db.Boolean, default=True)
    notify_email_comments = db.Column(db.Boolean, default=True)
    notify_email_follows = db.Column(db.Boolean, default=True)
    notify_push_likes = db.Column(db.Boolean, default=True)
    notify_push_comments = db.Column(db.Boolean, default=True)
    notify_push_follows = db.Column(db.Boolean, default=True)
    albums = db.relationship('Album', backref='user', lazy='dynamic', cascade='all, delete-orphan')


    def increment_login_attempts(self):
        self.login_attempts += 1
        if self.login_attempts >= 5:
            self.locked_until = datetime.utcnow() + timedelta(minutes=15)
        db.session.commit()

    def reset_login_attempts(self):
        self.login_attempts = 0
        self.locked_until = None
        db.session.commit()

    def is_account_locked(self):
        if self.locked_until and self.locked_until > datetime.utcnow():
            return True
        return False

    def set_2fa_secret(self, secret):
        self.otp_secret = secret
        db.session.commit()

    def enable_2fa(self):
        self.two_factor_enabled = True
        db.session.commit()

    def disable_2fa(self):
        self.two_factor_enabled = False
        db.session.commit()

    def set_gdpr_consent(self, consent=True):
        self.gdpr_consent = consent
        self.gdpr_consent_date = datetime.utcnow() if consent else None
        db.session.commit()

    def get_friends(self):
        return self.friends.all()

    def get_friend_count(self):
        return self.friends.count()

    def send_friend_request(self, user):
        if not self.has_friend_request_pending(user) and user != self:
            request = FriendRequest(from_user_id=self.id, to_user_id=user.id)
            db.session.add(request)
            db.session.commit()
            return True
        return False

    def has_friend_request_pending(self, user):
        return FriendRequest.query.filter_by(
            from_user_id=self.id, to_user_id=user.id, status='pending'
        ).first() is not None

    def avatar(self, size):
        if self.profile_pic and self.profile_pic not in ['default.jpg', 'None']:
            try:
                return url_for('static', filename=f'uploads/profiles/{self.profile_pic}')
            except:
                pass
        digest = md5(self.email.lower().encode('utf-8')).hexdigest()
        return f'https://www.gravatar.com/avatar/{digest}?d=identicon&s={size}'

    @property
    def is_online(self):
        if self.last_seen:
            now = datetime.now(timezone.utc)
            if self.last_seen.tzinfo is None:
                last_seen = self.last_seen.replace(tzinfo=timezone.utc)
            else:
                last_seen = self.last_seen
            return (now - last_seen).total_seconds() < 300
        return False

    def cover_photo(self):
        if self.cover_pic and self.cover_pic not in ['default_cover.jpg', 'None']:
            try:
                return url_for('static', filename=f'uploads/profiles/{self.cover_pic}')
            except:
                pass
        return None

    def from_dict(self, data, new_user=False):
        for field in ['username', 'email', 'about_me']:
            if field in data:
                setattr(self, field, data[field])
        if new_user and 'password' in data:
            self.set_password(data['password'])

    def following_posts(self):
        return (
            sa.select(Post)
            .where(Post.scheduled_for.is_(None))
            .where(Post.privacy == 'public')
            .order_by(Post.timestamp.desc())
        )
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def follow(self, user):
        if not self.is_following(user):
            self.following.add(user)

    def unfollow(self, user):
        if self.is_following(user):
            self.following.remove(user)

    def is_following(self, user):
        query = self.following.select().where(User.id == user.id)
        return db.session.scalar(query) is not None

    def followers_count(self):
        query = sa.select(sa.func.count()).select_from(
            self.followers.select().subquery())
        return db.session.scalar(query)

    def following_count(self):
        query = sa.select(sa.func.count()).select_from(
            self.following.select().subquery())
        return db.session.scalar(query)

    def unread_message_count(self):
        last_read_time = self.last_message_read_time or datetime(1900, 1, 1)
        query = sa.select(Message).where(Message.recipient == self,
                                         Message.timestamp > last_read_time)
        return db.session.scalar(sa.select(sa.func.count()).select_from(
            query.subquery()))

    def add_notification(self, name, data):
        db.session.execute(self.notifications.delete().where(
            Notification.name == name))
        n = Notification(name=name, payload_json=json.dumps(data), user=self)
        db.session.add(n)
        return n

    def launch_task(self, name, description, *args, **kwargs):
        rq_job = current_app.task_queue.enqueue(f'app.tasks.{name}', self.id,
                                                *args, **kwargs)
        task = Task(id=rq_job.get_id(), name=name, description=description,
                    user=self)
        db.session.add(task)
        return task

    def get_tasks_in_progress(self):
        query = self.tasks.select().where(Task.complete == False)
        return db.session.scalars(query)

    def get_task_in_progress(self, name):
        query = self.tasks.select().where(Task.name == name,
                                          Task.complete == False)
        return db.session.scalar(query)

    def get_reset_password_token(self, expires_in=600):
        return jwt.encode(
            {'reset_password': self.id, 'exp': time() + expires_in},
            current_app.config['SECRET_KEY'], algorithm='HS256')

    @staticmethod
    def verify_reset_password_token(token):
        try:
            id = jwt.decode(token, current_app.config['SECRET_KEY'],
                            algorithms=['HS256'])['reset_password']
        except Exception:
            return
        return db.session.get(User, id)

    def to_dict(self, include_email=False):
        data = {
            'id': self.id,
            'username': self.username,
            'last_seen': self.last_seen.replace(
                tzinfo=timezone.utc).isoformat() if self.last_seen else None,
            'about_me': self.about_me,
            'post_count': self.posts_count(),
            'follower_count': self.followers_count(),
            'following_count': self.following_count(),
            'is_verified': self.is_verified,
            'points': self.points,
            '_links': {
                'self': url_for('api.get_user', id=self.id),
                'followers': url_for('api.get_followers', id=self.id),
                'following': url_for('api.get_following', id=self.id),
                'avatar': self.avatar(128)
            }
        }
        if include_email:
            data['email'] = self.email
        return data

    def get_token(self, expires_in=3600):
        now = datetime.now(timezone.utc)
        if self.token and self.token_expiration and self.token_expiration.replace(
                tzinfo=timezone.utc) > now + timedelta(seconds=60):
            return self.token
        self.token = secrets.token_hex(16)
        self.token_expiration = now + timedelta(seconds=expires_in)
        db.session.add(self)
        return self.token

    def revoke_token(self):
        self.token_expiration = datetime.now(timezone.utc) - timedelta(seconds=1)

    @staticmethod
    def check_token(token):
        user = db.session.scalar(sa.select(User).where(User.token == token))
        if user is None or user.token_expiration and user.token_expiration.replace(
                tzinfo=timezone.utc) < datetime.now(timezone.utc):
            return None
        return user

    def is_blocked_by(self, user):
        if user.is_authenticated:
            return db.session.scalar(
                sa.select(BlockedUser).where(
                    BlockedUser.blocker_id == user.id,
                    BlockedUser.blocked_id == self.id
                )
            ) is not None
        return False

    def posts_count(self):
        query = sa.select(sa.func.count()).select_from(
            self.posts.select().subquery())
        return db.session.scalar(query)


    def accept_friend_request(self, request):
        if request.to_user_id == self.id:
            request.status = 'accepted'
            self.friends.append(request.from_user)
            request.from_user.friends.append(self)
            db.session.commit()
            return True
        return False

    def reject_friend_request(self, request):
        if request.to_user_id == self.id:
            db.session.delete(request)
            db.session.commit()
            return True
        return False

    def is_friend_with(self, user):
        return self.friends.filter(friends.c.friend_id == user.id).count() > 0

    def get_pending_friend_requests(self):
        return self.friend_requests_received.filter_by(status='pending').all()

    def get_active_friends_online(self):
        from datetime import datetime, timedelta
        five_minutes_ago = datetime.utcnow() - timedelta(minutes=5)
        return [f for f in self.friends if f.last_seen and f.last_seen > five_minutes_ago]

    def get_blocked_users(self):
        blocked_list = BlockedUser.query.filter_by(blocker_id=self.id).all()
        return [db.session.get(User, b.blocked_id) for b in blocked_list if db.session.get(User, b.blocked_id)]

    def get_blocked_count(self):
        return BlockedUser.query.filter_by(blocker_id=self.id).count()


class Album(db.Model):
    __tablename__ = 'album'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    name = db.Column(db.String(100), default='Timeline Photos')
    description = db.Column(db.String(500))
    cover_photo = db.Column(db.String(500))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    photos = db.relationship('AlbumPhoto', backref='album', lazy='dynamic', cascade='all, delete-orphan')


class AlbumPhoto(db.Model):
    __tablename__ = 'album_photo'
    id = db.Column(db.Integer, primary_key=True)
    album_id = db.Column(db.Integer, db.ForeignKey('album.id', ondelete='CASCADE'), nullable=False)
    media_url = db.Column(db.String(500), nullable=False)
    media_type = db.Column(db.String(10), default='image')
    caption = db.Column(db.String(500))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class FriendRequest(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    from_user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    to_user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    status = db.Column(db.String(20), default='pending')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (db.UniqueConstraint('from_user_id', 'to_user_id', name='unique_friend_request'),)

    @property
    def from_user(self):
        return db.session.get(User, self.from_user_id)

    @property
    def to_user(self):
        return db.session.get(User, self.to_user_id)

class PostReaction(db.Model):
    __tablename__ = 'post_reaction'
    id: so.Mapped[int] = so.mapped_column(primary_key=True)
    user_id: so.Mapped[int] = so.mapped_column(sa.ForeignKey(User.id), index=True)
    post_id: so.Mapped[int] = so.mapped_column(sa.ForeignKey('post.id', ondelete='CASCADE'), index=True)
    reaction: so.Mapped[str] = so.mapped_column(sa.String(20))
    timestamp: so.Mapped[datetime] = so.mapped_column(default=lambda: datetime.now(timezone.utc))

    __table_args__ = (sa.UniqueConstraint('user_id', 'post_id', name='unique_reaction'),)


class PostMedia(db.Model):
    __tablename__ = 'post_media'
    id = db.Column(db.Integer, primary_key=True)
    post_id = db.Column(db.Integer, db.ForeignKey('post.id', ondelete='CASCADE'), nullable=False)
    media_url = db.Column(db.String(500), nullable=False)
    media_type = db.Column(db.String(10), nullable=False)  # 'image' or 'video'
    order = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    post = db.relationship('Post', backref=db.backref('media_items', lazy='dynamic', cascade='all, delete-orphan'))

class Like(db.Model):
    __tablename__ = 'like'
    id: so.Mapped[int] = so.mapped_column(primary_key=True)
    user_id: so.Mapped[int] = so.mapped_column(sa.ForeignKey(User.id), index=True)
    post_id: so.Mapped[int] = so.mapped_column(sa.ForeignKey('post.id', ondelete='CASCADE'), index=True)
    timestamp: so.Mapped[datetime] = so.mapped_column(default=lambda: datetime.now(timezone.utc))

    __table_args__ = (sa.UniqueConstraint('user_id', 'post_id', name='unique_like'),)


class Comment(db.Model):
    __tablename__ = 'comment'
    id: so.Mapped[int] = so.mapped_column(primary_key=True)
    body: so.Mapped[str] = so.mapped_column(sa.String(500))
    timestamp: so.Mapped[datetime] = so.mapped_column(default=lambda: datetime.now(timezone.utc))
    user_id: so.Mapped[int] = so.mapped_column(sa.ForeignKey(User.id), index=True)
    post_id: so.Mapped[int] = so.mapped_column(sa.ForeignKey('post.id', ondelete='CASCADE'), index=True)
    is_hidden: so.Mapped[bool] = so.mapped_column(default=False)

    author: so.Mapped[User] = so.relationship(foreign_keys=[user_id])
    post: so.Mapped['Post'] = so.relationship(foreign_keys=[post_id], back_populates='comments')


class SharedPost(db.Model):
    __tablename__ = 'shared_post'
    id: so.Mapped[int] = so.mapped_column(primary_key=True)
    original_post_id: so.Mapped[int] = so.mapped_column(sa.ForeignKey('post.id', ondelete='CASCADE'), index=True)
    shared_by_id: so.Mapped[int] = so.mapped_column(sa.ForeignKey(User.id), index=True)
    timestamp: so.Mapped[datetime] = so.mapped_column(default=lambda: datetime.now(timezone.utc))

    original_post: so.Mapped['Post'] = so.relationship(foreign_keys=[original_post_id])
    shared_by: so.Mapped[User] = so.relationship(foreign_keys=[shared_by_id])


class SavedPost(db.Model):
    __tablename__ = 'saved_post'
    id: so.Mapped[int] = so.mapped_column(primary_key=True)
    user_id: so.Mapped[int] = so.mapped_column(sa.ForeignKey(User.id), index=True)
    post_id: so.Mapped[int] = so.mapped_column(sa.ForeignKey('post.id', ondelete='CASCADE'), index=True)
    timestamp: so.Mapped[datetime] = so.mapped_column(default=lambda: datetime.now(timezone.utc))

    user: so.Mapped[User] = so.relationship(foreign_keys=[user_id], back_populates='saved_posts')
    post: so.Mapped['Post'] = so.relationship(foreign_keys=[post_id])


class BlockedUser(db.Model):
    __tablename__ = 'blocked_user'
    id: so.Mapped[int] = so.mapped_column(primary_key=True)
    blocker_id: so.Mapped[int] = so.mapped_column(sa.ForeignKey(User.id), index=True)
    blocked_id: so.Mapped[int] = so.mapped_column(sa.ForeignKey(User.id), index=True)
    timestamp: so.Mapped[datetime] = so.mapped_column(default=lambda: datetime.now(timezone.utc))

    blocker: so.Mapped[User] = so.relationship(foreign_keys=[blocker_id], back_populates='blocked_users')
    blocked: so.Mapped[User] = so.relationship(foreign_keys=[blocked_id], back_populates='blocked_by')


class Hashtag(db.Model):
    __tablename__ = 'hashtag'
    id: so.Mapped[int] = so.mapped_column(primary_key=True)
    name: so.Mapped[str] = so.mapped_column(sa.String(100), unique=True, index=True)
    post_count: so.Mapped[int] = so.mapped_column(default=0)

    def __repr__(self):
        return f'#{self.name}'


class PostHashtag(db.Model):
    __tablename__ = 'post_hashtag'
    id: so.Mapped[int] = so.mapped_column(primary_key=True)
    post_id: so.Mapped[int] = so.mapped_column(sa.ForeignKey('post.id', ondelete='CASCADE'), index=True)
    hashtag_id: so.Mapped[int] = so.mapped_column(sa.ForeignKey(Hashtag.id, ondelete='CASCADE'), index=True)


class Story(db.Model):
    __tablename__ = 'story'
    id: so.Mapped[int] = so.mapped_column(primary_key=True)
    user_id: so.Mapped[int] = so.mapped_column(sa.ForeignKey(User.id), index=True)
    media_url: so.Mapped[Optional[str]] = so.mapped_column(sa.String(500))
    media_type: so.Mapped[str] = so.mapped_column(sa.String(20), default='image')
    caption: so.Mapped[Optional[str]] = so.mapped_column(sa.String(500))
    bg_color: so.Mapped[Optional[str]] = so.mapped_column(sa.String(50), default='gradient-purple')
    shared_post_id: so.Mapped[Optional[int]] = so.mapped_column(sa.Integer, nullable=True)
    timestamp: so.Mapped[datetime] = so.mapped_column(default=lambda: datetime.now(timezone.utc))
    expires_at: so.Mapped[datetime] = so.mapped_column(
        default=lambda: datetime.now(timezone.utc) + timedelta(hours=24))

    author: so.Mapped[User] = so.relationship(foreign_keys=[user_id])

class StoryView(db.Model):
    __tablename__ = 'story_view'
    id: so.Mapped[int] = so.mapped_column(primary_key=True)
    story_id: so.Mapped[int] = so.mapped_column(sa.ForeignKey(Story.id, ondelete='CASCADE'), index=True)
    viewer_id: so.Mapped[int] = so.mapped_column(sa.ForeignKey(User.id), index=True)
    timestamp: so.Mapped[datetime] = so.mapped_column(default=lambda: datetime.now(timezone.utc))


class ChatMessage(db.Model):
    __tablename__ = 'chat_message'
    id: so.Mapped[int] = so.mapped_column(primary_key=True)
    sender_id: so.Mapped[int] = so.mapped_column(sa.ForeignKey(User.id), index=True)
    recipient_id: so.Mapped[int] = so.mapped_column(sa.ForeignKey(User.id), index=True)
    message: so.Mapped[str] = so.mapped_column(sa.String(1000))
    is_read: so.Mapped[bool] = so.mapped_column(default=False)
    timestamp: so.Mapped[datetime] = so.mapped_column(default=lambda: datetime.now(timezone.utc))

    sender: so.Mapped[User] = so.relationship(foreign_keys=[sender_id])
    recipient: so.Mapped[User] = so.relationship(foreign_keys=[recipient_id])


class Post(SearchableMixin, db.Model):
    __tablename__ = 'post'
    __searchable__ = ['body']
    id: so.Mapped[int] = so.mapped_column(primary_key=True)
    body: so.Mapped[str] = so.mapped_column(sa.String(280))
    original_body: so.Mapped[Optional[str]] = so.mapped_column(sa.String(280))
    timestamp: so.Mapped[datetime] = so.mapped_column(
        index=True, default=lambda: datetime.now(timezone.utc))
    edited_at: so.Mapped[Optional[datetime]] = so.mapped_column()
    user_id: so.Mapped[int] = so.mapped_column(sa.ForeignKey(User.id), index=True)
    language: so.Mapped[Optional[str]] = so.mapped_column(sa.String(5))
    is_spam: so.Mapped[bool] = so.mapped_column(sa.Boolean, default=False)
    spam_confidence: so.Mapped[float] = so.mapped_column(sa.Float, default=0.0)
    reviewed: so.Mapped[bool] = so.mapped_column(sa.Boolean, default=False)
    approved: so.Mapped[bool] = so.mapped_column(sa.Boolean, default=True)
    privacy: so.Mapped[str] = so.mapped_column(sa.String(20), default='public')
    scheduled_for: so.Mapped[Optional[datetime]] = so.mapped_column()
    is_pinned: so.Mapped[bool] = so.mapped_column(default=False)
    share_count: so.Mapped[int] = so.mapped_column(default=0)

    author: so.Mapped[User] = so.relationship(back_populates='posts')
    comments: so.WriteOnlyMapped['Comment'] = so.relationship(back_populates='post', passive_deletes=True)
    likes: so.WriteOnlyMapped['Like'] = so.relationship(passive_deletes=True)
    reactions: so.WriteOnlyMapped['PostReaction'] = so.relationship(passive_deletes=True)
    hashtags: so.WriteOnlyMapped['PostHashtag'] = so.relationship(passive_deletes=True)

    def like_count(self):
        return db.session.scalar(sa.select(sa.func.count()).select_from(self.likes.select().subquery()))

    def is_liked_by(self, user):
        if user.is_authenticated:
            return db.session.scalar(
                sa.select(Like).where(Like.user_id == user.id, Like.post_id == self.id)
            ) is not None
        return False

    def trending_score(self, refresh=False):
        from datetime import datetime, timezone

        if not refresh and self.trending_score_cache > 0:
            return self.trending_score_cache

        likes = self.like_count() or 0
        comments = self.comment_count() or 0
        reactions = sum(self.get_reaction_counts().values()) or 0
        shares = self.share_count or 0

        now_naive = datetime.now(timezone.utc).replace(tzinfo=None)
        post_time = self.timestamp.replace(tzinfo=None) if self.timestamp else now_naive

        age_hours = (now_naive - post_time).total_seconds() / 3600
        if age_hours < 1:
            age_hours = 1

        score = ((likes * 1.5) + (comments * 2.5) + (reactions * 1.2) + (shares * 3.0)) / (age_hours ** 0.8)
        rounded_score = round(score, 2)

        self.trending_score_cache = rounded_score
        db.session.commit()

        return rounded_score

    def comment_count(self):
        return db.session.scalar(sa.select(sa.func.count()).select_from(
            self.comments.select().where(Comment.is_hidden == False).subquery()))

    def get_comments(self):
        return db.session.scalars(
            self.comments.select().where(Comment.is_hidden == False).order_by(Comment.timestamp.asc())
        ).all()

    def get_reaction_counts(self):
        reactions = db.session.execute(
            sa.select(PostReaction.reaction, sa.func.count())
            .where(PostReaction.post_id == self.id)
            .group_by(PostReaction.reaction)
        ).all()
        return {r[0]: r[1] for r in reactions}

    def user_reaction(self, user):
        if user.is_authenticated:
            reaction = db.session.scalar(
                sa.select(PostReaction).where(PostReaction.user_id == user.id, PostReaction.post_id == self.id)
            )
            return reaction.reaction if reaction else None
        return None

    def extract_hashtags(self):
        import re
        hashtags = re.findall(r'#(\w+)', self.body)
        return hashtags

    def __repr__(self):
        return '<Post {}>'.format(self.body[:50])


class HiddenPost(db.Model):
    __tablename__ = 'hidden_post'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    post_id = db.Column(db.Integer, db.ForeignKey('post.id', ondelete='CASCADE'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship('User', foreign_keys=[user_id])
    post = db.relationship('Post', foreign_keys=[post_id])


class NotInterestedPost(db.Model):
    __tablename__ = 'not_interested_post'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    post_id = db.Column(db.Integer, db.ForeignKey('post.id', ondelete='CASCADE'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship('User', foreign_keys=[user_id])
    post = db.relationship('Post', foreign_keys=[post_id])


class InterestedPost(db.Model):
    __tablename__ = 'interested_post'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    post_id = db.Column(db.Integer, db.ForeignKey('post.id', ondelete='CASCADE'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship('User', foreign_keys=[user_id])
    post = db.relationship('Post', foreign_keys=[post_id])

class SpamReport(db.Model):
    __tablename__ = 'spam_report'
    id: so.Mapped[int] = so.mapped_column(primary_key=True)
    post_id: so.Mapped[int] = so.mapped_column(sa.ForeignKey(Post.id, ondelete='CASCADE'), index=True)
    reporter_id: so.Mapped[int] = so.mapped_column(sa.ForeignKey(User.id), index=True)
    reason: so.Mapped[Optional[str]] = so.mapped_column(sa.String(200))
    timestamp: so.Mapped[datetime] = so.mapped_column(
        index=True, default=lambda: datetime.now(timezone.utc))
    reviewed: so.Mapped[bool] = so.mapped_column(default=False)

    post: so.Mapped[Post] = so.relationship(foreign_keys=[post_id])
    reporter: so.Mapped[User] = so.relationship(foreign_keys=[reporter_id])


class Message(db.Model):
    __tablename__ = 'message'
    id: so.Mapped[int] = so.mapped_column(primary_key=True)
    sender_id: so.Mapped[int] = so.mapped_column(sa.ForeignKey(User.id), index=True)
    recipient_id: so.Mapped[int] = so.mapped_column(sa.ForeignKey(User.id), index=True)
    body: so.Mapped[str] = so.mapped_column(sa.String(140))
    timestamp: so.Mapped[datetime] = so.mapped_column(
        index=True, default=lambda: datetime.now(timezone.utc))

    author: so.Mapped[User] = so.relationship(
        foreign_keys='Message.sender_id',
        back_populates='messages_sent')
    recipient: so.Mapped[User] = so.relationship(
        foreign_keys='Message.recipient_id',
        back_populates='messages_received')


class Notification(db.Model):
    __tablename__ = 'notification'
    id: so.Mapped[int] = so.mapped_column(primary_key=True)
    name: so.Mapped[str] = so.mapped_column(sa.String(128), index=True)
    user_id: so.Mapped[int] = so.mapped_column(sa.ForeignKey(User.id), index=True)
    timestamp: so.Mapped[float] = so.mapped_column(index=True, default=time)
    payload_json: so.Mapped[str] = so.mapped_column(sa.Text)

    user: so.Mapped[User] = so.relationship(back_populates='notifications')

    def get_data(self):
        return json.loads(str(self.payload_json))

class Task(db.Model):
    __tablename__ = 'task'
    id: so.Mapped[str] = so.mapped_column(sa.String(36), primary_key=True)
    name: so.Mapped[str] = so.mapped_column(sa.String(128), index=True)
    description: so.Mapped[Optional[str]] = so.mapped_column(sa.String(128))
    user_id: so.Mapped[int] = so.mapped_column(sa.ForeignKey(User.id))
    complete: so.Mapped[bool] = so.mapped_column(default=False)

    user: so.Mapped[User] = so.relationship(back_populates='tasks')

    def get_rq_job(self):
        try:
            rq_job = rq.job.Job.fetch(self.id, connection=current_app.redis)
        except (redis.exceptions.RedisError, rq.exceptions.NoSuchJobError):
            return None
        return rq_job

    def get_progress(self):
        job = self.get_rq_job()
        return job.meta.get('progress', 0) if job is not None else 100


class UserActivity(db.Model):
    __tablename__ = 'user_activity'
    id: so.Mapped[int] = so.mapped_column(primary_key=True)
    user_id: so.Mapped[int] = so.mapped_column(sa.ForeignKey(User.id), index=True)
    activity_type: so.Mapped[str] = so.mapped_column(sa.String(50))
    target_id: so.Mapped[int] = so.mapped_column()
    timestamp: so.Mapped[datetime] = so.mapped_column(default=lambda: datetime.now(timezone.utc))


class StoryReaction(db.Model):
    __tablename__ = 'story_reaction'
    id: so.Mapped[int] = so.mapped_column(primary_key=True)
    user_id: so.Mapped[int] = so.mapped_column(sa.ForeignKey(User.id))
    story_id: so.Mapped[int] = so.mapped_column(sa.ForeignKey(Story.id, ondelete='CASCADE'))
    reaction: so.Mapped[str] = so.mapped_column(sa.String(20))
    timestamp: so.Mapped[datetime] = so.mapped_column(default=lambda: datetime.now(timezone.utc))

    __table_args__ = (sa.UniqueConstraint('user_id', 'story_id', name='unique_story_reaction'),)


class StoryComment(db.Model):
    __tablename__ = 'story_comment'
    id: so.Mapped[int] = so.mapped_column(primary_key=True)
    story_id: so.Mapped[int] = so.mapped_column(sa.ForeignKey(Story.id, ondelete='CASCADE'))
    user_id: so.Mapped[int] = so.mapped_column(sa.ForeignKey(User.id))
    message: so.Mapped[str] = so.mapped_column(sa.String(500))
    timestamp: so.Mapped[datetime] = so.mapped_column(default=lambda: datetime.now(timezone.utc))

    author: so.Mapped[User] = so.relationship(foreign_keys=[user_id])


class LoginHistory(db.Model):
    __tablename__ = 'login_history'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), index=True)
    ip_address = db.Column(db.String(45))
    user_agent = db.Column(db.String(500))
    success = db.Column(db.Boolean, default=False)
    failure_reason = db.Column(db.String(100))
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship('User', foreign_keys=[user_id])

    @classmethod
    def create(cls, user_id, ip_address, user_agent, success=True, failure_reason=None):
        history = cls(
            user_id=user_id,
            ip_address=ip_address,
            user_agent=user_agent,
            success=success,
            failure_reason=failure_reason
        )
        db.session.add(history)
        db.session.commit()
        return history

class SecurityEvent(db.Model):
    __tablename__ = 'security_event'
    id = db.Column(db.Integer, primary_key=True)
    event_type = db.Column(db.String(50), index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True, index=True)
    ip_address = db.Column(db.String(45))
    details = db.Column(db.String(1000))
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    user = db.relationship('User', foreign_keys=[user_id])

    @classmethod
    def log(cls, user_id, event_type, ip_address, details):
        event = cls(
            user_id=user_id,
            event_type=event_type,
            ip_address=ip_address,
            details=details
        )
        db.session.add(event)
        db.session.commit()
        return event


class UserSession(db.Model):
    __tablename__ = 'user_session'
    id = db.Column(db.String(128), primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), index=True)
    ip_address = db.Column(db.String(45))
    user_agent = db.Column(db.String(500))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    expires_at = db.Column(db.DateTime)
    is_active = db.Column(db.Boolean, default=True)

    user = db.relationship('User', foreign_keys=[user_id])


class DataDeletionRequest(db.Model):
    __tablename__ = 'data_deletion_request'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), index=True)
    request_date = db.Column(db.DateTime, default=datetime.utcnow)
    completed_date = db.Column(db.DateTime)
    status = db.Column(db.String(20), default='pending')
    request_ip = db.Column(db.String(45))

    user = db.relationship('User', foreign_keys=[user_id])

@login.user_loader
def load_user(id):
    return db.session.get(User, int(id))


