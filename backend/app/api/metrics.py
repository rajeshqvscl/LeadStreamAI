from fastapi import APIRouter, Header, Query
from typing import Optional
from app.database import get_db_connection
import psycopg2.extras
from datetime import datetime, timezone

router = APIRouter(tags=["Metrics"])

# All dispatched outreach statuses (must match admin_dashboard /stats/global —
# PostgreSQL IN is case-sensitive, so both endpoints share the same literals).
_SENT_STATUS_SQL = "('SENT', 'OPENED', 'CLICKED', 'REPLIED', 'CLOSED', 'Meeting Scheduled', 'Contacted', 'Interested')"

def _period_clause(val):
    v = (val or '').strip().lower()
    if v == 'daily':
        return "AND updated_at AT TIME ZONE 'UTC' AT TIME ZONE 'Asia/Kolkata' >= (NOW() AT TIME ZONE 'Asia/Kolkata')::date AND updated_at AT TIME ZONE 'UTC' AT TIME ZONE 'Asia/Kolkata' < ((NOW() AT TIME ZONE 'Asia/Kolkata')::date + INTERVAL '1 day')"
    elif v == 'weekly':
        return "AND updated_at >= NOW() - INTERVAL '7 days'"
    elif v == 'monthly':
        return "AND updated_at >= NOW() - INTERVAL '30 days'"
    return ""

def _period_clause_activity(val):
    """Period clause on activity_log.created_at (same rules as _period_clause,
    which targets leads_raw.updated_at). Sends are bucketed by the ACTUAL send
    time — leads_raw.updated_at gets overwritten by every follow-up/reply/edit,
    so it silently mis-attributes emails across days in reports."""
    v = (val or '').strip().lower()
    if v == 'daily':
        return "AND created_at AT TIME ZONE 'UTC' AT TIME ZONE 'Asia/Kolkata' >= (NOW() AT TIME ZONE 'Asia/Kolkata')::date AND created_at AT TIME ZONE 'UTC' AT TIME ZONE 'Asia/Kolkata' < ((NOW() AT TIME ZONE 'Asia/Kolkata')::date + INTERVAL '1 day')"
    elif v == 'weekly':
        return "AND created_at >= NOW() - INTERVAL '7 days'"
    elif v == 'monthly':
        return "AND created_at >= NOW() - INTERVAL '30 days'"
    return ""

def _date_clause(date_from, date_to):
    clauses = []
    if date_from:
        clauses.append(f"AND updated_at AT TIME ZONE 'UTC' AT TIME ZONE 'Asia/Kolkata' >= %s::date AT TIME ZONE 'Asia/Kolkata'")
    if date_to:
        clauses.append(f"AND updated_at AT TIME ZONE 'UTC' AT TIME ZONE 'Asia/Kolkata' < (%s::date + INTERVAL '1 day') AT TIME ZONE 'Asia/Kolkata'")
    return " ".join(clauses)

# Activity-log clauses qualified with `al.` — the report list joins activity_log
# to leads_raw (which ALSO has created_at/updated_at columns), so bare column
# names would be ambiguous.
def _period_clause_activity_qualified(val):
    """Same as _period_clause_activity but with `al.` prefix — the report list
    joins leads_raw (which ALSO has created_at), so bare columns are ambiguous.
    Derived from the bare version so the two can never drift apart."""
    return _period_clause_activity(val).replace("created_at", "al.created_at")

def _date_clause_activity_qualified(date_from, date_to):
    clauses = []
    if date_from:
        clauses.append("AND al.created_at AT TIME ZONE 'UTC' AT TIME ZONE 'Asia/Kolkata' >= %s::date AT TIME ZONE 'Asia/Kolkata'")
    if date_to:
        clauses.append("AND al.created_at AT TIME ZONE 'UTC' AT TIME ZONE 'Asia/Kolkata' < (%s::date + INTERVAL '1 day') AT TIME ZONE 'Asia/Kolkata'")
    return " ".join(clauses)

# Replied-lead time clauses use replied_at (the actual reply-received timestamp),
# NOT updated_at (which is polluted by bulk backfills and other lead edits).
# A lead with replied_at = NULL is an unsourced flag — never counted in the
# monthly reply numbers (exposed separately as `unsourced_replied`).

