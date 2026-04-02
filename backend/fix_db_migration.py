import os
import psycopg2
from dotenv import load_dotenv

load_dotenv("app/.env")
DATABASE_URL = os.getenv("DATABASE_URL")
if DATABASE_URL and DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

conn = psycopg2.connect(DATABASE_URL)
cur = conn.cursor()

try:
    # 1. Cleanup duplicates (keep only one record per email)
    print("Cleaning up duplicates...")
    cur.execute("""
        DELETE FROM leads_raw a
        USING (
            SELECT MIN(ctid) as ctid, email
            FROM leads_raw 
            GROUP BY email 
            HAVING COUNT(*) > 1
        ) b
        WHERE a.email = b.email AND a.ctid != b.ctid;
    """)
    print(f"Deleted {cur.rowcount} duplicate rows.")

    # 2. Add UNIQUE constraint
    print("Adding UNIQUE constraint on email...")
    cur.execute("ALTER TABLE leads_raw ADD CONSTRAINT unique_email UNIQUE (email);")
    conn.commit()
    print("Database migration successful.")
except Exception as e:
    conn.rollback()
    print(f"Migration error: {e}")
finally:
    cur.close()
    conn.close()
