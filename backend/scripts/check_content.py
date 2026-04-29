import psycopg2
import os
from dotenv import load_dotenv
load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

def check_content():
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()
    cur.execute("SELECT content FROM prompts WHERE name = 'palak_mam_Draft_1';")
    row = cur.fetchone()
    if row:
        print(row[0])
    cur.close()
    conn.close()

if __name__ == "__main__":
    check_content()
