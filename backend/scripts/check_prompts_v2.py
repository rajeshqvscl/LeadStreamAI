import psycopg2
import os
from dotenv import load_dotenv
load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

def check_prompts():
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()
    cur.execute("SELECT id, name, prompt_type FROM prompts WHERE prompt_type = 'CUSTOM_DRAFT';")
    rows = cur.fetchall()
    for row in rows:
        print(row)
    cur.close()
    conn.close()

if __name__ == "__main__":
    check_prompts()
