# save as fix_chat_columns.py
import sqlite3

conn = sqlite3.connect('app.db')
cursor = conn.cursor()

cursor.execute("PRAGMA table_info(chat_message)")
existing = [col[1] for col in cursor.fetchall()]

if 'image_url' not in existing:
    cursor.execute('ALTER TABLE chat_message ADD COLUMN image_url VARCHAR(500)')
    print('Added image_url column')

if 'is_delivered' not in existing:
    cursor.execute('ALTER TABLE chat_message ADD COLUMN is_delivered BOOLEAN DEFAULT 0')
    print('Added is_delivered column')

conn.commit()
conn.close()
print('Chat table updated!')