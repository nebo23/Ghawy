import sqlite3
from datetime import datetime, timedelta

conn = sqlite3.connect('backend/community.db')
cursor = conn.cursor()

one_min_ago = (datetime.utcnow() - timedelta(seconds=60)).strftime('%Y-%m-%d %H:%M:%S.%f')
cursor.execute("SELECT id FROM users WHERE last_seen >= ?", (one_min_ago,))
print("Active ids (python one_min_ago):", cursor.fetchall())

cursor.execute("SELECT id FROM users WHERE last_seen >= datetime('now', '-1 minutes')")
print("Active ids (sqlite datetime('now')):", cursor.fetchall())

cursor.execute("SELECT id, last_seen FROM users WHERE id=1")
print("User 1:", cursor.fetchone())
