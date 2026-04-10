import psycopg2
import os
from dotenv import load_dotenv

load_dotenv("app/.env")
url = os.getenv("DATABASE_URL")
print(f"Connecting to: {url[:30]}...")
try:
    conn = psycopg2.connect(url)
    cur = conn.cursor()
    cur.execute("SELECT version();")
    print(f"Version: {cur.fetchone()}")
    cur.execute("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public';")
    print(f"Tables: {[r[0] for r in cur.fetchall()]}")
    cur.close()
    conn.close()
except Exception as e:
    print(f"Error: {e}")
