"""
Daily Reply Monitoring & Follow-up Cleanup Service.

Scheduled to run at 10:00 and 16:00 IST (see main.py `reply_cleanup_loop`).

Responsibilities
----------------
1. `cleanup_replied_leads()`
   Finds every lead that HAS replied but still has remaining generated
   follow-ups (followup_draft / pending-approval / scheduled states), deletes
   those follow-ups, and moves the lead into the "replied" state
   (email_status=REPLIED/CLOSED, followup_status=STOPPED, is_responded=TRUE).

2. `run_daily_reply_cleanup_and_report()`
   Orchestrates the cleanup, then sends a morning/evening email report to all
   admins AND creates an in-app reminder notification listing the replies
   detected since the previous run (deduped via the REPLY_DETECTED activity
   log written by gmail.handle_potential_reply).
"""

import html
import logging
from datetime import UTC, datetime, timedelta, timezone

import psycopg2.extras
from app.database import get_db_connection
from app.models.lead import add_activity_log

logger = logging.getLogger(__name__)

IST = timezone(timedelta(hours=5, minutes=30))

# A lead "has replied" if any of these hold.
REPLY_SIGNAL_SQL = """(
    is_responded = TRUE
    OR email_status IN ('REPLIED', 'CLOSED')
    OR reply_intent IS NOT NULL
)"""

# ...and still has "remaining generated follow-ups" that should be deleted.
REMAINING_FOLLOWUP_SQL = """(
    followup_status IN ('ACTIVE', 'SCHEDULED', 'PENDING_APPROVAL', 'APPROVED', 'IDLE')
    OR email_status IN ('PENDING_APPROVAL', 'APPROVED', 'SCHEDULED', 'DRAFT', 'PENDING')
    OR followup_draft IS NOT NULL
    OR followup_approved = TRUE
)"""

# Deliberate safety: if the intent could not be classified the reply workflow
# keeps the sequence 'ACTIVE' for MANUAL REVIEW instead of stopping it. Never
# override that — those leads are excluded from the auto-stop sweep.
KEEP_ACTIVE_FOR_REVIEW_SQL = """NOT (
    followup_status = 'ACTIVE'
    AND (reply_intent IS NULL OR reply_intent = '')
)"""

REPORT_KEY = "reply_report_last_run"


def _replied_email_status(reply_intent) -> str:
    """Map reply intent to the 'replied' email_status the lead should show."""
    return 'CLOSED' if (reply_intent or '').upper() == 'NOT_INTERESTED' else 'REPLIED'


def cleanup_replied_leads(scope_user_id=None, dry_run: bool = False) -> dict:
    """
    Deletes remaining generated follow-ups for every replied lead and moves it
    into the "replied" state.

    - followup_draft    -> NULL        (generated follow-up text deleted)
    - followup_approved -> FALSE       (approval flag reset)
    - scheduled_at      -> NULL        (scheduled follow-up email cancelled)
    - email_status      -> REPLIED/CLOSED unless already terminal
    - followup_status   -> STOPPED for decline/neutral replies, but preserved
                           as MEETING_REQUIRED for INTERESTED/MEETING_REQUESTED
                           (both states stop auto-follow-ups; the warm-lead
                           state is kept so the meeting workflow stays intact)
    - is_responded      -> TRUE

    With `dry_run=True` nothing is written — only the match count is returned.
    """
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    stats = {"replied_found": 0, "followups_deleted": 0, "moved_to_replied": 0, "errors": 0}
    try:
        query = f"""
            SELECT id, user_id, first_name, last_name, email, company_name,
                   email_status, followup_status, reply_intent
            FROM leads_raw
            WHERE {REPLY_SIGNAL_SQL}
              AND {REMAINING_FOLLOWUP_SQL}
              AND {KEEP_ACTIVE_FOR_REVIEW_SQL}
        """
        params = []
        if scope_user_id is not None:
            query += " AND user_id = %s"
            params.append(scope_user_id)
        cur.execute(query, params)
        leads = cur.fetchall()
        stats["replied_found"] = len(leads)

        for lead in leads:
            lead_id = lead["id"]
            target_status = _replied_email_status(lead.get("reply_intent"))
            intent = (lead.get("reply_intent") or "").upper()
            # Warm intents keep the reply workflow's MEETING_REQUIRED state so
            # the meeting workflow stays intact; everything else stops cleanly.
            target_followup_status = (
                "MEETING_REQUIRED" if intent in ("INTERESTED", "MEETING_REQUESTED") else "STOPPED"
            )
            try:
                if not dry_run:
                    cur.execute(
                        """
                        UPDATE leads_raw
                        SET followup_status = %s,
                            is_responded = TRUE,
                            replied_at = COALESCE(replied_at, NOW()),
                            email_status = CASE
                                WHEN email_status IN ('REPLIED', 'CLOSED', 'BOUNCED') THEN email_status
                                ELSE %s
                            END,
                            followup_draft = NULL,
                            followup_approved = FALSE,
                            scheduled_at = NULL,
                            updated_at = NOW()
                        WHERE id = %s
                        """,
                        (target_followup_status, target_status, lead_id),
                    )
                    rowcount = cur.rowcount
                    conn.commit()
                else:
                    rowcount = 1
                if rowcount:
                    stats["followups_deleted"] += 1
                    stats["moved_to_replied"] += 1

                if not dry_run and rowcount:
                    try:
                        add_activity_log(
                            lead_id,
                            "FOLLOWUP_STOPPED",
                            "Reply received — remaining followups deleted, lead moved to replied (auto-cleanup)",
                            "system",
                            lead.get("user_id"),
                        )
                    except Exception as log_err:
                        logger.warning(f"Cleanup activity log failed for lead {lead_id}: {log_err}")
            except Exception as e:
                stats["errors"] += 1
                conn.rollback()
                logger.exception(f"Cleanup failed for lead {lead_id}: {e}")

        logger.info(
            "Reply cleanup %s: %d replied leads matched, %d follow-ups deleted, %d errors",
            "(DRY RUN)" if dry_run else "",
            stats["replied_found"],
            stats["followups_deleted"],
            stats["errors"],
        )
        return stats
    finally:
        cur.close()
        conn.close()


