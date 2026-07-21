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
    max_overflow=30,    # 60 total ≤ PG max_connections=100 (single gunicorn worker)
    pool_pre_ping=True,
    pool_recycle=1800,  # recycle connections every 30m to avoid stale/leaked handles
    pool_timeout=3,     # fail fast: under load a thread waiting on the pool blocks the
                        # whole threadpool queue — 3s keeps threads churning, 10s caused
                        # the 2026-07-21 congestion collapse to self-sustain for 26 min
    connect_args={"options": "-c statement_timeout=30000"},  # no query may run >30s
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()