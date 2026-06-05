import sqlalchemy as sa
import sqlalchemy.orm as so
from app import create_app, db
from app.models import User, Post, Message, Notification, Task
import os

app = create_app()

with app.app_context():
    try:
        from flask_migrate import upgrade
        from alembic.config import Config
        import os

        alembic_cfg = Config(os.path.join(os.getcwd(), "alembic.ini"))
        upgrade(alembic_cfg, "head")
        print("Database migrations completed")
    except Exception as e:
        print(f"Migration error: {e}")

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
            print("Admin user created")
    except Exception as e:
        print(f"Admin creation error: {e}")
        db.session.rollback()


@app.shell_context_processor
def make_shell_context():
    return {'sa': sa, 'so': so, 'db': db, 'User': User, 'Post': Post,
            'Message': Message, 'Notification': Notification, 'Task': Task}


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('FLASK_ENV', 'production') == 'development'
    app.run(host='0.0.0.0', port=port, debug=debug)