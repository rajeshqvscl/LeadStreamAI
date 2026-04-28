import sys
import os

sys.path.append(os.getcwd())

from app.database import get_db_connection

def check_leads():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT id, email, user_id, is_responded FROM leads_raw;")
    rows = cur.fetchall()
    for row in rows:
        print(row)
    cur.close()
    conn.close()

if __name__ == "__main__":
    check_leads()
