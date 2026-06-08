from fastapi import APIRouter, Header, HTTPException
from app.database import get_db_connection
import psycopg2.extras
from typing import Optional
from datetime import datetime

router = APIRouter()

@router.get("/reminders")
def list_reminders(status: Optional[str] = None, user_id: Optional[str] = Header(None, alias="X-User-Id")):
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    is_admin = (str(user_id or '').lower() == 'admin')
    try:
        if is_admin:
            if status:
                cur.execute("SELECT * FROM reminders WHERE status = %s ORDER BY due_at ASC", (status,))
            else:
                cur.execute("SELECT * FROM reminders ORDER BY due_at ASC")
        else:
            uid = int(user_id) if user_id and user_id.isdigit() else 0
            if status:
                cur.execute("SELECT * FROM reminders WHERE user_id = %s AND status = %s ORDER BY due_at ASC", (uid, status))
            else:
                cur.execute("SELECT * FROM reminders WHERE user_id = %s ORDER BY due_at ASC", (uid,))
        rows = cur.fetchall()
        return [dict(r) for r in rows]
    finally:
        cur.close()
        conn.close()

@router.post("/reminders")
def create_reminder(data: dict, user_id: Optional[str] = Header(None, alias="X-User-Id")):
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    try:
        uid = int(user_id) if user_id and user_id.isdigit() else None
        user_name = None
        if uid:
            cur.execute("SELECT full_name, username FROM users WHERE id = %s", (uid,))
            u = cur.fetchone()
            if u: user_name = u['full_name'] or u['username']

        title = data.get('title', 'Untitled')
        description = data.get('description', '')
        due_at = data.get('due_at')
        priority = data.get('priority', 'MEDIUM')

        if not due_at:
            raise HTTPException(400, "due_at is required")

        cur.execute("""
            INSERT INTO reminders (title, description, due_at, priority, user_id, user_name)
            VALUES (%s, %s, %s, %s, %s, %s) RETURNING id
        """, (title, description, due_at, priority, uid, user_name))
        rid = cur.fetchone()[0]
        conn.commit()
        return {"id": rid, "message": "Reminder created"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, str(e))
    finally:
        cur.close()
        conn.close()

@router.patch("/reminders/{reminder_id}")
def update_reminder(reminder_id: int, data: dict, user_id: Optional[str] = Header(None, alias="X-User-Id")):
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        fields = []
        values = []
        for key in ['title', 'description', 'due_at', 'priority', 'status']:
            if key in data:
                fields.append(f"{key} = %s")
                values.append(data[key])
        if data.get('status') == 'COMPLETED':
            fields.append("completed_at = NOW()")
        if not fields:
            return {"message": "No fields to update"}
        values.append(reminder_id)
        cur.execute(f"UPDATE reminders SET {', '.join(fields)} WHERE id = %s", values)
        conn.commit()
        return {"message": "Reminder updated"}
    except Exception as e:
        raise HTTPException(500, str(e))
    finally:
        cur.close()
        conn.close()

@router.delete("/reminders/{reminder_id}")
def delete_reminder(reminder_id: int):
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("DELETE FROM reminders WHERE id = %s", (reminder_id,))
        conn.commit()
        return {"message": "Reminder deleted"}
    finally:
        cur.close()
        conn.close()

@router.get("/reminders/due")
def get_due_reminders(user_id: Optional[str] = Header(None, alias="X-User-Id")):
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    is_admin = (str(user_id or '').lower() == 'admin')
    try:
        now = datetime.utcnow().isoformat()
        if is_admin:
            cur.execute("SELECT * FROM reminders WHERE status = 'PENDING' AND due_at <= %s ORDER BY due_at ASC", (now,))
        else:
            uid = int(user_id) if user_id and user_id.isdigit() else 0
            cur.execute("SELECT * FROM reminders WHERE user_id = %s AND status = 'PENDING' AND due_at <= %s ORDER BY due_at ASC", (uid, now))
        rows = cur.fetchall()
        return [dict(r) for r in rows]
    finally:
        cur.close()
        conn.close()

@router.get("/reminders/urgent-actions")
def get_urgent_actions(user_id: Optional[str] = Header(None, alias="X-User-Id")):
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    is_admin = (str(user_id or '').lower() == 'admin')
    try:
        uid_cond = ""
        uid_val = None
        if not is_admin and user_id and user_id.isdigit():
            uid_cond = "AND user_id = %s"
            uid_val = (int(user_id),)

        params = uid_val if uid_val else ()

        # Pending follow-ups — leads with active/idle/scheduled followup, not responded
        cur.execute(f"""
            SELECT id, COALESCE(first_name, '') || ' ' || COALESCE(last_name, '') AS name,
                   company_name, followup_stage, followup_status,
                   last_outreach_at, sector
            FROM leads_raw
            WHERE followup_status IN ('ACTIVE', 'IDLE', 'SCHEDULED')
              AND COALESCE(is_responded, FALSE) = FALSE
              {uid_cond}
            ORDER BY followup_stage DESC, last_outreach_at ASC NULLS FIRST
            LIMIT 20
        """, params)
        pending_followups = [dict(r) for r in cur.fetchall()]

        # Pending drafts — only leads actively awaiting approval
        cur.execute(f"""
            SELECT id, COALESCE(first_name, '') || ' ' || COALESCE(last_name, '') AS name,
                   company_name, email_draft, email_status,
                   created_at, sector
            FROM leads_raw
            WHERE email_status IN ('PENDING_APPROVAL', 'DRAFT', 'PENDING')
              AND COALESCE(is_responded, FALSE) = FALSE
              {uid_cond}
            ORDER BY created_at ASC
            LIMIT 20
        """, params)
        pending_drafts = [dict(r) for r in cur.fetchall()]

        # Also get total unresponded leads count
        cur.execute(f"""
            SELECT COUNT(*) as total
            FROM leads_raw
            WHERE COALESCE(is_responded, FALSE) = FALSE
              {uid_cond}
        """, params)
        total_pending = cur.fetchone()[0]

        return {
            "pending_followups": pending_followups,
            "pending_followups_count": len(pending_followups),
            "pending_drafts": pending_drafts,
            "pending_drafts_count": len(pending_drafts),
            "total_pending_leads": total_pending
        }
    except Exception as e:
        raise HTTPException(500, str(e))
    finally:
        cur.close()
        conn.close()
