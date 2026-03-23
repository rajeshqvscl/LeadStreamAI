import psycopg2
import os
import random
from dotenv import load_dotenv
from pathlib import Path

env_path = Path("app/.env").resolve()
load_dotenv(dotenv_path=env_path, override=True)
DATABASE_URL = os.getenv("DATABASE_URL")

conn = psycopg2.connect(DATABASE_URL)
cur = conn.cursor()

def categorize_lead(title):
    title = str(title).lower() if title else ""
    if any(x in title for x in ["founder", "ceo", "co-founder", "owner"]):
        return "FOUNDER", random.randint(85, 99)
    elif any(x in title for x in ["investor", "partner", "capital", "vc"]):
        if "partner" in title and "venture" not in title:
            return "PARTNER", random.randint(70, 89)
        return "INVESTOR", random.randint(80, 95)
    elif "partner" in title:
        return "PARTNER", random.randint(65, 85)
    else:
        return "OTHER", random.randint(40, 75)

cur.execute("SELECT id, raw_payload FROM leads_raw WHERE fit_score = 0 OR fit_score IS NULL;")
rows = cur.fetchall()

for row in rows:
    lid = row[0]
    payload = row[1] or {}
    title = payload.get("current_title", "")
    persona, score = categorize_lead(title)
    
    cur.execute("UPDATE leads_raw SET persona = %s, fit_score = %s WHERE id = %s", (persona, score, lid))

conn.commit()
cur.close()
conn.close()
print(f"Updated {len(rows)} leads.")
