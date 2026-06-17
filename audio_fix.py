import sqlite3

db_path = 'app.db'

try:
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute('ALTER TABLE chat_message ADD COLUMN audio_url VARCHAR(256)')
    conn.commit()
    print(" Added audio_url column successfully!")
    conn.close()
except sqlite3.OperationalError as e:
    if 'duplicate column name' in str(e):
        print(" Column already exists!")
    else:
        print(f"Error: {e}")