import sys
import os

sys.path.append(os.getcwd())

from app.api.drafts import DraftRequest, generate_draft
from app.database import get_db_connection

def verify_sravanthi_draft():
    conn = get_db_connection()
    cur = conn.cursor()
    # Using DictCursor because it's the default in get_db_connection
    cur.execute("SELECT id, first_name, last_name, email FROM leads_raw WHERE user_id = 9 LIMIT 1;")
    lead = cur.fetchone()
    if not lead:
        print("No leads found for user 9")
        return
    
    lead_id = lead['id']
    print(f"Generating draft for Lead ID: {lead_id} ({lead.get('first_name')} {lead.get('last_name')})")
    
    req = DraftRequest(lead_id=lead_id)
    # Simulate sravanthi logged in (user_id 9)
    res = generate_draft(req, user_id='9')
    
    print("\n--- GENERATED DRAFT ---")
    print(f"Subject: {res.get('subject')}")
    print("-" * 20)
    print(res.get('body'))
    print("-" * 20)

if __name__ == "__main__":
    verify_sravanthi_draft()
