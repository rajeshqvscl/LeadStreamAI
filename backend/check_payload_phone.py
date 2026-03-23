import sys
import os
import json
sys.path.append(os.path.join(os.getcwd(), 'app'))
from database import get_db_connection
import psycopg2.extras

def check_leads():
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        # Find leads where phone column is null/empty but raw_payload has phone/phones
        cur.execute("SELECT id, first_name, last_name, phone, raw_payload FROM leads_raw LIMIT 100;")
        rows = cur.fetchall()
        found = False
        for r in rows:
            payload = r['raw_payload']
            if isinstance(payload, str):
                try:
                    payload = json.loads(payload)
                except:
                    payload = {}
            
            # Check if phone col is empty but payload has it
            has_payload_phone = payload.get('phone') or (payload.get('phones') and len(payload.get('phones', [])) > 0)
            if (not r['phone']) and has_payload_phone:
                print(f"ID: {r['id']}, NAME: {r['first_name']} {r['last_name']}, PHONE_COL: {r['phone']}, HAS_PAYLOAD_PHONE: True")
                found = True
        
        if not found:
            print("No leads found with phone only in payload.")
            
        cur.close()
        conn.close()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    check_leads()
