#!/usr/bin/env python3
"""Step 1: Rollback affected leads. Step 2: Send followups in batches of 50."""
import os, sys, datetime, logging, time
os.chdir(os.path.join(os.path.dirname(__file__), '..', 'app'))
sys.path.insert(0, os.getcwd())
from dotenv import load_dotenv
load_dotenv('.env')

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
logger = logging.getLogger(__name__)

from database import get_db_connection

# ========== STEP 1: ROLLBACK ==========
print("=" * 60)
print("STEP 1: ROLLBACK AFFECTED LEADS")
print("=" * 60)

conn = get_db_connection()
cur = conn.cursor()

# Rollback leads with prior followups
cur.execute("""
    WITH affected AS (
        SELECT l.id FROM leads_raw l
        WHERE l.followup_status IN ('ACTIVE', 'SCHEDULED', 'COMPLETED')
          AND COALESCE(l.is_responded, FALSE) = FALSE
          AND (l.last_outreach_at AT TIME ZONE 'UTC' AT TIME ZONE 'Asia/Kolkata')::date =
              (NOW() AT TIME ZONE 'Asia/Kolkata')::date
          AND l.id NOT IN (
              SELECT al2.lead_id FROM activity_log al2
              WHERE al2.lead_id = l.id
                AND al2.action IN ('AUTO_FOLLOWUP_SENT', 'FOLLOWUP_APPROVED')
                AND (al2.created_at AT TIME ZONE 'UTC' AT TIME ZONE 'Asia/Kolkata')::date =
                    (NOW() AT TIME ZONE 'Asia/Kolkata')::date
          )
    ),
    last_fu AS (
        SELECT DISTINCT ON (al.lead_id) al.lead_id, al.details, al.created_at
        FROM activity_log al
        INNER JOIN affected a ON a.id = al.lead_id
        WHERE al.action IN ('AUTO_FOLLOWUP_SENT', 'FOLLOWUP_APPROVED')
        ORDER BY al.lead_id, al.created_at DESC
    ),
    parsed AS (
        SELECT lf.lead_id,
            CASE WHEN lf.details ~* 'Stage\\s+(\\d+)' THEN (regexp_match(lf.details, 'Stage\\s+(\\d+)', 'i'))[1]::int ELSE 0 END AS correct_stage,
            lf.created_at AS correct_last_outreach
        FROM last_fu lf
    )
    UPDATE leads_raw l
    SET followup_stage = p.correct_stage,
        followup_status = CASE WHEN p.correct_stage >= 2 THEN 'COMPLETED' ELSE 'ACTIVE' END,
        last_outreach_at = p.correct_last_outreach,
        updated_at = NOW()
    FROM parsed p WHERE l.id = p.lead_id
""")
w1 = cur.rowcount
conn.commit()
print(f"  Leads with prior followups rolled back: {w1}")

# Rollback leads without prior followups
cur.execute("""
    UPDATE leads_raw l
    SET followup_stage = 0,
        followup_status = 'ACTIVE',
        last_outreach_at = l.first_outreach_at,
        updated_at = NOW()
    WHERE l.followup_status IN ('ACTIVE', 'SCHEDULED', 'COMPLETED')
      AND COALESCE(l.is_responded, FALSE) = FALSE
      AND (l.last_outreach_at AT TIME ZONE 'UTC' AT TIME ZONE 'Asia/Kolkata')::date =
          (NOW() AT TIME ZONE 'Asia/Kolkata')::date
      AND l.id NOT IN (
          SELECT al.lead_id FROM activity_log al
          WHERE al.action IN ('AUTO_FOLLOWUP_SENT', 'FOLLOWUP_APPROVED')
      )
""")
w2 = cur.rowcount
conn.commit()
print(f"  Leads without prior followups rolled back: {w2}")
print(f"  TOTAL ROLLBACK: {w1 + w2}")

# Verify
cur.execute("""
    SELECT COUNT(*) as cnt FROM leads_raw l
    WHERE l.followup_status IN ('ACTIVE', 'SCHEDULED', 'COMPLETED')
      AND COALESCE(l.is_responded, FALSE) = FALSE
      AND (l.last_outreach_at AT TIME ZONE 'UTC' AT TIME ZONE 'Asia/Kolkata')::date =
          (NOW() AT TIME ZONE 'Asia/Kolkata')::date
      AND l.id NOT IN (
          SELECT al.lead_id FROM activity_log al
          WHERE al.lead_id = l.id
            AND al.action IN ('AUTO_FOLLOWUP_SENT', 'FOLLOWUP_APPROVED')
            AND (al.created_at AT TIME ZONE 'UTC' AT TIME ZONE 'Asia/Kolkata')::date =
                (NOW() AT TIME ZONE 'Asia/Kolkata')::date
      )
""")
remaining = cur.fetchone()[0]
print(f"  Affected remaining after rollback: {remaining}")

cur.close()
conn.close()
print()
print("ROLLBACK COMPLETE. Server scheduler will pick up all due leads automatically.")
print("No manual sending needed - the scheduler loop handles it.")
