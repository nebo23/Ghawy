from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import os
from dotenv import load_dotenv
from pathlib import Path # علشان نحدد مكان الصور اللي عي الجهاز 

# Resolve .env using an absolute path anchored to *this* file's location
# so it works regardless of the current working directory.
ENV_PATH = Path(__file__).resolve().parents[1] / ".env"
load_dotenv(dotenv_path=ENV_PATH)

# Read DATABASE_URL securely
DATABASE_URL = os.getenv("DATABASE_URL")

# Strict guard check at startup
if not DATABASE_URL or not DATABASE_URL.startswith("postgresql"):
    raise RuntimeError("🚨 DATABASE_URL must be a valid PostgreSQL connection string!")

# Create engine with PostgreSQL production-grade connection pooling
engine = create_engine(
    DATABASE_URL,
    pool_size=30,
    max_overflow=20,
    pool_pre_ping=True,
    pool_recycle=1800,  # recycle connections every 30m to avoid stale/leaked handles
    pool_timeout=10,    # fail fast (10s) instead of default 30s to prevent request pile-up
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()