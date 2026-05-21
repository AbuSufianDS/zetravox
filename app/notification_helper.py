from app import db
from app.models import Notification
import json
from datetime import datetime, timezone

def create_notification(user_id, notification_type, data):
    """Create a notification for a user"""
    try:
        notification = Notification(
            name=notification_type,
            user_id=user_id,
            payload_json=json.dumps(data),
            timestamp=datetime.now(timezone.utc).timestamp()
        )
        db.session.add(notification)
        db.session.commit()
        print(f"✅ NOTIFICATION CREATED: {notification_type} for user {user_id}")
        print(f"   Data: {data}")
        return notification
    except Exception as e:
        print(f"❌ Error creating notification: {e}")
        return None

def send_like_notification(post_author_id, liker_username, post_id, post_preview):
    """Send notification when someone likes a post"""
    if post_author_id != liker_username:
        print(f"📨 Creating like notification from {liker_username} to user {post_author_id}")
        create_notification(post_author_id, 'like', {
            'type': 'like',
            'username': liker_username,
            'post_id': post_id,
            'post_preview': post_preview[:50] if post_preview else '',
            'message': f'{liker_username} liked your post'
        })

def send_comment_notification(post_author_id, commenter_username, post_id, comment_preview):
    """Send notification when someone comments on a post"""
    if post_author_id != commenter_username:
        print(f"📨 Creating comment notification from {commenter_username} to user {post_author_id}")
        create_notification(post_author_id, 'comment', {
            'type': 'comment',
            'username': commenter_username,
            'post_id': post_id,
            'comment_preview': comment_preview[:50] if comment_preview else '',
            'message': f'{commenter_username} commented on your post'
        })

def send_follow_notification(user_id, follower_username):
    """Send notification when someone follows you"""
    print(f"📨 Creating follow notification to user {user_id} from {follower_username}")
    create_notification(user_id, 'follow', {
        'type': 'follow',
        'username': follower_username,
        'message': f'{follower_username} started following you'
    })

def send_share_notification(post_author_id, sharer_username, post_id):
    """Send notification when someone shares your post"""
    if post_author_id != sharer_username:
        print(f"📨 Creating share notification from {sharer_username} to user {post_author_id}")
        create_notification(post_author_id, 'share', {
            'type': 'share',
            'username': sharer_username,
            'post_id': post_id,
            'message': f'{sharer_username} shared your post'
        })