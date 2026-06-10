from app import db
from app.models import User, Post, Like, Comment
import random

class RecommendationEngine:

    def get_personalized_feed(self, user_id, limit=20):
        from datetime import datetime, timedelta

        liked_posts = db.session.query(Like.post_id).filter(Like.user_id == user_id).all()
        liked_ids = [l[0] for l in liked_posts]

        week_ago = datetime.utcnow() - timedelta(days=7)

        query = db.session.query(Post).filter(
            Post.scheduled_for == None,
            Post.timestamp > week_ago
        )

        if liked_ids:
            query = query.filter(Post.id.notin_(liked_ids))
        posts = query.order_by(Post.timestamp.desc()).limit(limit * 2).all()
        random.shuffle(posts)

        return [p.id for p in posts[:limit]]

    def get_user_recommendations(self, user_id, limit=10):
        following = db.session.query(User.following).filter(User.id == user_id).first()
        following_ids = [f.id for f in following[0]] if following and following[0] else []
        following_ids.append(user_id)
        suggested = db.session.query(User).filter(
            User.id.notin_(following_ids)
        ).limit(limit).all()
        if len(suggested) < limit:
            more = db.session.query(User).filter(
                User.id.notin_(following_ids)
            ).order_by(User.id).limit(limit).all()
            suggested.extend(more)

        return [u.id for u in suggested[:limit]]

recommendation_engine = RecommendationEngine()
