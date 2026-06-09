from app import db


def create_notification(user_id, type, message, link=None):
    from app.models import Notification
    import json

    notification = Notification(
        user_id=user_id,
        name=type,
        payload_json=json.dumps({
            'type': type,
            'message': message,
            'link': link
        }),
        read=False
    )
    db.session.add(notification)
    db.session.commit()
    return notification

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

def send_message_notification(user_id, from_username, message_preview):
    create_notification(user_id, 'message', {
        'from_user': from_username,
        'type': 'private_message',
        'message': message_preview,
        'notification_type': 'message'
    })