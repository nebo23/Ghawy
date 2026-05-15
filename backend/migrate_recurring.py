"""
Migration script: Add recurring/subscription columns to users and payments tables.
Run once: python migrate_recurring.py
"""
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent / "community.db"

if not DB_PATH.exists():
    print(f"❌ Database not found at {DB_PATH}")
    exit(1)

conn = sqlite3.connect(str(DB_PATH))
cursor = conn.cursor()

columns_to_add = [
    ("users", "card_token", "TEXT"),
    ("users", "shopper_reference", "TEXT"),
    ("users", "subscription_type", "TEXT DEFAULT 'monthly'"),
    ("users", "subscription_start", "DATETIME"),
    ("users", "subscription_end", "DATETIME"),
    ("users", "last_charged_at", "DATETIME"),
    ("users", "next_charge_at", "DATETIME"),
    ("payments", "is_recurring", "BOOLEAN DEFAULT 0"),
    ("payments", "recurring_cycle", "INTEGER DEFAULT 0"),
]

for table, col, col_type in columns_to_add:
    try:
        cursor.execute(f"ALTER TABLE {table} ADD COLUMN {col} {col_type}")
        print(f"[OK] Added {table}.{col}")
    except Exception as e:
        print(f"[SKIP] {table}.{col}: {e}")

conn.commit()
conn.close()
print("\n[DONE] Migration complete!")
