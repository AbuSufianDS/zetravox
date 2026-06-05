from app import db
from app.models import Post


def update_all_trending_scores():
    print("Updating trending scores for all posts...")

    posts = Post.query.all()
    updated_count = 0

    for post in posts:
        post.trending_score(refresh=True)
        updated_count += 1

        if updated_count % 100 == 0:
            db.session.commit()
            print(f"Updated {updated_count} posts...")

    db.session.commit()
    print(f" Updated trending scores for {updated_count} posts")


def update_new_posts_scores():
    from datetime import datetime, timedelta

    yesterday = datetime.utcnow() - timedelta(days=1)
    posts = Post.query.filter(Post.timestamp > yesterday).all()

    for post in posts:
        post.trending_score(refresh=True)

    db.session.commit()
    print(f"Updated trending scores for {len(posts)} recent posts")