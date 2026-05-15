"""Reset password for test user so we can log in."""
import sqlite3
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
new_hash = pwd_context.hash("Test123!")

conn = sqlite3.connect(r"c:\Users\nabil\Code\Payment method\backend\community.db")
conn.execute("UPDATE users SET hashed_password=?, is_verified=1, is_active=1 WHERE email='test@test.com'", (new_hash,))
conn.commit()
rows = conn.execute("SELECT id, full_name, email, is_verified, is_active FROM users").fetchall()
for r in rows:
    print(r)
conn.close()
print("Password reset to Test123!")
