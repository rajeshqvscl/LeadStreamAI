"""
Check which leads under Yashika's account were actually sent by Kajal or Ayush.
Yashika = user_id 4, Kajal = user_id 3, Ayush = user_id 2

Run from backend/ directory:
    python scripts/check_lead_ownership.py
Or from project root:
    python backend/scripts/check_lead_ownership.py
"""
import sys, os
from dotenv import load_dotenv

# Try to load .env from multiple locations
for env_loc in ["app/.env", "backend/app/.env", "../backend/app/.env"]:
    if os.path.exists(env_loc):
        load_dotenv(env_loc)
        break

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
import psycopg2
from psycopg2.extras import RealDictCursor

db_url = os.getenv('DATABASE_URL')
if not db_url:
    print("DATABASE_URL not found. Tried env locations.")
    # Try direct environment variable
    if os.getenv("DATABASE_URL"):
        db_url = os.getenv("DATABASE_URL")
        print("Found via direct env")
    else:
        print("Still not found")
        sys.exit(1)

db_url = db_url.strip().strip("'").strip('"').replace('postgres://', 'postgresql://', 1)
conn = psycopg2.connect(db_url, cursor_factory=RealDictCursor, connect_timeout=10)
cur = conn.cursor()

# Yashika=4, Kajal=3, Ayush=2

print("=== EMAILS SENT BY OTHER USERS TO YASHIKA'S LEADS ===")
cur.execute("""
    SELECT al.user_id, u.username, COUNT(*) as sent_count
    FROM activity_log al
    JOIN leads_raw lr ON al.lead_id = lr.id
    JOIN users u ON al.user_id = u.id
    WHERE lr.user_id = 4 
    AND al.action = 'EMAIL_SENT'
    AND al.user_id != 4
    GROUP BY al.user_id, u.username
    ORDER BY sent_count DESC
""")
for r in cur.fetchall():
    print(f"User {r['user_id']} ({r['username']}): {r['sent_count']} emails sent to Yashika's leads")

print("\n=== YASHIKA'S INBOUND DEALS SENT BY KAJAL/AYUSH ===")
cur.execute("""
    SELECT COUNT(DISTINCT lr.id) as cnt
    FROM leads_raw lr
    JOIN activity_log al ON al.lead_id = lr.id AND al.action = 'EMAIL_SENT'
    WHERE lr.user_id = 4
    AND lr.is_responded = TRUE
    AND al.user_id IN (2, 3)
""")
count = cur.fetchone()['cnt']
print(f"Count: {count}")

print("\n--- Details ---")
# Remove ORDER BY for DISTINCT query
cur.execute("""
    SELECT DISTINCT lr.id, lr.first_name, lr.last_name, lr.email, lr.company_name, 
           lr.reply_intent, lr.email_status, al.user_id as sent_by
    FROM leads_raw lr
    JOIN activity_log al ON al.lead_id = lr.id AND al.action = 'EMAIL_SENT'
    WHERE lr.user_id = 4
    AND lr.is_responded = TRUE
    AND al.user_id IN (2, 3)
    LIMIT 50
""")
for l in cur.fetchall():
    sender = 'Kajal' if l['sent_by'] == 3 else 'Ayush'
    print(f"ID:{l['id']} | By:{sender} | {l['first_name']} {l['last_name']} | {l['email']} | {l['company_name']} | intent:{l['reply_intent']} | status:{l['email_status']}")

print("\n=== INBOUND DEALS WITH KAJAL/AYUSH TEMPLATES ===")
cur.execute("""
    SELECT COUNT(*) as cnt
    FROM leads_raw
    WHERE user_id = 4
    AND is_responded = TRUE
    AND (draft_template_used ILIKE '%kajal%' OR draft_template_used ILIKE '%ayush%' OR draft_template_used ILIKE '%ayush_sir%')
""")
count2 = cur.fetchone()['cnt']
print(f"Count: {count2}")

if count2 > 0:
    cur.execute("""
        SELECT id, first_name, last_name, email, company_name, reply_intent, draft_template_used
        FROM leads_raw
        WHERE user_id = 4
        AND is_responded = TRUE
        AND (draft_template_used ILIKE '%kajal%' OR draft_template_used ILIKE '%ayush%' OR draft_template_used ILIKE '%ayush_sir%')
        LIMIT 20
    """)
    for l in cur.fetchall():
        print(f"ID:{l['id']} | {l['first_name']} {l['last_name']} | template:{l['draft_template_used']} | intent:{l['reply_intent']}")

cur.close()
conn.close()
