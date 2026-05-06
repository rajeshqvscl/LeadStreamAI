import psycopg2
import os, sys
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(dotenv_path=Path(__file__).resolve().parent.parent / "app/.env")

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    print("ERROR: DATABASE_URL not set")
    sys.exit(1)

conn = psycopg2.connect(DATABASE_URL)
cur = conn.cursor()
cur.execute("SELECT name, description, content FROM prompts WHERE name = 'palak_mam_Draft_1'")
row = cur.fetchone()
if row:
    print(f"Name: {row[0]}")
    print(f"Desc: {row[1]}")
    print(f"\n--- CONTENT ---\n{row[2]}")
else:
    print("Template NOT FOUND in DB.")
cur.close()
conn.close()
