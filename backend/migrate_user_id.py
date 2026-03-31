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
    
    # 1. Add user_id to leads_raw
    try:
        cur.execute("ALTER TABLE leads_raw ADD COLUMN IF NOT EXISTS user_id INTEGER;")
        print("Updated leads_raw: user_id column ensured.")
    except Exception as e:
        conn.rollback()
        print(f"Error adding user_id to leads_raw: {e}")
        
    # 2. Add user_id to activity_log
    try:
        cur.execute("ALTER TABLE activity_log ADD COLUMN IF NOT EXISTS user_id INTEGER;")
        print("Updated activity_log: user_id column ensured.")
    except Exception as e:
        conn.rollback()
        print(f"Error adding user_id to activity_log: {e}")
        
    # 3. Get admin ID
    try:
        cur.execute("SELECT id FROM users WHERE username = 'admin' LIMIT 1;")
        admin_row = cur.fetchone()
        if admin_row:
            admin_id = admin_row[0]
            print(f"Admin User ID found: {admin_id}")
            
            # 4. Migrate orphaned leads
            cur.execute("UPDATE leads_raw SET user_id = %s WHERE user_id IS NULL;", (admin_id,))
            print(f"Migrated {cur.rowcount} orphaned leads to Admin.")
            
            # 5. Migrate orphaned logs
            cur.execute("UPDATE activity_log SET user_id = %s WHERE user_id IS NULL;", (admin_id,))
            print(f"Migrated {cur.rowcount} orphaned activity logs to Admin.")
        else:
            print("Admin user not found. Migration skipped.")
            
    except Exception as e:
        conn.rollback()
        print(f"Critical error during migration: {e}")
        
    conn.commit()
    cur.close()
    conn.close()
    print("Migration complete.")

if __name__ == '__main__':
    migrate()
