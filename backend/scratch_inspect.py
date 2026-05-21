import os
import psycopg2
from dotenv import load_dotenv
from pathlib import Path

env_path = Path(__file__).resolve().parent / "app" / ".env"
load_dotenv(dotenv_path=env_path)

DATABASE_URL = os.getenv("DATABASE_URL")

def inspect():
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()
    cur.execute("SELECT id, first_name, last_name, company_name, email_status, email_draft FROM leads_raw WHERE email_draft IS NOT NULL LIMIT 10;")
    rows = cur.fetchall(how)
    print(f"Total rows with drafts: {len(rows)}")
    for r in rows:
        draft = r[5] or ""
        print(f"ID: {r[0]} | Name: {r[1]} {r[2]} | Company: {r[3]} | Status: {r[4]}")
        print(f"Subject in draft: {draft.splitlines()[0] if draft else 'None'}")
        print(f"Snippet: {draft[:120] if draft else ''}")
        print("-" * 50)
    cur.close()
    conn.close()

if __name__ == "__main__":
    inspect()
