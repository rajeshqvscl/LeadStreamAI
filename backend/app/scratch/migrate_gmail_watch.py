import psycopg2
import os
from dotenv import load_dotenv

def migrate():
    load_dotenv()
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        print("DATABASE_URL not found in .env")
        return

    conn = psycopg2.connect(db_url)
    cur = conn.cursor()

    try:
        # 1. Update users table
        print("Migrating 'users' table...")
        cur.execute("""
            ALTER TABLE users 
            ADD COLUMN IF NOT EXISTS google_access_token TEXT,
            ADD COLUMN IF NOT EXISTS google_refresh_token TEXT,
            ADD COLUMN IF NOT EXISTS google_token_expiry TIMESTAMP WITH TIME ZONE,
            ADD COLUMN IF NOT EXISTS google_linked_at TIMESTAMP WITH TIME ZONE;
        """)

        # 2. Update leads_raw table
        print("Migrating 'leads_raw' table...")
        cur.execute("""
            ALTER TABLE leads_raw 
            ADD COLUMN IF NOT EXISTS gmail_thread_id TEXT;
        """)

        conn.commit()
        print("Migration successful!")
    except Exception as e:
        conn.rollback()
        print(f"Migration failed: {e}")
    finally:
        cur.close()
        conn.close()

if __name__ == "__main__":
    migrate()
