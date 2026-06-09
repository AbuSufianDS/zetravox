import sqlite3
import json

conn = sqlite3.connect('app.db')
cursor = conn.cursor()

cursor.execute("PRAGMA table_info(chat_message)")
existing_columns = [col[1] for col in cursor.fetchall()]

if 'is_delivered' not in existing_columns:
    cursor.execute('ALTER TABLE chat_message ADD COLUMN is_delivered BOOLEAN DEFAULT 0')
    print('Added is_delivered column')
else:
    print('is_delivered column already exists')

if 'image_url' not in existing_columns:
    cursor.execute('ALTER TABLE chat_message ADD COLUMN image_url VARCHAR(500)')
    print('Added image_url column')
else:
    print('image_url column already exists')

if 'reply_to_id' not in existing_columns:
    cursor.execute('ALTER TABLE chat_message ADD COLUMN reply_to_id INTEGER DEFAULT NULL')
    print('Added reply_to_id column')
else:
    print('reply_to_id column already exists')

if 'reactions' not in existing_columns:
    cursor.execute('ALTER TABLE chat_message ADD COLUMN reactions TEXT DEFAULT "{}"')
    print('Added reactions column')
else:
    print('reactions column already exists')

conn.commit()
conn.close()
print('All ChatMessage columns updated successfully!')