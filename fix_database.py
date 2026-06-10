import sqlite3
from werkzeug.security import generate_password_hash


def fix_database():
    conn = sqlite3.connect('app.db')
    cursor = conn.cursor()

    cursor.execute("PRAGMA table_info(user)")
    existing_columns = [col[1] for col in cursor.fetchall()]

    new_columns = [
        ('cover_pic', 'VARCHAR(200)', "'default_cover.jpg'"),
        ('relationship_status', 'VARCHAR(50)', 'NULL'),
        ('work', 'VARCHAR(100)', 'NULL'),
        ('education', 'VARCHAR(100)', 'NULL'),
        ('location', 'VARCHAR(100)', 'NULL'),
        ('website', 'VARCHAR(200)', 'NULL'),
        ('birthday', 'VARCHAR(20)', 'NULL'),
        ('gender', 'VARCHAR(20)', 'NULL'),
        ('interested_in', 'VARCHAR(100)', 'NULL'),
        ('phone', 'VARCHAR(20)', 'NULL'),
        ('notify_push_shares', 'BOOLEAN', '1'),
        ('notify_push_friend_requests', 'BOOLEAN', '1'),
        ('notify_push_messages', 'BOOLEAN', '1'),
        ('notify_email_shares', 'BOOLEAN', '0'),
        ('notify_email_friend_requests', 'BOOLEAN', '0'),
        ('notify_email_messages', 'BOOLEAN', '0'),
        ('show_email', 'BOOLEAN', '0'),
        ('show_last_seen', 'BOOLEAN', '1'),
        ('allow_comments', 'BOOLEAN', '1'),
        ('allow_messages', 'BOOLEAN', '1'),
        ('theme_preference', 'VARCHAR(20)', "'light'"),
    ]

    for col_name, col_type, default_value in new_columns:
        if col_name not in existing_columns:
            try:
                sql = f'ALTER TABLE user ADD COLUMN {col_name} {col_type} DEFAULT {default_value}'
                cursor.execute(sql)
                print(f"Added column: {col_name}")
            except Exception as e:
                print(f"Error adding {col_name}: {e}")
        else:
            print(f"Column already exists: {col_name}")

    cursor.execute("PRAGMA table_info(notification)")
    notification_cols = [col[1] for col in cursor.fetchall()]

    if 'read' not in notification_cols:
        try:
            cursor.execute('ALTER TABLE notification ADD COLUMN read BOOLEAN DEFAULT 0')
            print("Added column: notification.read")
        except Exception as e:
            print(f"Error adding notification.read: {e}")

    cursor.execute("SELECT * FROM user WHERE username = 'Sufian'")
    admin = cursor.fetchone()

    if not admin:
        password_hash = generate_password_hash('SufianAdmin12345')
        cursor.execute('''
            INSERT INTO user (
                username, email, password_hash, is_admin, is_verified, 
                about_me, profile_pic, cover_pic, points, is_private
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            'Sufian',
            'abusufian3344md@gmail.com',
            password_hash,
            1,
            1,
            '',
            'default.jpg',
            'default_cover.jpg',
            0,
            0
        ))
        print("Admin user created successfully!")
    else:
        print("Admin user already exists")

    conn.commit()
    conn.close()
    print("Database fix completed!")


if __name__ == '__main__':
    fix_database()
