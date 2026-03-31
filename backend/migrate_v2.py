import os
import psycopg2
from dotenv import load_dotenv
from pathlib import Path

# Load env
env_path = Path('app/.env').resolve()
load_dotenv(dotenv_path=env_path)
DATABASE_URL = os.getenv('DATABASE_URL')

def migrate():
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()
    
    # 1. Add user_id to campaigns
    try:
        cur.execute("ALTER TABLE campaigns ADD COLUMN IF NOT EXISTS user_id INTEGER;")
        print("Updated campaigns: user_id column ensured.")
    except Exception as e:
        conn.rollback()
        print(f"Error campaigns: {e}")
        
    # 2. Add user_id to family_offices
    try:
        cur.execute("ALTER TABLE family_offices ADD COLUMN IF NOT EXISTS user_id INTEGER;")
        print("Updated family_offices: user_id column ensured.")
    except Exception as e:
        conn.rollback()
        print(f"Error family_offices: {e}")
        
    conn.commit()
    cur.close()
    conn.close()
    print("Migration V2 complete.")

if __name__ == '__main__':
    migrate()
