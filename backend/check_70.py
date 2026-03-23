import sys
import os
import json
sys.path.append(os.path.join(os.getcwd(), 'app'))
from database import get_db_connection
import psycopg2.extras

def check_lead(id):
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        cur.execute("SELECT raw_payload FROM leads_raw WHERE id = %s;", (id,))
        row = cur.fetchone()
        payload = row['raw_payload']
        if isinstance(payload, str):
            payload = json.loads(payload)
        
        print("KEYS:", list(payload.keys()))
        if 'phones' in payload:
            print("PHONES:", json.dumps(payload['phones'], indent=2))
        if 'phone' in payload:
            print("PHONE:", payload['phone'])
            
        cur.close()
        conn.close()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    check_lead(70)
