# from app.database import get_db_connection
from app.database import get_db_connection


def insert_draft(lead_id, subject, body, temperature, prompt_version):
    conn = get_db_connection()
    cur = conn.cursor()

    # Combine subject + body (since you only have one column)
    email_content = f"Subject: {subject}\n\n{body}"

    cur.execute("""
        UPDATE leads_raw
        SET email_draft = %s
        WHERE id = %s
        RETURNING id
    """, (email_content, lead_id))

    result = cur.fetchone()

    conn.commit()
    cur.close()
    conn.close()

    # Return lead_id as draft_id equivalent
    return result[0] if result else None