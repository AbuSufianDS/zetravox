import sqlite3
import os

db_path = 'instance/app.db'
if not os.path.exists(db_path):
    db_path = 'app.db'

print(f'Using database: {db_path}')
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

cursor.execute('PRAGMA table_info(comment)')
columns = [col[1] for col in cursor.fetchall()]

if 'parent_id' not in columns:
    print('Adding parent_id column to comment table...')
    cursor.execute('ALTER TABLE comment ADD COLUMN parent_id INTEGER')
    print(' parent_id column added')
else:
    print(' parent_id column already exists')

cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='comment_reaction'")
if not cursor.fetchone():
    print('Creating comment_reaction table...')
    cursor.execute('''
        CREATE TABLE comment_reaction (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            comment_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            reaction VARCHAR(10) NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (comment_id) REFERENCES comment(id) ON DELETE CASCADE,
            FOREIGN KEY (user_id) REFERENCES user(id) ON DELETE CASCADE,
            UNIQUE(comment_id, user_id)
        )
    ''')
    cursor.execute('CREATE INDEX idx_comment_reaction_comment ON comment_reaction(comment_id)')
    cursor.execute('CREATE INDEX idx_comment_reaction_user ON comment_reaction(user_id)')
    print(' comment_reaction table created')
else:
    print(' comment_reaction table already exists')

cursor.execute('PRAGMA table_info(not_interested_post)')
columns = [col[1] for col in cursor.fetchall()]
if 'read' not in columns:
    print('Adding read column to not_interested_post...')
    cursor.execute('ALTER TABLE not_interested_post ADD COLUMN read BOOLEAN DEFAULT 0')
    print(' read column added')
else:
    print(' read column already exists')

conn.commit()
conn.close()
print('\n Database migration completed successfully!')