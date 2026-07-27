"""
Find leads under Yashika (user_id=4) where the reply content (remarks)
mentions "Kajal" or "Ayush" — indicating the reply was directed at them.
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

# Find Yashika's inbound deals where remarks mention "Kajal" or "Ayush"
print("=== YASHIKA'S INBOUND DEALS MENTIONING 'KAJAL' IN REMARKS ===")
cur.execute("""
    SELECT id, first_name, last_name, email, company_name, 
           reply_intent, email_status, remarks
    FROM leads_raw
    WHERE user_id = 4
    AND is_responded = TRUE
    AND remarks ILIKE '%kajal%'
    ORDER BY updated_at DESC
""")
kajal_leads = cur.fetchall()
print(f"Count: {len(kajal_leads)}")
for l in kajal_leads:
    excerpt = (l['remarks'] or '')[:200].replace('\n', ' | ')
    print(f"ID:{l['id']} | {l['first_name']} {l['last_name']} | {l['email']}")
    print(f"  Remarks: {excerpt}")
    print()

print("\n=== YASHIKA'S INBOUND DEALS MENTIONING 'AYUSH' IN REMARKS ===")
cur.execute("""
    SELECT id, first_name, last_name, email, company_name, 
           reply_intent, email_status, remarks
    FROM leads_raw
    WHERE user_id = 4
    AND is_responded = TRUE
    AND remarks ILIKE '%ayush%'
    ORDER BY updated_at DESC
""")
ayush_leads = cur.fetchall()
print(f"Count: {len(ayush_leads)}")
for l in ayush_leads:
    excerpt = (l['remarks'] or '')[:200].replace('\n', ' | ')
    print(f"ID:{l['id']} | {l['first_name']} {l['last_name']} | {l['email']}")
    print(f"  Remarks: {excerpt}")
    print()

# Also check for "Dear Kajal", "Hi Kajal", etc.
print("\n=== 'Hi Kajal' / 'Dear Kajal' in REMARKS ===")
cur.execute("""
    SELECT COUNT(*) as cnt
    FROM leads_raw
    WHERE user_id = 4
    AND is_responded = TRUE
    AND (remarks ILIKE '%dear kajal%' OR remarks ILIKE '%hi kajal%' OR remarks ILIKE '%hey kajal%' OR remarks ILIKE '%hello kajal%')
""")
print(f"Count: {cur.fetchone()['cnt']}")

print("\n=== 'Hi Ayush' / 'Dear Ayush' in REMARKS ===")
cur.execute("""
    SELECT COUNT(*) as cnt
    FROM leads_raw
    WHERE user_id = 4
    AND is_responded = TRUE
    AND (remarks ILIKE '%dear ayush%' OR remarks ILIKE '%hi ayush%' OR remarks ILIKE '%hey ayush%' OR remarks ILIKE '%hello ayush%')
""")
print(f"Count: {cur.fetchone()['cnt']}")

cur.close()
conn.close()
