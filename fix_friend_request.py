from app import create_app, db
from sqlalchemy import text

app = create_app()

with app.app_context():
    try:
        db.session.execute(text("DROP TABLE IF EXISTS friend_request"))
        db.session.commit()
        print(" Dropped friend_request table")

        db.create_all()
        print(" Friend request table recreated successfully")

    except Exception as e:
        print(f"Error: {e}")
        db.session.rollback()
