import os
from app.database import get_db_connection

def check_columns():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name = 'leads_raw'")
    columns = [row['column_name'] for row in cur.fetchall()]
    cur.close()
    conn.close()
    
    needed = ['reply_intent', 'meeting_link', 'meeting_time']
    for col in needed:
        if col in columns:
            print(f"SUCCESS: Column {col} exists.")
        else:
            print(f"FAIL: Column {col} is MISSING.")

if __name__ == "__main__":
    check_columns()
