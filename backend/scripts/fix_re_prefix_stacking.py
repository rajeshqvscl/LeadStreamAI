#!/usr/bin/env python3
"""
Fix Re: prefix stacking in last_outreach_subject.
Converts 'Re: Re: Re: Original Subject' → 'Re: Original Subject'
"""
import os, sys, datetime, logging, re
os.chdir(os.path.join(os.path.dirname(__file__), '..', 'app'))
sys.path.insert(0, os.getcwd())
from dotenv import load_dotenv
load_dotenv('.env')

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
logger = logging.getLogger(__name__)

from database import get_db_connection

tz = datetime.timezone(datetime.timedelta(hours=5, minutes=30))
now = datetime.datetime.now(tz)

logger.info(f"Running at {now} IST — Fixing Re: prefix stacking")

conn = get_db_connection()
cur = conn.cursor()

# Find all leads with stacked Re: prefixes
cur.execute("""
    SELECT id, last_outreach_subject
    FROM leads_raw
    WHERE last_outreach_subject ~* 'Re:.*Re:'
""")
stacked = cur.fetchall()
logger.info(f"Found {len(stacked)} leads with stacked Re: prefixes")

fixed = 0
for lead_id, subject in stacked:
    # Strip all Re:/RE: prefixes, keep only the original
    cleaned = re.sub(r'^(Re:\s*|RE:\s*)+', '', subject, flags=re.IGNORECASE).strip()
    new_subject = f"Re: {cleaned}"

    cur.execute("""
        UPDATE leads_raw
        SET last_outreach_subject = %s, updated_at = NOW()
        WHERE id = %s
    """, (new_subject, lead_id))
    fixed += 1
    logger.info(f"  Fixed lead {lead_id}: '{subject}' → '{new_subject}'")

conn.commit()
cur.close()
conn.close()

print("\n" + "=" * 60)
print("RE: PREFIX CLEANUP COMPLETE")
print("=" * 60)
print(f"  Found:  {len(stacked)} stacked subjects")
print(f"  Fixed:  {fixed}")
print("=" * 60)
