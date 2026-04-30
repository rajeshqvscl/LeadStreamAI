
import os
import psycopg2
from dotenv import load_dotenv

load_dotenv("app/.env")
db_url = os.getenv("DATABASE_URL")

def check_users():
    if not db_url:
        print("Error: DATABASE_URL not found in app/.env")
        return
    conn = psycopg2.connect(db_url)
    cur = conn.cursor()
    cur.execute("SELECT id, username, full_name, linkedin_url FROM users;")
    rows = cur.fetchall()
    for row in rows:
        print(f"ID: {row[0]} | Username: {row[1]} | Name: {row[2]} | LinkedIn: {row[3]}")
    cur.close()
    conn.close()

if __name__ == "__main__":
    check_users()
