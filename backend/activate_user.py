import sqlite3
conn = sqlite3.connect(r"c:\Users\nabil\Code\Payment method\backend\community.db")
conn.execute("UPDATE users SET is_verified=1, is_active=1, is_admin=1 WHERE email='test@test.com'")
conn.commit()
rows = conn.execute("SELECT id, full_name, email, is_verified, is_active, is_admin FROM users").fetchall()
for r in rows:
    print(r)
conn.close()
