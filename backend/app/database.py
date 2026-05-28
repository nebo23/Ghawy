from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import os
from dotenv import load_dotenv
from pathlib import Path # علشان نحدد مكان الصور اللي عي الجهاز 

# Resolve .env using an absolute path anchored to *this* file's location
# so it works regardless of the current working directory.
ENV_PATH = Path(__file__).resolve().parents[1] / ".env"
load_dotenv(dotenv_path=ENV_PATH)

# بنقرأ رابط الداتابيز السري من غير ما نكشفه في الكود
DATABASE_URL = os.getenv("DATABASE_URL")

# Create engine with PostgreSQL connection pooling (Step 8 included)
engine = create_engine(
    DATABASE_URL,
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True, # To make a check 
    pool_recycle=300 # بيتحدد كل 5 دقايق
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()