"""Migration: Add failed_charge_count column to users table."""
from app.database import engine
from sqlalchemy import text

with engine.connect() as conn:
    conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS failed_charge_count INTEGER DEFAULT 0"))
    conn.commit()
    print("✅ Migration complete: failed_charge_count added")
