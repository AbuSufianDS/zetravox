import sqlalchemy as sa
import sqlalchemy.orm as so
from app import create_app, db
from app.models import User, Post, Message, Notification, Task
import os
import sys

app = create_app()


@app.shell_context_processor
def make_shell_context():
    return {'sa': sa, 'so': so, 'db': db, 'User': User, 'Post': Post,
            'Message': Message, 'Notification': Notification, 'Task': Task}


def init_database():
    with app.app_context():
        try:
            from alembic.config import Config
            from alembic import command
            from flask_migrate import upgrade

            alembic_cfg = Config("alembic.ini")
            upgrade(alembic_cfg, "head")
            print("Database migrations completed successfully")
        except Exception as e:
            print(f"Migration warning: {e}")

        try:
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
                print("Admin user created: Sufian / SufianAdmin12345")
            else:
                print("Admin user already exists")
        except Exception as e:
            print(f"Admin creation error: {e}")
            db.session.rollback()


if __name__ == '__main__':
    init_database()

    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('FLASK_ENV', 'production') == 'development'

    app.run(host='0.0.0.0', port=port, debug=debug)