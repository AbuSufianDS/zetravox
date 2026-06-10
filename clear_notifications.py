import sqlite3

conn = sqlite3.connect('app.db')
cursor = conn.cursor()
cursor.execute('DELETE FROM notification')
conn.commit()
print('All notifications cleared')
conn.close()
