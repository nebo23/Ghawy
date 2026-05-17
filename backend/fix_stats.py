import os, sys
sys.path.insert(0, os.path.abspath('backend'))
from app.database import engine, SessionLocal
from app.models import User
from sqlalchemy import update

db = SessionLocal()

db.execute(update(User).where(User.level == None).values(level=1))
db.execute(update(User).where(User.xp == None).values(xp=0))
db.execute(update(User).where(User.streak_days == None).values(streak_days=0))

db.commit()
print("Fixed level, xp, and streak_days.")
