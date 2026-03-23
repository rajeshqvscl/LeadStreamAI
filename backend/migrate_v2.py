import psycopg2
import os
from dotenv import load_dotenv
from pathlib import Path

env_path = Path("app/.env").resolve()
load_dotenv(dotenv_path=env_path, override=True)
DATABASE_URL = os.getenv("DATABASE_URL")

conn = psycopg2.connect(DATABASE_URL)
cur = conn.cursor()

# 1. Add phone column
try:
    cur.execute("ALTER TABLE leads_raw ADD COLUMN phone TEXT;")
    conn.commit()
    print("Added phone column.")
except psycopg2.errors.DuplicateColumn:
    conn.rollback()
    print("Phone column already exists.")

# 2. Create activity_log table
try:
    cur.execute("""
        CREATE TABLE IF NOT EXISTS activity_log (
            id SERIAL PRIMARY KEY,
            lead_id INTEGER REFERENCES leads_raw(id) ON DELETE CASCADE,
            action TEXT NOT NULL,
            details TEXT,
            performed_by TEXT DEFAULT 'system',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)
    conn.commit()
    print("Created activity_log table.")
except Exception as e:
    conn.rollback()
    print(f"Error creating activity_log: {e}")

cur.close()
conn.close()
print("Migration completed.")
