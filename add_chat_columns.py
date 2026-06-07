import sqlite3

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

conn.commit()
conn.close()
print('ChatMessage columns updated successfully')