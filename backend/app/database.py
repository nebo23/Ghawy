from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import os
from dotenv import load_dotenv
from pathlib import Path

# Resolve .env using an absolute path anchored to *this* file's location
# so it works regardless of the current working directory.
ENV_PATH = Path(__file__).resolve().parents[1] / ".env"
load_dotenv(dotenv_path=ENV_PATH)

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./community.db")

# ── Fix relative SQLite paths ──────────────────────────────────────
# sqlite:///./community.db is relative to CWD. If the server is started
# from a directory other than backend/, the app opens/creates a *different*
# database file — so codes saved during registration are never found during
# verification.  Resolve relative paths to absolute, anchored to backend/.
if DATABASE_URL.startswith("sqlite"):
    _BACKEND_DIR = Path(__file__).resolve().parents[1]  # …/backend
    # Extract the path portion after 'sqlite:///'
    _db_path_str = DATABASE_URL.split("///", 1)[1] if "///" in DATABASE_URL else "community.db"
    _db_path = Path(_db_path_str)
    if not _db_path.is_absolute():
        _db_path = _BACKEND_DIR / _db_path
    DATABASE_URL = f"sqlite:///{_db_path}"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()