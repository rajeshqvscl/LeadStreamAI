"""
Show full details for specific leads before moving them.
"""
import sys, os
from dotenv import load_dotenv

for env_loc in ["app/.env", "backend/app/.env", "../backend/app/.env"]:
    if os.path.exists(env_loc):
        load_dotenv(env_loc)
        break

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
import psycopg2
from psycopg2.extras import RealDictCursor

db_url = os.getenv('DATABASE_URL')
if not db_url:
    print("DATABASE_URL not found")
    sys.exit(1)

db_url = db_url.strip().strip("'").strip('"').replace('postgres://', 'postgresql://', 1)
conn = psycopg2.connect(db_url, cursor_factory=RealDictCursor, connect_timeout=10)
cur = conn.cursor()

# Lead IDs to check (Kajal: 2498, 2499, 7749 | Ayush: 478, 7609, 1771)
lead_ids = [2498, 2499, 7749, 478, 7609, 1771]

for lid in lead_ids:
    cur.execute("""
        SELECT id, first_name, last_name, email, company_name, 
               email_status, reply_intent, is_responded, user_id,
               draft_template_used, remarks,
               updated_at, created_at, source
        FROM leads_raw WHERE id = %s
    """, (lid,))
    l = cur.fetchone()
    if not l:
        continue
    
    current_owner = "Yashika" if l['user_id'] == 4 else ("Kajal" if l['user_id'] == 3 else ("Ayush" if l['user_id'] == 2 else f"User_{l['user_id']}"))
    target_owner = "Kajal" if lid in [2498, 2499, 7749] else "Ayush"
    
    print("=" * 70)
    print(f"LEAD ID: {l['id']} -> Move to {target_owner}")
    print("=" * 70)
    print(f"Name:     {l['first_name']} {l['last_name']}")
    print(f"Email:    {l['email']}")
    print(f"Company:  {l['company_name'] or 'N/A'}")
    print(f"Owner:    {current_owner} (user_id={l['user_id']})")
    print(f"Status:   {l['email_status']}")
    print(f"Intent:   {l['reply_intent'] or 'N/A'}")
    print(f"Replied:  {'Yes' if l['is_responded'] else 'No'}")
    print(f"Template: {l['draft_template_used'] or 'N/A'}")
    print(f"Source:   {l['source'] or 'N/A'}")
    print(f"Created:  {l['created_at']}")
    print(f"Updated:  {l['updated_at']}")
    excerpt = (l['remarks'] or '')[:400].replace('\n', ' | ').replace('\r', '')
    print(f"Reply:\n  {excerpt}")
    print()

cur.close()
conn.close()
