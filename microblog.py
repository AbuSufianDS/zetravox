import sqlalchemy as sa
import sqlalchemy.orm as so
from app import create_app, db
from app.models import User, Post, Message, Notification, Task
import os
import sys

app = create_app()


def run_migrations():
    with app.app_context():
        try:
            from flask_migrate import upgrade, migrate, init, stamp
            from flask_migrate import Migrate
            import subprocess

            print("Checking database migrations...")

            if not os.path.exists('migrations'):
                print("Initializing migrations...")
                subprocess.run([sys.executable, '-m', 'flask', 'db', 'init'], check=True)
                print("Generating initial migration...")
                subprocess.run([sys.executable, '-m', 'flask', 'db', 'migrate', '-m', 'initial_migration'], check=True)

            print("Applying migrations...")
            subprocess.run([sys.executable, '-m', 'flask', 'db', 'upgrade'], check=True)
            print("Migrations completed successfully!")

        except Exception as e:
            print(f"Migration error: {e}")
            print("Falling back to db.create_all()...")
            db.create_all()
            print("Tables created successfully")


def create_admin_user():
    with app.app_context():
        try:
            from sqlalchemy import inspect
            inspector = inspect(db.engine)

            if not inspector.has_table('user'):
                print("Tables not ready yet, skipping admin creation")
                return

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
                print(f"Admin user already exists: {admin.username}")
        except Exception as e:
            print(f"Admin creation skipped: {e}")


if os.environ.get('RENDER') or os.environ.get('FLASK_ENV') == 'production':
    run_migrations()
else:
    with app.app_context():
        db.create_all()
        print("Database tables created")

create_admin_user()


@app.shell_context_processor
def make_shell_context():
    return {'sa': sa, 'so': so, 'db': db, 'User': User, 'Post': Post,
            'Message': Message, 'Notification': Notification, 'Task': Task}


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('FLASK_ENV', 'production') == 'development'
    app.run(host='0.0.0.0', port=port, debug=debug)