import sqlalchemy as sa
from app import create_app, db
from sqlalchemy import inspect, text

app = create_app()

with app.app_context():
    try:
        inspector = inspect(db.engine)

        # Check if table exists
        if 'notification' in inspector.get_table_names():
            columns = [col['name'] for col in inspector.get_columns('notification')]

            if 'read' not in columns:
                print("Adding 'read' column to notification table...")
                with db.engine.connect() as conn:
                    conn.execute(text('ALTER TABLE notification ADD COLUMN read BOOLEAN DEFAULT FALSE'))
                    conn.commit()
                print("Successfully added 'read' column!")
            else:
                print("'read' column already exists")
        else:
            print("Notification table doesn't exist yet")
    except Exception as e:
        print(f"Error: {e}")