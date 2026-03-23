import psycopg2
import os
from dotenv import load_dotenv
from pathlib import Path

env_path = Path(__file__).resolve().parent / "app" / ".env"
load_dotenv(dotenv_path=env_path, override=True)
DATABASE_URL = os.getenv("DATABASE_URL")

conn = psycopg2.connect(DATABASE_URL)
cur = conn.cursor()

columns = [
    "validation_status TEXT DEFAULT 'PENDING'",
    "email_draft TEXT",
    "email_status TEXT DEFAULT 'PENDING_APPROVAL'",
    "persona TEXT",
    "fit_score INTEGER DEFAULT 0",
    "industry TEXT",
    "city TEXT",
    "country TEXT",
    "linkedin_url TEXT",
    "is_unsubscribed BOOLEAN DEFAULT FALSE",
    "campaign_id INTEGER",
    "company_id INTEGER",
    "family_office_name TEXT",
    "phone TEXT"
]

for col in columns:
    try:
        cur.execute(f"ALTER TABLE leads_raw ADD COLUMN {col};")
        conn.commit()
    except psycopg2.errors.DuplicateColumn:
        conn.rollback()
    except Exception as e:
        conn.rollback()
        print(f"Skipped {col}: {e}")

# fix existing linkedin if it has the wrong name
try:
    cur.execute("ALTER TABLE leads_raw RENAME COLUMN linkedin TO linkedin_url;")
    conn.commit()
except Exception:
    conn.rollback()

print("Migration completed.")
cur.close()
conn.close()
