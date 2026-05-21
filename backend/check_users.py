import os
import psycopg2
from dotenv import load_dotenv
from pathlib import Path

env_path = Path(__file__).resolve().parent / "app" / ".env"
load_dotenv(dotenv_path=env_path)

DATABASE_URL = os.getenv("DATABASE_URL")

def check_users():
    print(f"Connecting to database to check users: {DATABASE_URL[:50]}...")
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor()
        
        # Check if users table exists
        cur.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_name = 'users'
            );
        """)
        exists = cur.fetchone()[0]
        print(f"Users table exists: {exists}")
        
        if exists:
            cur.execute("SELECT id, username, email, role, is_active, is_approved FROM users;")
            rows = cur.fetchall()
            print(f"Total users found: {len(rows)}")
            for r in rows:
                print(f"ID: {r[0]} | Username: {r[1]} | Email: {r[2]} | Role: {r[3]} | Active: {r[4]} | Approved: {r[5]}")
        
        cur.close()
        conn.close()
    except Exception as e:
        print(f"Error checking database: {e}")

if __name__ == "__main__":
