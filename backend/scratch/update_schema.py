import os
import psycopg2
from dotenv import load_dotenv

load_dotenv("app/.env")
conn = psycopg2.connect(os.getenv("DATABASE_URL"))
cur = conn.cursor()

try:
    print("Adding sentiment_score and urgency_level columns...")
    cur.execute("ALTER TABLE leads_raw ADD COLUMN IF NOT EXISTS sentiment_score INTEGER")
    cur.execute("ALTER TABLE leads_raw ADD COLUMN IF NOT EXISTS urgency_level TEXT")
    conn.commit()
    print("Successfully updated schema.")
except Exception as e:
    print(f"Error updating schema: {e}")
    conn.rollback()
finally:
    cur.close()
    conn.close()
