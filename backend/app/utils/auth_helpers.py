from typing import Optional
from fastapi import Header
import logging

from app.database import get_db_connection

logger = logging.getLogger(__name__)


def normalize_user_id(user_id: Optional[str]) -> Optional[str]:
    """Normalizes the user ID from the header to a valid numeric database ID string.
    Handles 'admin' or string usernames by resolving them to their numeric database ID.
    Returns None if no valid user_id (callers handle by showing all unscoped data).
    """
    if not user_id or str(user_id).strip() == "":
        return None
    
    u_str = str(user_id).strip()
    if u_str.lower() == "admin":
        return "1"
    
    if u_str.isdigit():
        return u_str
        
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT id FROM users WHERE LOWER(username) = LOWER(%s) OR LOWER(email) = LOWER(%s) LIMIT 1", (u_str, u_str))
        row = cur.fetchone()
        cur.close()
        conn.close()
        if row:
            return str(row[0])
    except Exception as e:
        logger.error(f"Error resolving user_id for '{u_str}': {e}")
        
    return "1"  # Fallback to admin/system if resolution fails


def get_daily_email_limit(user_id: Optional[str]) -> int:
    """Returns the user's configured daily outreach limit (default 2000)."""
    uid = normalize_user_id(user_id)
    is_admin = (str(user_id or '').lower() == 'admin')
    
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        daily_limit = 2000
        if not is_admin and uid:
            cur.execute("SELECT outreach_daily_limit FROM users WHERE id = %s", (uid,))
            limit_row = cur.fetchone()
            stored = limit_row[0] if limit_row else None
            if stored:
                daily_limit = int(stored)
        return daily_limit
    except Exception as e:
        logger.error(f"Error fetching email limit: {e}")
        return 2000
    finally:
        cur.close()
        conn.close()


def check_daily_email_limit(user_id: Optional[str], batch_size: int = 1) -> bool:
    """Returns True if the user has not exceeded their daily outreach limit."""
    uid = normalize_user_id(user_id)
    is_admin = (str(user_id or '').lower() == 'admin')
    
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        daily_limit = 2000
        if not is_admin and uid:
            cur.execute("SELECT outreach_daily_limit FROM users WHERE id = %s", (uid,))
            limit_row = cur.fetchone()
            stored = limit_row[0] if limit_row else None
            if stored:
                daily_limit = int(stored)

        if is_admin:
            cur.execute("SELECT COUNT(*) FROM leads_raw WHERE email_status = 'SENT' AND updated_at >= NOW() - INTERVAL '1 day'")
        elif uid:
            cur.execute("SELECT COUNT(*) FROM leads_raw WHERE user_id = %s AND email_status = 'SENT' AND updated_at >= NOW() - INTERVAL '1 day'", (uid,))
        else:
            cur.execute("SELECT COUNT(*) FROM leads_raw WHERE user_id IS NULL AND email_status = 'SENT' AND updated_at >= NOW() - INTERVAL '1 day'")
        
        sent_today = cur.fetchone()[0] or 0
        return (sent_today + batch_size) <= daily_limit
    except Exception as e:
        logger.error(f"Error checking email limit: {e}")
        return True
    finally:
        cur.close()
        conn.close()