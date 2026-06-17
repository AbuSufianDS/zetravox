from app import create_app, db
from app.models import Like

app = create_app()
with app.app_context():
    corrupted_likes = Like.query.filter(Like.post_id == None).all()
    print(f"Found {len(corrupted_likes)} corrupted likes")
    for like in corrupted_likes:
        db.session.delete(like)
    db.session.commit()
    print("Fixed! Corrupted likes deleted.")