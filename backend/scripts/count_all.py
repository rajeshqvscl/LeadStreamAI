import psycopg2
import os
from dotenv import load_dotenv

load_dotenv("app/.env")
url = os.getenv("DATABASE_URL")
try:
    conn = psycopg2.connect(url)
    cur = conn.cursor()
    tables = [
        'leads_raw', 'leads', 'email_drafts', 'drafts', 'campaigns', 
        'family_offices', 'companies', 'company_registry', 'users'
    ]
    for table in tables:
        try:
            cur.execute(f"SELECT COUNT(*) FROM {table}")
            print(f"{table}: {cur.fetchone()[0]}")
        except:
            print(f"{table}: Not found or error")
            conn.rollback()
    cur.close()
    conn.close()
except Exception as e:
    print(f"Error: {e}")
