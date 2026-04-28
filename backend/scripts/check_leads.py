import os
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

load_dotenv("app/.env")
DATABASE_URL = os.getenv("DATABASE_URL")

def check_leads():
    try:
        conn = psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)
        cur = conn.cursor()
        cur.execute("SELECT id, first_name, last_name, source, persona FROM leads_raw WHERE last_name IN ('Johnson', 'Brown', 'Sharma') LIMIT 10;")
        rows = cur.fetchall()
        for r in rows:
            print(r)
        cur.close()
        conn.close()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    check_leads()
