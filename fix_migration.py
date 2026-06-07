import sqlite3

conn = sqlite3.connect('app.db')
cursor = conn.cursor()

cursor.execute('DROP TABLE IF EXISTS alembic_version')
cursor.execute('CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL)')
cursor.execute('INSERT INTO alembic_version (version_num) VALUES ("head")')

conn.commit()
conn.close()
print('Alembic version reset successfully')