import psycopg2
import os
from dotenv import load_dotenv

load_dotenv()

def get_db_connection():
    return psycopg2.connect(os.getenv("DATABASE_URL"))

def check_schema():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT column_name, data_type FROM information_schema.columns WHERE table_name = 'leads_raw' ORDER BY ordinal_position")
    columns = cur.fetchall()
    for col in columns:
        print(f"{col[0]}: {col[1]}")
    cur.close()
    conn.close()

if __name__ == "__main__":
    check_schema()
