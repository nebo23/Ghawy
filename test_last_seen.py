import os
import sys
from datetime import datetime, timedelta

# Add backend to path
sys.path.append(os.path.abspath('backend'))

from app.database import SessionLocal
from app.models import User

db = SessionLocal()

one_min_ago = datetime.utcnow() - timedelta(seconds=60)
print(f"One min ago: {one_min_ago}")

users = db.query(User).all()
for u in users:
    print(f"User {u.id}: {u.last_seen} (type: {type(u.last_seen)})")

active_users = db.query(User).filter(User.last_seen >= one_min_ago).all()
print("Active users via filter:")
for u in active_users:
    print(f"  {u.id}")

db.close()
