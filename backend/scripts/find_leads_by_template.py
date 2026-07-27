"""
Find leads under Yashika's account (user_id=4) that used Kajal/Ayush templates.
Then move them to the correct user_id.
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

# Template -> Owner mapping
TEMPLATE_OWNERS = {
    'kajal_mam_health_ecosystem': 3,   # Kajal
    'kajal_mam_qvscl_intro': 3,        # Kajal
    'kajal_mam_jv': 3,                 # Kajal
    'kajal_mam_hyphen': 3,             # Kajal
    'kajal_mam_agritech': 3,           # Kajal
    'ayush_sir_hospital_draft': 2,     # Ayush
    'palak_mam_corporate_advisory': None, # Palak (need to find her user_id)
    'palak_mam_mna_fundraising': None,
    'palak_mam_Draft_1': None,
    'vismaya_leadstream': None,
}

# Find Palak and Vismaya user IDs
cur.execute("SELECT id, username, full_name FROM users WHERE LOWER(username) LIKE '%palak%' OR LOWER(full_name) LIKE '%palak%'")
for r in cur.fetchall():
    print(f"Palak: ID={r['id']}, username={r['username']}, name={r['full_name']}")
    TEMPLATE_OWNERS['palak_mam_corporate_advisory'] = r['id']
    TEMPLATE_OWNERS['palak_mam_mna_fundraising'] = r['id']
    TEMPLATE_OWNERS['palak_mam_Draft_1'] = r['id']

cur.execute("SELECT id, username, full_name FROM users WHERE LOWER(username) LIKE '%vismaya%' OR LOWER(full_name) LIKE '%vismaya%'")
for r in cur.fetchall():
    print(f"Vismaya: ID={r['id']}, username={r['username']}, name={r['full_name']}")
    TEMPLATE_OWNERS['vismaya_leadstream'] = r['id']

print("\n=== LEADS UNDER YASHIKA (user_id=4) BY TEMPLATE ===")
total_movable = 0
for template, owner_id in TEMPLATE_OWNERS.items():
    if owner_id is None:
        continue
    cur.execute("""
        SELECT COUNT(*) as cnt 
        FROM leads_raw 
        WHERE user_id = 4 AND draft_template_used = %s
    """, (template,))
    cnt = cur.fetchone()['cnt']
    if cnt > 0:
        owner_name = {3: 'Kajal', 2: 'Ayush'}.get(owner_id, f'User_{owner_id}')
        print(f"\nTemplate: {template} -> {owner_name} (user_id={owner_id})")
        print(f"  Total leads: {cnt}")
        total_movable += cnt
        
        # Show sample leads (including responded ones)
        cur.execute("""
            SELECT id, first_name, last_name, email, is_responded, reply_intent, email_status
            FROM leads_raw 
            WHERE user_id = 4 AND draft_template_used = %s
            ORDER BY updated_at DESC
            LIMIT 5
        """, (template,))
        for l in cur.fetchall():
            responded = "✅" if l['is_responded'] else "❌"
            print(f"  ID:{l['id']} | {responded} | {l['first_name']} {l['last_name']} | {l['email']} | intent:{l['reply_intent']} | status:{l['email_status']}")

# Also check for all leads without any template filter (all responded leads)
print(f"\n\n=== TOTAL MOVABLE LEADS: {total_movable} ===")

# Also check if there are leads with Kajal/Ayush in the email_status history
print("\n=== LEADS WITH KAJAL/AYUSH IN DRAFT_TEMPLATE_USED (partial match) ===")
cur.execute("""
    SELECT draft_template_used, COUNT(*) as cnt,
           SUM(CASE WHEN is_responded = TRUE THEN 1 ELSE 0 END) as responded
    FROM leads_raw
    WHERE user_id = 4 
    AND draft_template_used IS NOT NULL
    GROUP BY draft_template_used
    ORDER BY cnt DESC
    LIMIT 30
""")
for r in cur.fetchall():
    print(f"  Template: {r['draft_template_used']} | Total: {r['cnt']} | Responded: {r['responded']}")

cur.close()
conn.close()
