import os
import sys
from app import create_app, db
from app.models import User

app = create_app()


def init_database():
    with app.app_context():
        try:
            db.create_all()
            print("Tables created successfully")

            admin = User.query.filter_by(username='Sufian').first()
            if not admin:
                admin = User(
                    username='Sufian',
                    email='abusufian3344md@gmail.com',
                    is_admin=True,
                    is_verified=True
                )
                admin.set_password('SufianAdmin12345')
                db.session.add(admin)
                db.session.commit()
                print("Admin user created: Sufian")
            else:
                print(f"Admin user already exists: {admin.username}")

        except Exception as e:
            print(f"Error: {e}")
            sys.exit(1)


if __name__ == '__main__':
    init_database()