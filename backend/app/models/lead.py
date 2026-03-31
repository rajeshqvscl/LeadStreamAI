# from app.database import get_db_connection
from app.database import get_db_connection
import json


def insert_lead(first_name, last_name, email, domain, linkedin, company, source, payload, fit_score=0, persona="OTHER", phone=None):

    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute(
        """
        INSERT INTO leads_raw
        (first_name, last_name, email, domain, linkedin_url, company_name, source, raw_payload, fit_score, persona, phone)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
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
            phone
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

def add_activity_log(lead_id, action, details=None, performed_by='system'):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO activity_log (lead_id, action, details, performed_by) VALUES (%s, %s, %s, %s)",
        (lead_id, action, details, performed_by)
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
    return [dict(r) for r in rows]

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