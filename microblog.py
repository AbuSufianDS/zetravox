import sqlalchemy as sa
import sqlalchemy.orm as so
from app import create_app, db
from app.models import User, Post, Message, Notification, Task
import os

app = create_app()


@app.shell_context_processor
def make_shell_context():
    return {'sa': sa, 'so': so, 'db': db, 'User': User, 'Post': Post,
            'Message': Message, 'Notification': Notification, 'Task': Task}


def init_admin():
    with app.app_context():
        try:
            inspector = sa.inspect(db.engine)
            if not inspector.has_table('user'):
                print("Tables not created yet. Run migrations first.")
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
            print(f"Error initializing admin: {e}")
            print("Please run 'flask db upgrade' first to create all tables")


if __name__ == '__main__':
    init_admin()

    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('FLASK_ENV', 'production') == 'development'
    app.run(host='0.0.0.0', port=port, debug=debug)