import sys
import os
sys.path.append(os.path.join(os.getcwd(), 'app'))
from database import get_db_connection
import psycopg2.extras

def check_leads():
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        cur.execute("SELECT id, first_name, last_name, phone FROM leads_raw WHERE phone IS NOT NULL AND phone != '' LIMIT 5;")
        rows = cur.fetchall()
        for r in rows:
            print(f"ID: {r['id']}, NAME: {r['first_name']} {r['last_name']}, PHONE: {r['phone']}")
        cur.close()
        conn.close()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    check_leads()
