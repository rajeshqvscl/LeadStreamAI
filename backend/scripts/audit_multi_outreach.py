"""Quantify leads where first_outreach_subject != last_outreach_subject (multi-outreach)."""
import sys
import os
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.path.insert(0, os.getcwd())
from dotenv import load_dotenv
load_dotenv(dotenv_path=Path('app/.env'))
from app.database import get_db_connection
import psycopg2.extras

conn = get_db_connection()
cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

cur.execute("""
    SELECT count(*) AS n FROM leads_raw
    WHERE followup_status = 'ACTIVE'
      AND followup_stage >= 1
      AND first_outreach_subject IS DISTINCT FROM last_outreach_subject
      AND COALESCE(first_outreach_subject,'') != ''
      AND COALESCE(last_outreach_subject,'') != ''
      AND COALESCE(last_outreach_subject,'') NOT ILIKE 're:%'
      AND COALESCE(last_outreach_subject,'') NOT ILIKE 'following up%'
""")
print('ACTIVE stage>=1 leads with first_subject != last_subject (multi-outreach):', cur.fetchone()['n'])

cur.execute("""
    SELECT id, user_id, email, followup_stage, followup_status,
           first_outreach_subject, last_outreach_subject
    FROM leads_raw
    WHERE followup_status = 'ACTIVE' AND followup_stage >= 1
      AND first_outreach_subject IS DISTINCT FROM last_outreach_subject
      AND COALESCE(first_outreach_subject,'') != ''
      AND COALESCE(last_outreach_subject,'') != ''
      AND COALESCE(last_outreach_subject,'') NOT ILIKE 're:%'
      AND COALESCE(last_outreach_subject,'') NOT ILIKE 'following up%'
    ORDER BY user_id, id LIMIT 30
""")
for r in cur.fetchall():
    print(f'  lead={r["id"]} user={r["user_id"]} stage={r["followup_stage"]} | first={str(r["first_outreach_subject"])[:42]} | last={str(r["last_outreach_subject"])[:42]}')

cur.execute("SELECT count(*) AS n FROM leads_raw WHERE followup_status='ACTIVE' AND followup_stage>=1 AND last_outreach_subject ILIKE 'following up%'")
print('\nleads w/ last_outreach_subject "Following up":', cur.fetchone()['n'])

# Total ACTIVE stage>=1 leads for context
cur.execute("SELECT count(*) AS n FROM leads_raw WHERE followup_status='ACTIVE' AND followup_stage>=1")
print('Total ACTIVE stage>=1 leads:', cur.fetchone()['n'])
conn.close()
