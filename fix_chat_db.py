import sqlite3

conn = sqlite3.connect('app.db')
cursor = conn.cursor()

try:
    cursor.execute('ALTER TABLE chat_message ADD COLUMN reply_to_id INTEGER DEFAULT NULL')
    print('Added reply_to_id column')
except Exception as e:
    print(f'reply_to_id: {e}')

try:
    cursor.execute('ALTER TABLE chat_message ADD COLUMN reactions TEXT DEFAULT "{}"')
    print('Added reactions column')
except Exception as e:
    print(f'reactions: {e}')

conn.commit()
conn.close()
print('Done!')
