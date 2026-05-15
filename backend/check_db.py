import sqlite3
import os

db_path = "ghawy.db"
if not os.path.exists(db_path):
    print("No db")
else:
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.execute("SELECT name FROM sqlite_master WHERE type='table'")
    print(c.fetchall())
