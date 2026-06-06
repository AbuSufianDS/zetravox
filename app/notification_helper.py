from app import db
from app.models import Notification
import json
from datetime import datetime, timezone


def create_notification(user_id, notification_type, data):
    try:
        # Ensure data is a dictionary
        if not isinstance(data, dict):
            data = {}

        notification = Notification(
            name=notification_type,
            user_id=user_id,
            payload_json=json.dumps(data),
            timestamp=datetime.now(timezone.utc).timestamp(),
            read=False
        )
        db.session.add(notification)
        db.session.commit()
        print(f"NOTIFICATION CREATED: {notification_type} for user {user_id}")
        print(f"   Data: {data}")
        return notification
    except Exception as e:
        print(f"Error creating notification: {e}")
        db.session.rollback()
        return None


def send_like_notification(user_id, from_username, post_id, post_body):
    create_notification(user_id, 'like', {
        'from_user': from_username,
        'post_id': post_id,
        'message': f'{from_username} liked your post'
    })


def send_comment_notification(user_id, from_username, post_id, comment_body):
    create_notification(user_id, 'comment', {
        'from_user': from_username,
        'post_id': post_id,
        'comment': comment_body[:100],
        'message': f'{from_username} commented on your post'
    })


def send_share_notification(user_id, from_username, post_id):
    create_notification(user_id, 'share', {
        'from_user': from_username,
        'post_id': post_id,
        'message': f'{from_username} shared your post'
    })


def send_follow_notification(user_id, follower_username):
    print(f"Creating follow notification to user {user_id} from {follower_username}")
    create_notification(user_id, 'follow', {
        'from_user': follower_username,
        'type': 'follow',
        'message': f'{follower_username} started following you'
    })