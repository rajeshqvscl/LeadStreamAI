import sys
import psycopg2
from app.database import get_db_connection

def test():
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Check leads_raw for recent inserts
        cur.execute("SELECT id, email, source, user_id, email_status, validation_status FROM leads_raw ORDER BY id DESC LIMIT 5")
        rows = cur.fetchall()
        print("Recent leads:")
        for r in rows:
            print(r)
            
        cur.close()
        conn.close()
    except Exception as e:
        print("Error:", e)

if __name__ == '__main__':
    test()