def _period_clause_replied(val):
    v = (val or '').strip().lower()
    if v == 'daily':
        return "AND replied_at AT TIME ZONE 'UTC' AT TIME ZONE 'Asia/Kolkata' >= (NOW() AT TIME ZONE 'Asia/Kolkata')::date AND replied_at AT TIME ZONE 'UTC' AT TIME ZONE 'Asia/Kolkata' < ((NOW() AT TIME ZONE 'Asia/Kolkata')::date + INTERVAL '1 day')"
    elif v == 'weekly':
        return "AND replied_at >= NOW() - INTERVAL '7 days'"
    elif v == 'monthly':
        return "AND replied_at >= NOW() - INTERVAL '30 days'"
    return ""

def _date_clause_replied(date_from, date_to):
    clauses = []
    if date_from:
        clauses.append(f"AND replied_at AT TIME ZONE 'UTC' AT TIME ZONE 'Asia/Kolkata' >= %s::date AT TIME ZONE 'Asia/Kolkata'")
    if date_to:
        clauses.append(f"AND replied_at AT TIME ZONE 'UTC' AT TIME ZONE 'Asia/Kolkata' < (%s::date + INTERVAL '1 day') AT TIME ZONE 'Asia/Kolkata'")
    return " ".join(clauses)

@router.get("/metrics")
def get_metrics(
    user_id: Optional[str] = Header(None, alias="X-User-Id"),
    period: str = Query('all'),
    date_from: str = Query(None),
    date_to: str = Query(None),
    status: str = Query(None),
    for_user: Optional[str] = Query(None, description="Admin-only override: 'all' for global scope, or a user id/username to view. Non-admins are always limited to their own data."),
):
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    # ── Admin-only view override (for_user) ──
    # Admins can view 'all' users or a specific user. Regular users can only
    # ever see their own data — even if they pass for_user, it is ignored.
    _view_label = None
    if for_user is not None and str(for_user).strip():
        _fv = str(for_user).strip()
        _caller_id = int(user_id.strip()) if (user_id or '').strip().isdigit() else None
        _caller_admin = False
        if _caller_id is not None:
            cur.execute("SELECT role FROM users WHERE id = %s", (_caller_id,))
            _c = cur.fetchone()
            _caller_admin = bool(_c and _c.get('role') == 'ADMIN')
        if _fv.lower() == 'all':
            if _caller_admin:
                user_id = None  # global scope
                _view_label = 'All Users'
        elif _caller_admin or (_caller_id is not None and _fv == str(_caller_id)):
            user_id = _fv

    rng = _period_clause(period)
    dte = _date_clause(date_from, date_to)

    params = []
    where_parts = []
    resolved_id = None
    resolved_name = None
    _investor_user_templates = []
    if user_id and user_id != 'all':
        uid_val = user_id.strip()
        if uid_val.isdigit():
            cur.execute("SELECT id, full_name, username FROM users WHERE id = %s LIMIT 1", (int(uid_val),))
        else:
            cur.execute("SELECT id, full_name, username FROM users WHERE LOWER(username) = LOWER(%s) OR LOWER(email) = LOWER(%s) LIMIT 1", (uid_val, uid_val))
        row = cur.fetchone()
        if row:
            resolved_id = row['id']
            resolved_name = row['full_name'] or row['username']
            _un = str(row.get('username') or '').lower()
            _fn = str(row.get('full_name') or '').lower()
            # Template-scoped users (Palak / Yashika / Kajal): derive the template
            # list dynamically from their own leads instead of hardcoded lists.
            # Hardcoded lists went stale (e.g. kajal_mam_Fambo, 'M&A.') and silently
            # dropped those users' PENDING leads from reports.
            _template_scoped = any(kw in (_un + ' ' + _fn) for kw in ('palak', 'yashika', 'kajal'))
            if _template_scoped:
                cur.execute(
                    "SELECT DISTINCT draft_template_used FROM leads_raw "
                    "WHERE user_id = %s AND draft_template_used IS NOT NULL AND draft_template_used != ''",
                    (resolved_id,),
                )
                _investor_user_templates = [r['draft_template_used'] for r in cur.fetchall()]
        if resolved_id is not None:
            where_parts.append("user_id = %s")
            params.append(resolved_id)
            if _template_scoped:
                # Template-scoped users: only their own templates count as "theirs";
                # pending leads with unknown/NULL templates stay excluded. If the
                # derived list is somehow empty, use a sentinel so the IN clause
                # matches nothing (same as the old hardcoded behaviour).
                if not _investor_user_templates:
                    _investor_user_templates = ['__no_templates__']
                tmpl_qs = ','.join(['%s'] * len(_investor_user_templates))
                where_parts.append(f"(draft_template_used IN ({tmpl_qs}) OR email_status NOT IN ('PENDING', 'PENDING_APPROVAL'))")
                params.extend(_investor_user_templates)
        else:
            where_parts.append("1=0")
    where_parts.append("1=1")
    where_base = " AND ".join(where_parts)
    where_clause = f"WHERE {where_base} {rng} {dte}".strip()

    # Build full params list: user_id first, then date_from, date_to
    full_params = tuple(params)
    if date_from:
        full_params = full_params + (date_from,)
    if date_to:
        full_params = full_params + (date_to,)

    # Drafts = leads with PENDING_APPROVAL status (in review queue)
    cur.execute(f"SELECT COUNT(*) as count FROM leads_raw {where_clause} AND email_status = 'PENDING_APPROVAL'", full_params)
    drafts_generated = cur.fetchone()['count'] or 0

    # Reverted = leads that replied (VERIFIED — has a real reply timestamp).
    # Bounced leads are never 'replied' — exclude them. Date filtering is on
    # replied_at (actual reply time), not updated_at (polluted by backfills).
    rng_replied = _period_clause_replied(period)
    dte_replied = _date_clause_replied(date_from, date_to)
    where_replied = f"WHERE {where_base} {rng_replied} {dte_replied}".strip()
    cur.execute(f"SELECT COUNT(*) as count FROM leads_raw {where_replied} AND replied_at IS NOT NULL AND email_status NOT ILIKE 'BOUNCED'", full_params)
    reverted = cur.fetchone()['count'] or 0

    # Unsourced reply flags — is_responded=TRUE but no reply event evidence
    # (replied_at IS NULL). These cannot be dated by reply time, so they are
    # excluded from the monthly reply count and reported separately. They ARE
    # date-filtered on updated_at so the card matches the selected period
    # instead of always showing an all-time number.
    cur.execute(f"SELECT COUNT(*) as count FROM leads_raw {where_clause} AND is_responded = TRUE AND replied_at IS NULL", full_params)
    unsourced_replied = cur.fetchone()['count'] or 0

    # Total leads (with range)
    cur.execute(f"SELECT COUNT(*) as count FROM leads_raw {where_clause}", full_params)
    leads_count = cur.fetchone()['count'] or 0

    # Registry (without range)
    if user_id and user_id != 'all' and resolved_id is not None:
        cur.execute("SELECT COUNT(*) as count FROM company_registry WHERE user_id = %s", (resolved_id,))
    else:
        cur.execute("SELECT COUNT(*) as count FROM company_registry WHERE 1=1")
    registry_count = cur.fetchone()['count'] or 0

    # Today sent (from activity_log, IST timezone)
    ist_today = "(NOW() AT TIME ZONE 'Asia/Kolkata')::date"
    ist_date = "(created_at AT TIME ZONE 'UTC' AT TIME ZONE 'Asia/Kolkata')::date"
    if user_id and user_id != 'all' and resolved_id:
        cur.execute(f"SELECT COUNT(*) as count FROM activity_log WHERE performed_by = %s AND action = 'EMAIL_SENT' AND {ist_date} = {ist_today}", (resolved_name or resolved_id,))
        today_sent = cur.fetchone()['count'] or 0
        cur.execute(f"SELECT COUNT(*) as count FROM activity_log WHERE user_id = %s AND action IN ('AUTO_FOLLOWUP_SENT', 'FOLLOWUP_APPROVED') AND {ist_date} = {ist_today}", (resolved_id,))
        today_followups = cur.fetchone()['count'] or 0
    else:
        cur.execute(f"SELECT COUNT(*) as count FROM activity_log WHERE action = 'EMAIL_SENT' AND {ist_date} = {ist_today}")
        today_sent = cur.fetchone()['count'] or 0
        cur.execute(f"SELECT COUNT(*) as count FROM activity_log WHERE action IN ('AUTO_FOLLOWUP_SENT', 'FOLLOWUP_APPROVED') AND {ist_date} = {ist_today}")
        today_followups = cur.fetchone()['count'] or 0

    daily_limit = 2000

    # Period-based sent/followups — ALWAYS computed from activity_log (the only
    # reliable source for when emails were actually dispatched). leads_raw's
    # updated_at is overwritten by every follow-up/reply/edit, so date-bucketing
    # on it silently drops or mis-attributes sends (e.g. Kajal's 46 on Aug 10
    # showed as 1 in leads_raw but 46 in activity_log).
    al_date_parts = []
    al_date_params = []
    if user_id and user_id != 'all' and resolved_name:
        al_date_parts.append("performed_by = %s")
        al_date_params.append(resolved_name)
    al_date_parts.append("1=1")
    al_date_base = " AND ".join(al_date_parts)
    # Period clause on activity_log.created_at (not leads_raw.updated_at)
    al_period = _period_clause_activity(period)
    al_date_filter = al_period
    if date_from:
        al_date_filter += " AND created_at AT TIME ZONE 'UTC' AT TIME ZONE 'Asia/Kolkata' >= %s::date AT TIME ZONE 'Asia/Kolkata'"
        al_date_params.append(date_from)
    if date_to:
        al_date_filter += " AND created_at AT TIME ZONE 'UTC' AT TIME ZONE 'Asia/Kolkata' < (%s::date + INTERVAL '1 day') AT TIME ZONE 'Asia/Kolkata'"
        al_date_params.append(date_to)
    al_params = tuple(al_date_params)
    cur.execute(f"SELECT COUNT(*) as count FROM activity_log WHERE action = 'EMAIL_SENT' AND {al_date_base} {al_date_filter}", al_params)
    period_email_sent = cur.fetchone()['count'] or 0
    # Follow-ups: use user_id column for per-user filter (same period/date scope)
    fup_date_parts = []
    fup_date_params = []
    if user_id and user_id != 'all' and resolved_id:
        fup_date_parts.append("user_id = %s")
        fup_date_params.append(resolved_id)
    fup_date_parts.append("1=1")
    fup_date_base = " AND ".join(fup_date_parts)
    fup_date_filter = al_period
    if date_from:
        fup_date_filter += " AND created_at AT TIME ZONE 'UTC' AT TIME ZONE 'Asia/Kolkata' >= %s::date AT TIME ZONE 'Asia/Kolkata'"
        fup_date_params.append(date_from)
    if date_to:
        fup_date_filter += " AND created_at AT TIME ZONE 'UTC' AT TIME ZONE 'Asia/Kolkata' < (%s::date + INTERVAL '1 day') AT TIME ZONE 'Asia/Kolkata'"
        fup_date_params.append(date_to)
    fup_params = tuple(fup_date_params)
    cur.execute(f"SELECT COUNT(*) as count FROM activity_log WHERE action IN ('AUTO_FOLLOWUP_SENT', 'FOLLOWUP_APPROVED') AND {fup_date_base} {fup_date_filter}", fup_params)
    period_followups = cur.fetchone()['count'] or 0

    # Total follow-ups (all time)
    if user_id and user_id != 'all' and resolved_id:
        cur.execute("SELECT COUNT(*) as count FROM activity_log WHERE user_id = %s AND action IN ('AUTO_FOLLOWUP_SENT', 'FOLLOWUP_APPROVED')", (resolved_id,))
    else:
        cur.execute("SELECT COUNT(*) as count FROM activity_log WHERE action IN ('AUTO_FOLLOWUP_SENT', 'FOLLOWUP_APPROVED')")
    total_followups = cur.fetchone()['count'] or 0

    # Bounces
    cur.execute(f"SELECT COUNT(*) FROM leads_raw {where_clause} AND email_status = 'BOUNCED'", full_params)
    bounce_count = cur.fetchone()['count'] or 0

    # Unsubscribes — leads in scope whose email is on the global
    # unsubscribe_list. Date-filtered on the ACTUAL unsubscribe event
    # (u.unsubscribed_at, same IST rules as the other period clauses) so the
    # card tracks when people opted out, not when the lead was ingested.
    # Scoped exactly like every other card (user_id / template scope for
    # Palak-Yashika-Kajal, global for admin), so each user's report shows
    # their own unsubscribe count.
    unsub_rng = _period_clause_activity(period).replace("created_at", "u.unsubscribed_at")
    unsub_dte = _date_clause_activity_qualified(date_from, date_to).replace("al.created_at", "u.unsubscribed_at")
    unsub_params = tuple(params)
    if date_from:
        unsub_params = unsub_params + (date_from,)
    if date_to:
        unsub_params = unsub_params + (date_to,)
    cur.execute(
        f"""SELECT COUNT(*) as count FROM unsubscribe_list u
            WHERE u.email IN (SELECT email FROM leads_raw WHERE {where_base})
            {unsub_rng} {unsub_dte}""",
        unsub_params,
    )
    total_unsubs = cur.fetchone()['count'] or 0
    unsub_rate = (total_unsubs / period_email_sent * 100) if period_email_sent > 0 else 0.0

    # Sent (all dispatched outreach statuses — CLOSED is a reply outcome, still sent)
    cur.execute(f"SELECT COUNT(*) as count FROM leads_raw {where_clause} AND email_status IN {_SENT_STATUS_SQL}", full_params)
    sent = cur.fetchone()['count'] or 0

    delivered = max(sent - bounce_count, 0)

    # Unique opens/clicks come from the tracking-pixel activity log — far more
    # accurate than email_status, which only holds the LATEST status and loses
    # earlier OPENED/CLICKED events.
    #
    # COHORT METHOD: count opens/clicks among the SAME cohort of leads the
    # sent/delivered numbers use (the `where_clause` scope). Filtering the open
    # events by their own date would misalign the numerator and denominator
    # (e.g. leads sent in June that opened in July), producing >100% rates.
    cur.execute(
        f"""SELECT COUNT(DISTINCT al.lead_id)
            FROM activity_log al JOIN leads_raw l ON l.id = al.lead_id
            WHERE al.action = 'OPENED' AND l.id IN (SELECT id FROM leads_raw {where_clause} AND email_status IN {_SENT_STATUS_SQL})""",
        full_params,
    )
    unique_opens = cur.fetchone()['count'] or 0
    cur.execute(
        f"""SELECT COUNT(DISTINCT al.lead_id)
            FROM activity_log al JOIN leads_raw l ON l.id = al.lead_id
            WHERE al.action = 'CLICKED' AND l.id IN (SELECT id FROM leads_raw {where_clause} AND email_status IN {_SENT_STATUS_SQL})""",
        full_params,
    )
    unique_clicks = cur.fetchone()['count'] or 0
    unique_engaged = reverted

    open_rate = (unique_opens / delivered * 100) if delivered > 0 else 0.0
    click_rate = (unique_clicks / delivered * 100) if delivered > 0 else 0.0
    bounce_rate = (bounce_count / sent * 100) if sent > 0 else 0.0
    engagement_rate = (unique_engaged / delivered * 100) if delivered > 0 else 0.0
    conversion_rate = (unique_engaged / leads_count * 100) if leads_count > 0 else 0.0

    # ── PERIOD-SCOPED OPEN/CLICK RATES ──
    # These use the SAME activity-log scope as period_email_sent (performed_by +
    # created_at range), so the denominator matches the Emails Sent card exactly
    # and the numbers tell one story (e.g. 197 sent -> 14 opened -> 7.1%).
    # The cohort-based open_rate/click_rate above are kept for API compatibility.
    cur.execute(
        f"""SELECT COUNT(DISTINCT alo.lead_id)
            FROM activity_log alo
            WHERE alo.action = 'OPENED'
              AND alo.lead_id IN (
                  SELECT DISTINCT al.lead_id FROM activity_log al
                  WHERE al.action = 'EMAIL_SENT' AND {al_date_base} {al_date_filter}
              )""",
        al_params,
    )
    period_opens = cur.fetchone()['count'] or 0
    cur.execute(
        f"""SELECT COUNT(DISTINCT alo.lead_id)
            FROM activity_log alo
            WHERE alo.action = 'CLICKED'
              AND alo.lead_id IN (
                  SELECT DISTINCT al.lead_id FROM activity_log al
                  WHERE al.action = 'EMAIL_SENT' AND {al_date_base} {al_date_filter}
              )""",
        al_params,
    )
    period_clicks = cur.fetchone()['count'] or 0
    period_open_rate = (period_opens / period_email_sent * 100) if period_email_sent > 0 else 0.0
    period_click_rate = (period_clicks / period_email_sent * 100) if period_email_sent > 0 else 0.0

    # Persona breakdown
    if user_id and user_id != 'all' and resolved_name:
        uname = (resolved_name or '').lower()
        _is_investor_user = any(kw in uname for kw in ['yashika', 'kajal', 'ayush'])
        _is_client_user = any(kw in uname for kw in ['palak', 'vismaya'])
    else:
        _is_investor_user = False
        _is_client_user = False
    if _is_investor_user:
        persona_breakdown = {'INVESTOR': leads_count}
    elif _is_client_user:
        persona_breakdown = {'CLIENT': leads_count}
    else:
        cur.execute(f"SELECT COALESCE(lead_type, 'OTHER') as persona, COUNT(*) as count FROM leads_raw {where_clause} GROUP BY COALESCE(lead_type, 'OTHER')", full_params)
        persona_rows = cur.fetchall()
        persona_breakdown = { r['persona'].upper(): r['count'] for r in persona_rows }

    # Sector breakdown — split comma-separated sectors into individual counts
    cur.execute(f"""
        SELECT industry, COUNT(*) as count 
        FROM (
            SELECT TRIM(BOTH FROM s) as industry 
            FROM leads_raw, 
                 regexp_split_to_table(COALESCE(sector, 'Other'), ',') as s
            {where_clause}
        ) sub
        WHERE industry != '' AND industry IS NOT NULL
        GROUP BY industry 
        ORDER BY count DESC 
        LIMIT 10
    """, full_params)
    industry_rows = cur.fetchall()
    industry_breakdown = { r['industry']: r['count'] for r in industry_rows }

    # Country breakdown
    cur.execute(f'''
        SELECT COALESCE(country, raw_payload->>'country', 'Unknown') as country, COUNT(*) as count 
        FROM leads_raw 
        {where_clause}
        AND COALESCE(country, raw_payload->>'country') IS NOT NULL
        GROUP BY 1
        ORDER BY count DESC 
        LIMIT 8
    ''', full_params)
    country_rows = cur.fetchall()
    country_breakdown = { r['country']: r['count'] for r in country_rows }

    # Per-lead report data — built from activity_log EMAIL_SENT events so the
    # list EXACTLY matches the period_email_sent count. (leads_raw.updated_at is
    # overwritten by every follow-up/reply/edit, so filtering the list on it
    # silently dropped sends — Kajal's 46 sends on Aug 10 showed only 7 rows.)
    rpt_period = _period_clause_activity_qualified(period)
    rpt_date = _date_clause_activity_qualified(date_from, date_to)
    report_params = []
    report_where = []

    # Optional status filter (e.g. status=BOUNCED) — applied to the joined lead
    if status:
        status_val = status.strip().upper()
        if status_val == 'ACTIVE':
            report_where.append("l.email_status IN ('SENT', 'OPENED', 'CLICKED', 'REPLIED', 'INTERESTED', 'MEETING SCHEDULED', 'CONTACTED')")
        else:
            report_where.append("l.email_status = %s")
            report_params.append(status_val)

    # Detect Palak for 2-followup display
    _palak_user = 'palak' in (resolved_name or '').lower()

    # Same per-user scoping as period_email_sent (performed_by) so the list and
    # the count can never diverge. Admin/global scope → all sends.
    if user_id and user_id != 'all' and resolved_name:
        report_where.append("al.performed_by = %s")
        report_params.append(resolved_name)
    report_where.append("1=1")
    report_base = " AND ".join(report_where)
    report_filter = f"WHERE al.action = 'EMAIL_SENT' AND {report_base} {rpt_period} {rpt_date}".strip()
    report_params_t = tuple(report_params)
    if date_from:
        report_params_t = report_params_t + (date_from,)
    if date_to:
        report_params_t = report_params_t + (date_to,)

    cur.execute(f"""
        SELECT l.first_name, l.last_name, l.email, l.company_name, l.family_office_name,
               COALESCE(l.sector, 'Other') as sector,
               COALESCE(l.lead_type, 'CLIENT') as lead_type,
               l.email_status, l.followup_status, l.followup_stage,
               l.is_responded, l.is_unsubscribed, l.reply_intent, l.check_size,
               l.replied_at, l.first_outreach_subject, l.draft_template_used,
               al.created_at AS sent_at,
               (SELECT ab.details FROM activity_log ab WHERE ab.lead_id = l.id AND ab.action = 'BOUNCED' ORDER BY ab.created_at DESC LIMIT 1) as bounce_reason
        FROM activity_log al
        JOIN leads_raw l ON al.lead_id = l.id
        {report_filter}
        ORDER BY al.created_at DESC
    """, report_params_t)
    report_rows = cur.fetchall()

    report = []
    generic_domains = {"gmail", "yahoo", "hotmail", "outlook", "protonmail", "icloud", "qvscl", "me", "live", "microsoft", "samsung", "sea", "example"}
    for r in report_rows:
        status = (r['email_status'] or '').upper()
        reply_intent = (r['reply_intent'] or '').upper()

        if r.get('is_unsubscribed') or reply_intent == 'NOT_INTERESTED':
            action = 'Unsubscribed'
        elif status == 'BOUNCED':
            action = 'Bounced'
        elif status in ('REPLIED', 'INTERESTED', 'MEETING SCHEDULED') or r.get('is_responded'):
            action = 'Replied'
        elif status == 'CLICKED':
            action = 'Clicked'
        elif status == 'OPENED':
            action = 'Opened'
        elif status in ('SENT', 'CONTACTED'):
            action = 'Sent'
        else:
            action = 'Pending'

        fs = (r['followup_status'] or '').upper()
        stage = r['followup_stage'] or 0
        _ms = 2 if _palak_user else 3
        if fs == 'COMPLETED' or stage >= _ms:
            followup_display = 'Completed'
        elif fs == 'ACTIVE' and stage > 0:
            followup_display = str(stage)
        elif stage > 0:
            followup_display = str(stage)
        elif fs == 'ACTIVE':
            followup_display = 'Active'
        else:
            followup_display = 'Not started'

        updated = r['sent_at']
        if updated:
            updated = updated.isoformat() if hasattr(updated, 'isoformat') else str(updated)

        # Company name: use family_office_name, then email domain, then Individual
        company_name = r['company_name'] or ''
        if not company_name or company_name.lower() == 'independent':
            company_name = r.get('family_office_name') or ''
        if not company_name:
            email = r['email'] or ''
            if '@' in email:
                domain_part = email.split('@')[-1].split('.')[0].lower()
                if domain_part not in generic_domains:
                    company_name = domain_part.capitalize()
        if not company_name:
            company_name = 'Individual'

        # Sector: taken directly from the lead's own data column (no template inference)
        sector = (r.get('sector') or '').strip() or 'Other'

        replied_ts = r['replied_at']
        replied_at_display = None
        if replied_ts:
            replied_at_display = replied_ts.isoformat() if hasattr(replied_ts, 'isoformat') else str(replied_ts)

        report.append({
            "name": f"{r['first_name'] or ''} {r['last_name'] or ''}".strip(),
            "email": r['email'] or '',
            "company": company_name,
            "sector": sector,
            "action": action,
            "followup": followup_display,
            "date": updated,
            "replied_at": replied_at_display,
            "bounce_reason": r.get('bounce_reason') or '',
            "first_outreach_subject": r.get('first_outreach_subject') or '',
            "check_size": r.get('check_size') or '',
        })

    cur.close()
    conn.close()

    return {
        "total_registry": registry_count,
        "today_sent": today_sent,
        "today_followups": today_followups,
        "total_followups": total_followups,
        "period_email_sent": period_email_sent,
        "period_followups": period_followups,
        "daily_limit": daily_limit,
        "drafts_generated": drafts_generated,
        "reverted": reverted,
        "unsourced_replied": unsourced_replied,
        "total_leads": leads_count,
        # sent is ALWAYS the leads_raw status-based count (same cohort as
        # bounces / drafts / total_leads) so all cards use one consistent source
        # and bounce_rate can never exceed 100%. period_email_sent (activity_log)
        # is still returned separately for API compatibility.
        "sent": sent,
        "delivered": delivered,
        "unique_opens": unique_opens,
        "unique_clicks": unique_clicks,
        "unique_engaged": unique_engaged,
        "bounces": bounce_count,
        "total_unsubs": total_unsubs,
        "unsub_rate": round(unsub_rate, 2),

        "open_rate": round(open_rate, 2),
        "click_rate": round(click_rate, 2),
        "period_opens": period_opens,
        "period_clicks": period_clicks,
        "period_open_rate": round(period_open_rate, 2),
        "period_click_rate": round(period_click_rate, 2),
        "bounce_rate": round(bounce_rate, 2),
        "engagement_rate": round(engagement_rate, 2),
        "conversion_rate": round(conversion_rate, 2),

        "persona_breakdown": persona_breakdown,
        "industry_breakdown": industry_breakdown,
        "country_breakdown": country_breakdown,
        "report": report,
        "report_for": _view_label or resolved_name or "All Users",

        "timestamp": datetime.now(timezone.utc).isoformat()
    }
