# from app.database import get_db_connection
from app.database import get_db_connection
import json


def insert_lead(first_name, last_name, email, domain, linkedin, company, source, payload, fit_score=0, persona="OTHER", phone=None, user_id=None):

    conn = get_db_connection()
    cur = conn.cursor()

    # Global Blacklist Check: Prevent ingestion of opted-out leads
    if email:
        cur.execute("SELECT 1 FROM unsubscribe_list WHERE email = %s", (email,))
        if cur.fetchone():
            cur.close()
            conn.close()
            return  # Silently skip insertion for blacklisted emails

    # Extract designation from payload if not explicitly provided
    designation = payload.get("current_title", payload.get("designation", payload.get("Designation", ""))) if payload else ""
    if not designation or not str(designation).strip():
        designation = None
    else:
        designation = str(designation).strip()

    # Convert empty linkedin_url to NULL so the unique constraint allows multiple blank entries
    linkedin = linkedin if linkedin and str(linkedin).strip() else None

    cur.execute(
        """
        INSERT INTO leads_raw
        (first_name, last_name, email, domain, linkedin_url, company_name, source, raw_payload, fit_score, persona, phone, user_id, designation)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        ON CONFLICT (email) DO UPDATE SET
            first_name = EXCLUDED.first_name,
            last_name = EXCLUDED.last_name,
            domain = EXCLUDED.domain,
            linkedin_url = EXCLUDED.linkedin_url,
            company_name = EXCLUDED.company_name,
            source = EXCLUDED.source,
            raw_payload = EXCLUDED.raw_payload,
            fit_score = EXCLUDED.fit_score,
            persona = EXCLUDED.persona,
            phone = EXCLUDED.phone,
            user_id = COALESCE(leads_raw.user_id, EXCLUDED.user_id),
            designation = EXCLUDED.designation,
            created_at = CURRENT_TIMESTAMP
        """,
        (
            first_name,
            last_name,
            email,
            domain,
            linkedin,
            company,
            source,
            json.dumps(payload),
            fit_score,
            persona,
            phone,
            user_id,
            designation
        )
    )


    conn.commit()
    cur.close()
    conn.close()


def get_lead_by_id(lead_id):
    conn = get_db_connection()
    # Use DictCursor for easier mapping
    from psycopg2.extras import DictCursor
    cur = conn.cursor(cursor_factory=DictCursor)

    cur.execute(
        """
        SELECT * FROM leads_raw WHERE id = %s
        """,
        (lead_id,)
    )

    row = cur.fetchone()
    cur.close()
    conn.close()

    if not row:
        return None

    return dict(row)

def update_lead(lead_id, data):
    conn = get_db_connection()
    cur = conn.cursor()
    
    # Generate dynamic SET clause
    fields = []
    values = []
    for key, val in data.items():
        # Map frontend names to DB columns if necessary
        db_key = key
        # (Add mapping if needed, e.g., 'designation' -> 'job_title' or similar)
        # For now assume keys match or we handle mapping in the API layer
        fields.append(f"{db_key} = %s")
        values.append(val)
    
    values.append(lead_id)
    query = f"UPDATE leads_raw SET {', '.join(fields)} WHERE id = %s"
    
    cur.execute(query, tuple(values))
    conn.commit()
    cur.close()
    conn.close()
    return True

def add_activity_log(lead_id, action, details=None, performed_by='system', user_id=None):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO activity_log (lead_id, action, details, performed_by, user_id) VALUES (%s, %s, %s, %s, %s)",
        (lead_id, action, details, performed_by, user_id)
    )

    conn.commit()
    cur.close()
    conn.close()

def get_activity_log(lead_id):
    conn = get_db_connection()
    from psycopg2.extras import DictCursor
    cur = conn.cursor(cursor_factory=DictCursor)
    cur.execute(
        "SELECT * FROM activity_log WHERE lead_id = %s ORDER BY created_at DESC",
        (lead_id,)
    )
    rows = cur.fetchall()
    cur.close()
    conn.close()
    res = []
    for r in rows:
        d = dict(r)
        if d.get("created_at"):
            d["created_at"] = d["created_at"].isoformat()
        res.append(d)
    return res

def save_email_draft(lead_id, draft):
    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute(
        """
        UPDATE leads_raw
        SET email_draft = %s,
            email_status = 'PENDING_APPROVAL'
        WHERE id = %s
        """,
        (draft, lead_id)
    )
    conn.commit()
    cur.close()
    conn.close()
    
    # Log activity
    try:
        add_activity_log(lead_id, "DRAFT_GENERATED", "AI email draft generated and saved for review", "system")
    except:
        pass
        pass