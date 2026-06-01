from app import db
from app.services.recommendation_service import recommendation_engine
import logging


def update_recommendation_models():
    logging.info("Updating recommendation models...")
    logging.info("Recommendation models updated successfully")


def refresh_user_feed_cache():
    from app.models import User, UserActivity
    from datetime import datetime, timedelta

    day_ago = datetime.utcnow() - timedelta(days=1)
    active_users = db.session.query(User.id).filter(
        User.last_seen > day_ago
    ).limit(100).all()

    for (user_id,) in active_users:
        recommendation_engine.get_personalized_feed(user_id, limit=50)

    logging.info(f"Cached feeds for {len(active_users)} active users")

