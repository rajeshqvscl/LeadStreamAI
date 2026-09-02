import logging

from app.database import get_db

logger = logging.getLogger(__name__)


def normalize_user_id(user_id: str | None) -> str | None:
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
        with get_db() as conn:
            cur = conn.cursor()
            cur.execute("SELECT id FROM users WHERE LOWER(username) = LOWER(%s) OR LOWER(email) = LOWER(%s) LIMIT 1", (u_str, u_str))
            row = cur.fetchone()
            if row:
                return str(row['id'])
    except Exception as e:
        logger.exception(f"Error resolving user_id for '{u_str}': {e}")

    return None  # Do NOT fall back to admin on failure; callers must treat as unauthenticated


def is_admin_user(user_id: str | None) -> bool:
    """Returns True if the (numeric session) user_id belongs to a user with ADMIN role.

    The AuthMiddleware overrides X-User-Id with the verified numeric session id, so
    admin must be resolved from the users.role column, never from a literal 'admin' string
    (which is always False for a numeric header and previously broke admin visibility).
    """
    if not user_id:
        return False
    uid = str(user_id).strip()
    if not uid.isdigit():
        return False
    try:
        with get_db() as conn:
            cur = conn.cursor()
            cur.execute("SELECT role FROM users WHERE id = %s", (int(uid),))
            row = cur.fetchone()
            return bool(row and str(row['role']).strip().upper() == "ADMIN")
    except Exception as e:
        logger.exception(f"Error checking admin role for '{uid}': {e}")
        return False


def get_daily_email_limit(user_id: str | None) -> int:
    """Returns the user's configured daily outreach limit (default 2000)."""
    uid = normalize_user_id(user_id)
    is_admin = is_admin_user(user_id)

    try:
        with get_db() as conn:
            cur = conn.cursor()
            daily_limit = 2000
            if not is_admin and uid:
                cur.execute("SELECT outreach_daily_limit FROM users WHERE id = %s", (uid,))
                limit_row = cur.fetchone()
                stored = limit_row[0] if limit_row else None
                if stored:
                    daily_limit = int(stored)
            return daily_limit
    except Exception as e:
        logger.exception(f"Error fetching email limit: {e}")
        return 2000


def check_daily_email_limit(user_id: str | None, batch_size: int = 1) -> bool:
    """Returns True if the user has not exceeded their daily outreach limit."""
    uid = normalize_user_id(user_id)
    is_admin = is_admin_user(user_id)

    try:
        with get_db() as conn:
            cur = conn.cursor()
            daily_limit = 2000
            if not is_admin and uid:
                cur.execute("SELECT outreach_daily_limit FROM users WHERE id = %s", (uid,))
                limit_row = cur.fetchone()
                stored = limit_row[0] if limit_row else None
                if stored:
                    daily_limit = int(stored)

            if is_admin:
                cur.execute("SELECT COUNT(*) FROM leads_raw WHERE email_status = 'SENT' AND last_outreach_at >= NOW() - INTERVAL '1 day'")
            elif uid:
                cur.execute("SELECT COUNT(*) FROM leads_raw WHERE user_id = %s AND email_status = 'SENT' AND last_outreach_at >= NOW() - INTERVAL '1 day'", (uid,))
            else:
                cur.execute("SELECT COUNT(*) FROM leads_raw WHERE user_id IS NULL AND email_status = 'SENT' AND last_outreach_at >= NOW() - INTERVAL '1 day'")

            sent_today = cur.fetchone()[0] or 0
            return (sent_today + batch_size) <= daily_limit
    except Exception as e:
        logger.exception(f"Error checking email limit: {e}")
        return True
