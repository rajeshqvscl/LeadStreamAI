#!/usr/bin/env python3
"""
STOP all scheduled and active followups immediately.
- Sets email_status='STOPPED' for all SCHEDULED leads
- Sets followup_status='STOPPED' for all ACTIVE leads
"""
import os, sys, datetime, logging
os.chdir(os.path.join(os.path.dirname(__file__), '..', 'app'))
sys.path.insert(0, os.getcwd())
from dotenv import load_dotenv
load_dotenv('.env')

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
logger = logging.getLogger(__name__)

from database import get_db_connection

tz = datetime.timezone(datetime.timedelta(hours=5, minutes=30))
now = datetime.datetime.now(tz)

logger.info(f"Running at {now} IST — STOPPING ALL FOLLOWUPS")

conn = get_db_connection()
cur = conn.cursor()

# 1. Stop all SCHEDULED emails (email_status)
cur.execute("""
    UPDATE leads_raw
    SET email_status = 'STOPPED',
        followup_status = 'STOPPED',
        updated_at = NOW()
    WHERE email_status = 'SCHEDULED'
       OR followup_status = 'SCHEDULED'
""")
stopped_scheduled = cur.rowcount
conn.commit()
logger.info(f"Stopped SCHEDULED leads: {stopped_scheduled}")

# 2. Stop all ACTIVE followups
cur.execute("""
    UPDATE leads_raw
    SET followup_status = 'STOPPED',
        updated_at = NOW()
    WHERE followup_status = 'ACTIVE'
""")
stopped_active = cur.rowcount
conn.commit()
logger.info(f"Stopped ACTIVE followups: {stopped_active}")

# 3. Also stop any PENDING_APPROVAL or APPROVED
cur.execute("""
    UPDATE leads_raw
    SET email_status = 'STOPPED',
        followup_status = 'STOPPED',
        updated_at = NOW()
    WHERE email_status IN ('PENDING_APPROVAL', 'APPROVED')
       OR followup_status IN ('PENDING_APPROVAL', 'APPROVED')
""")
stopped_pending = cur.rowcount
conn.commit()
logger.info(f"Stopped PENDING/APPROVED leads: {stopped_pending}")

# Summary
print("\n" + "=" * 60)
print("FOLLOWUP SHUTDOWN COMPLETE")
print("=" * 60)
print(f"  SCHEDULED stopped: {stopped_scheduled}")
print(f"  ACTIVE stopped:    {stopped_active}")
print(f"  PENDING stopped:   {stopped_pending}")
print(f"  TOTAL stopped:     {stopped_scheduled + stopped_active + stopped_pending}")
print("=" * 60)

# Verify no active remain
cur.execute("SELECT COUNT(*) FROM leads_raw WHERE followup_status = 'ACTIVE' AND email_status = 'SCHEDULED'")
remaining = cur.fetchone()[0]
print(f"\n  Remaining ACTIVE+SCHEDULED: {remaining}")

cur.close()
conn.close()