# ---------------------------------------------------------------------------
# Last-report tracking (used to dedupe the email report / notification)
# ---------------------------------------------------------------------------

def _get_last_report_at() -> datetime:
    """Returns the stored last-report timestamp (naive UTC) or a 24h lookback."""
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("SELECT value FROM app_settings WHERE key = %s", (REPORT_KEY,))
        row = cur.fetchone()
        if row and row[0]:
            try:
                return datetime.fromisoformat(row[0])
            except ValueError:
                pass
        return datetime.now(UTC).replace(tzinfo=None) - timedelta(hours=24)
    finally:
        cur.close()
        conn.close()


def _set_last_report_at(dt: datetime) -> None:
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            INSERT INTO app_settings (key, value, updated_at)
            VALUES (%s, %s, NOW())
            ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value, updated_at = NOW()
            """,
            (REPORT_KEY, dt.isoformat()),
        )
        conn.commit()
    finally:
        cur.close()
        conn.close()


def get_replies_since(last_report_at: datetime) -> list:
    """Replies detected (REPLY_DETECTED activity log) since the given time."""
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    try:
        cur.execute(
            """
            SELECT al.lead_id, al.created_at, al.details,
                   l.first_name, l.last_name, l.email, l.company_name,
                   l.reply_intent, l.user_id, u.username
            FROM activity_log al
            JOIN leads_raw l ON l.id = al.lead_id
            LEFT JOIN users u ON l.user_id = u.id
            WHERE al.action = 'REPLY_DETECTED'
              AND al.created_at > %s
            ORDER BY al.created_at DESC
            """,
            (last_report_at,),
        )
        return [dict(r) for r in cur.fetchall()]
    finally:
        cur.close()
        conn.close()


# ---------------------------------------------------------------------------
# Email report + in-app notification
# ---------------------------------------------------------------------------

def _get_admin_users() -> list:
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    try:
        cur.execute(
            "SELECT id, email, full_name, username FROM users WHERE role = 'ADMIN' AND is_active = TRUE ORDER BY id"
        )
        return [dict(r) for r in cur.fetchall()]
    finally:
        cur.close()
        conn.close()


def _format_ist(dt) -> str:
    """Formats a naive-UTC timestamp as a readable IST time string."""
    try:
        if dt is None:
            return "-"
        if getattr(dt, "tzinfo", None) is None:
            dt = dt.replace(tzinfo=UTC)
        return dt.astimezone(IST).strftime("%d %b %I:%M %p")
    except Exception:
        return "-"


def _build_report_html(replies: list, cleanup_stats: dict, run_label: str) -> str:
    reply_count = len(replies)
    deleted = cleanup_stats.get("followups_deleted", 0)

    def esc(value) -> str:
        return html.escape(str(value or "")) if value is not None else "-"

    if replies:
        rows = ""
        for r in replies:
            name = f"{r.get('first_name') or ''} {r.get('last_name') or ''}".strip() or r.get("email") or "?"
            rows += f"""
            <tr style="border-bottom: 1px solid #1e293b;">
                <td style="padding: 10px 12px; font-size: 13px; color: #f8fafc; font-weight: 600;">{esc(name)}</td>
                <td style="padding: 10px 12px; font-size: 13px; color: #cbd5e1;">{esc(r.get('company_name') or '-')}</td>
                <td style="padding: 10px 12px; font-size: 12px; color: #94a3b8;">{esc(r.get('email') or '-')}</td>
                <td style="padding: 10px 12px; font-size: 12px; color: #8b5cf6; font-weight: bold;">{esc(r.get('reply_intent') or 'REPLIED')}</td>
                <td style="padding: 10px 12px; font-size: 12px; color: #94a3b8;">{esc(_format_ist(r.get('created_at')))}</td>
            </tr>"""
        reply_section = f"""
        <h3 style="color: #f8fafc; font-size: 14px; text-transform: uppercase; letter-spacing: 1px; margin-bottom: 15px;">New Replies ({reply_count})</h3>
        <table style="width: 100%; border-collapse: separate; border-spacing: 0; border-radius: 8px; overflow: hidden; border: 1px solid #1e293b;">
            <thead style="background-color: #1e293b;">
                <tr>
                    <th style="padding: 10px 12px; text-align: left; font-size: 10px; text-transform: uppercase; color: #64748b; letter-spacing: 1px;">Lead</th>
                    <th style="padding: 10px 12px; text-align: left; font-size: 10px; text-transform: uppercase; color: #64748b; letter-spacing: 1px;">Company</th>
                    <th style="padding: 10px 12px; text-align: left; font-size: 10px; text-transform: uppercase; color: #64748b; letter-spacing: 1px;">Email</th>
                    <th style="padding: 10px 12px; text-align: left; font-size: 10px; text-transform: uppercase; color: #64748b; letter-spacing: 1px;">Intent</th>
                    <th style="padding: 10px 12px; text-align: left; font-size: 10px; text-transform: uppercase; color: #64748b; letter-spacing: 1px;">Time (IST)</th>
                </tr>
            </thead>
            <tbody style="background-color: #0f172a;">{rows}</tbody>
        </table>"""
    else:
        reply_section = """
        <div style="background-color: #1e293b; padding: 24px; border-radius: 12px; border: 1px solid #334155; text-align: center;">
            <p style="color: #94a3b8; font-size: 14px; margin: 0;">✅ No new replies received since the last check.</p>
        </div>"""

    return f"""
    <div style="font-family: sans-serif; max-width: 650px; margin: auto; padding: 40px; border-radius: 16px; background-color: #0f172a; color: #f8fafc;">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 25px; border-bottom: 1px solid #1e293b; padding-bottom: 20px;">
            <h2 style="color: #f8fafc; margin: 0; font-size: 22px; font-weight: 800;">📬 Reply Monitor</h2>
            <span style="background-color: #3b82f620; color: #60a5fa; padding: 6px 14px; border-radius: 20px; font-size: 11px; font-weight: bold; border: 1px solid #3b82f640;">{run_label}</span>
        </div>

        <div style="display: flex; gap: 16px; margin-bottom: 30px;">
            <div style="flex: 1; background-color: #1e293b; padding: 20px; border-radius: 12px; border: 1px solid #334155; text-align: center;">
                <div style="font-size: 28px; font-weight: 900; color: #8b5cf6;">{reply_count}</div>
                <div style="font-size: 11px; color: #64748b; text-transform: uppercase; letter-spacing: 1px; margin-top: 4px;">New Replies</div>
            </div>
            <div style="flex: 1; background-color: #1e293b; padding: 20px; border-radius: 12px; border: 1px solid #334155; text-align: center;">
                <div style="font-size: 28px; font-weight: 900; color: #10b981;">{deleted}</div>
                <div style="font-size: 11px; color: #64748b; text-transform: uppercase; letter-spacing: 1px; margin-top: 4px;">Follow-ups Stopped & Deleted</div>
            </div>
        </div>

        {reply_section}

        <p style="text-align: center; margin-top: 40px; color: #475569; font-size: 11px; text-transform: uppercase; letter-spacing: 1px;">
            LeadStreamAI — Automatic Reply Monitor
        </p>
    </div>
    """


def _send_report_emails(replies: list, cleanup_stats: dict, run_label: str) -> int:
    """Sends the reply report email to every admin. Returns number sent."""
    from app.services.email_service import send_email

    admins = _get_admin_users()
    sent = 0
    html_content = _build_report_html(replies, cleanup_stats, run_label)
    reply_count = len(replies)
    subject = f"📬 Reply Report — {reply_count} new replies ({run_label})"

    for admin in admins:
        try:
            res = send_email(
                to_email=admin["email"],
                subject=subject,
                html_content=html_content,
                from_email=admin["email"] or "admin@leadstreamai.com",
                from_name="LeadStream Reply Monitor",
                is_system_email=True,
                user_id=1,
            )
            success = res[0] if isinstance(res, tuple) else res
            if success:
                sent += 1
                logger.info(f"Reply report email sent to {admin['email']}")
        except Exception as e:
            logger.exception(f"Reply report email failed for {admin.get('email')}: {e}")
    return sent


def _create_report_reminders(replies: list, cleanup_stats: dict, run_label: str) -> int:
    """Creates an in-app reminder notification for each admin. Returns count."""
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    created = 0
    try:
        reply_count = len(replies)
        deleted = cleanup_stats.get("followups_deleted", 0)
        priority = "HIGH" if reply_count > 0 else "MEDIUM"

        # Auto-complete the previous run's report reminders to avoid clutter
        try:
            cur.execute(
                "UPDATE reminders SET status = 'COMPLETED', completed_at = NOW() "
                "WHERE title LIKE 'Reply Report%' AND status = 'PENDING'"
            )
            conn.commit()
        except Exception:
            conn.rollback()

        title = f"Reply Report — {reply_count} new reply{'s' if reply_count != 1 else ''} ({run_label})"
        lines = [f"Follow-ups stopped & deleted: {deleted}"]
        if replies:
            for r in replies[:8]:
                name = f"{r.get('first_name') or ''} {r.get('last_name') or ''}".strip() or r.get("email") or "?"
                lines.append(
                    f"• {name} — {r.get('company_name') or r.get('email') or '?'} "
                    f"[{r.get('reply_intent') or 'REPLIED'}] @ {_format_ist(r.get('created_at'))}"
                )
            if len(replies) > 8:
                lines.append(f"…and {len(replies) - 8} more")
        else:
            lines.append("No new replies received.")

        description = "\n".join(lines)
        due_at = datetime.now(UTC).replace(tzinfo=None)

        for admin in _get_admin_users():
            try:
                cur.execute(
                    """
                    INSERT INTO reminders (title, description, due_at, priority, status, user_id, user_name)
                    VALUES (%s, %s, %s, %s, 'PENDING', %s, %s)
                    """,
                    (title, description, due_at, priority, admin["id"], admin.get("full_name") or admin.get("username")),
                )
                conn.commit()
                created += 1
            except Exception as e:
                conn.rollback()
                logger.exception(f"Reply report reminder failed for admin {admin.get('id')}: {e}")
        return created
    finally:
        cur.close()
        conn.close()


# ---------------------------------------------------------------------------
# Orchestrator (called from main.py at 10:00 & 16:00 IST, or manually)
# ---------------------------------------------------------------------------

def run_daily_reply_cleanup_and_report(
    dry_run: bool = False,
    send_email: bool = True,
    create_reminder: bool = True,
    run_label: str = None,
) -> dict:
    """
    Runs the full daily reply-monitoring job:
      1. Stop & delete remaining follow-ups for replied leads
      2. Collect replies detected since the previous run
      3. Send the admin email report
      4. Create the in-app reminder notification

    Always reports — even with zero replies the team knows the check ran.
    """
    now_ist = datetime.now(IST)
    run_label = run_label or f"{now_ist.strftime('%A, %d %b %Y')} {now_ist.strftime('%I:%M %p')} IST"

    cleanup_stats = {"replied_found": 0, "followups_deleted": 0, "moved_to_replied": 0, "errors": 0}
    try:
        cleanup_stats = cleanup_replied_leads(dry_run=dry_run)
    except Exception as e:
        logger.exception(f"Reply cleanup failed: {e}")

    replies = []
    try:
        # Gathering is read-only — run it even in dry-run so the preview shows
        # which replies the report WOULD contain.
        last_report_at = _get_last_report_at()
        replies = get_replies_since(last_report_at)
        if not dry_run:
            _set_last_report_at(datetime.now(UTC).replace(tzinfo=None))
    except Exception as e:
        logger.exception(f"Reply report data gathering failed: {e}")

    email_sent = 0
    notifications_created = 0
    if not dry_run:
        if send_email:
            email_sent = _send_report_emails(replies, cleanup_stats, run_label)
        if create_reminder:
            notifications_created = _create_report_reminders(replies, cleanup_stats, run_label)

    logger.info(
        "Reply monitor run '%s': cleanup=%s, replies=%d, emails=%d, reminders=%d",
        run_label,
        cleanup_stats,
        len(replies),
        email_sent,
        notifications_created,
    )
    return {
        "run_label": run_label,
        "cleanup_stats": cleanup_stats,
        "replies": replies,
        "reply_count": len(replies),
        "email_sent": email_sent,
        "notifications_created": notifications_created,
    }
