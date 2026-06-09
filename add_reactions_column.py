import sqlite3

conn = sqlite3.connect('app.db')
cursor = conn.cursor()

try:
    cursor.execute('ALTER TABLE chat_message ADD COLUMN reactions TEXT DEFAULT "{}"')
    print('Added reactions column')
except Exception as e:
    print(f'Error adding reactions: {e}')

conn.commit()
conn.close()
print('Done!')
