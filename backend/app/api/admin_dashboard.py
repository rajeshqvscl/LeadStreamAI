
import contextlib
import datetime
import json
import os
from typing import Any

import psycopg2.extras
import structlog
from app.database import get_db_connection
from app.utils.auth_helpers import normalize_user_id
from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel


class DateTimeEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, (datetime.datetime, datetime.date, datetime.time)):
            return obj.isoformat()
        return super().default(obj)

router = APIRouter()
logger = structlog.get_logger(__name__)

# --- REDIS CACHE INITIALIZATION ---
redis_client = None
redis_available = False

try:
    import redis
    from app.core.redis_pool import get_redis_pool
    REDIS_URL = os.getenv("REDIS_URL") or os.getenv("REDIS_TLS_URL") or "redis://localhost:6379"
    redis_client = redis.Redis(connection_pool=get_redis_pool())
    redis_client.ping()
    redis_available = True
    logger.info(f"SUCCESS: Connected to Redis Cache at {REDIS_URL.split('@')[-1]}")
except Exception as re_err:
    logger.warning(f"NOTICE: Redis is not active. Falling back to direct database execution. Error: {re_err}")
    redis_client = None
    redis_available = False

TYPE_CASE_SQL = """
CASE
    WHEN u.username ILIKE '%%yashika%%' OR u.username ILIKE '%%kajal%%' OR u.username ILIKE '%%ayush%%' THEN 'INVESTOR'
    WHEN u.username ILIKE '%%palak%%' OR u.username ILIKE '%%vismaya%%' THEN 'CLIENT'
    ELSE UPPER(COALESCE(l.lead_type, 'CLIENT'))
END
"""

# Sector is taken directly from the lead's own data (leads_raw.sector column),
# with industry as a fallback. No draft-template or email-content inference.
SECTOR_CASE_SQL = """
COALESCE(
    NULLIF(TRIM(UPPER(l.sector)), ''),
    NULLIF(TRIM(UPPER(l.industry)), ''),
    'OTHER'
)
"""

class BulkApproveRequest(BaseModel):
    lead_ids: list[int]


def _safe_payload(payload):
    """Parses a lead's raw_payload (JSONB) into a dict, tolerating strings."""
    if isinstance(payload, dict):
        return payload
    if isinstance(payload, str):
        try:
            return json.loads(payload)
        except Exception:
            return {}
    return {}


# Keys used to discover phone / location inside company-database payloads
# (raw_payload stores the original company registry row, e.g. 'Phone', 'Mobile',
#  'Contact Number', 'Location', 'City', 'Country', 'State', ...).
_PHONE_HINTS = ["phone", "mobile", "contact number", "contact no", "telephone", "cell", "whatsapp"]
_LOCATION_HINTS = ["location", "city", "country", "state", "address", "headquarters", "region", "place"]

# Words that disqualify a payload key from being treated as a location — these
# columns hold emails/URLs, not physical places (e.g. 'Email Address',
# 'Website Address', 'Mailing Address' should never appear in Location).
_NON_LOCATION_KEY_WORDS = ["email", "e-mail", "website", "web", "url", "link", "profile", "domain", "www", "http"]

# Keys that carry the INVESTING sector for investor-type leads (from the
# company-database payload / family-office sheet row, e.g. 'Investment Sectors',
# 'Sector Focus', 'Target Sectors', 'Preferred Sectors', 'Category', ...).
# Ordered from most specific to most generic.
_INVESTOR_SECTOR_HINTS = [
    "investment sectors", "investing sector", "sector focus", "focus sector",
    "target sector", "target sectors", "preferred sector", "preferred sectors",
    "focus sectors", "investment focus", "portfolio focus", "investment thesis",
    "mandate", "strategic fit", "sectors", "category",
]

# Generic sector placeholders that should never be treated as a real investing sector.
_GENERIC_SECTOR_SET = {s.lower() for s in ["investor", "client", "other", "investor - general", ""]}

# Known raw_payload keys (JSONB) that hold an investing sector for investor leads.
# Used to include payload-derived investor sectors in the sector dropdown + filter.
_PAYLOAD_SECTOR_KEYS_SQL = """
    COALESCE(raw_payload->>'Investment Sectors', '') || ',' ||
    COALESCE(raw_payload->>'Investing Sector', '') || ',' ||
    COALESCE(raw_payload->>'Sector Focus', '') || ',' ||
    COALESCE(raw_payload->>'Target Sectors', '') || ',' ||
    COALESCE(raw_payload->>'Preferred Sectors', '') || ',' ||
    COALESCE(raw_payload->>'Focus Sectors', '') || ',' ||
    COALESCE(raw_payload->>'Investment Focus', '') || ',' ||
    COALESCE(raw_payload->>'Portfolio Focus', '') || ',' ||
    COALESCE(raw_payload->>'Category', '')
""".strip()



def _hint_match(key: str, hint: str) -> bool:
    """True when a normalized payload key matches a hint.
    Matches the hint as a standalone word or as a trailing fragment,
    so 'Phone'/'Work Phone' match but 'Company Number' does not."""
    if not key:
        return False
    words = key.split()
    return any(w == hint for w in words) or key.endswith(hint)


def extract_investor_sector(row: dict) -> str:
    """Returns the INVESTING sector for an investor-type lead if present in the
    data. For investors the payload's investing sector takes priority (that is
    the sector they invest in — exactly what the user asked to surface); the
    lead's own sector column is used as fallback when the payload has nothing.
    Returns '' when not found or when the lead is not an investor."""
    lead_type = str(row.get("lead_type") or "").upper()
    if lead_type != "INVESTOR":
        return ""

    own_sector = str(row.get("sector") or "").strip()

    # 1. Company-database payload first — the investing-sector keys.
    payload = _safe_payload(row.get("raw_payload"))
    if payload:
        norm = {}
        for k, v in payload.items():
            norm[str(k).strip().lower().replace("_", " ").replace("-", " ")] = v
        for hint in _INVESTOR_SECTOR_HINTS:
            for k, v in norm.items():
                if _hint_match(k, hint) and v and str(v).strip():
                    val = str(v).strip()
                    if val.lower() in ("", "n/a", "na", "none", "-", "—", "null"):
                        continue
                    return val

    # 2. Fallback — lead's own sector column (skip generic classifier placeholders).
    if own_sector and own_sector.lower() not in _GENERIC_SECTOR_SET:
        return own_sector

    return ""


def extract_phone_location(row: dict):
    """Returns (phone, location) for an admin lead row.

    Source order — fetched strictly from THIS lead data:
      1. Lead pipeline's own columns (leads_raw.phone / city / country)
      2. Company-database payload fallback (leads_raw.raw_payload, which holds the
         original company registry row when the lead came from the company DB)
    """
    phone = str(row.get("phone") or "").strip()
    city = str(row.get("city") or "").strip()
    country = str(row.get("country") or "").strip()
    location = ", ".join(x for x in [city, country] if x).strip()

    payload = _safe_payload(row.get("raw_payload"))
    if payload:
        norm = {}
        for k, v in payload.items():
            norm[str(k).strip().lower().replace("_", " ").replace("-", " ")] = v

        if not phone:
            for hint in _PHONE_HINTS:
                for k, v in norm.items():
                    if _hint_match(k, hint) and v and str(v).strip():
                        phone = str(v).strip()
                        break
                if phone:
                    break

        if not location:
            loc_parts, seen = [], set()
            for hint in _LOCATION_HINTS:
                for k, v in norm.items():
                    # Skip keys that are email/website columns (e.g. 'Email Address')
                    # and skip values that look like emails.
                    if not _hint_match(k, hint) or not v:
                        continue
                    if any(w in k for w in _NON_LOCATION_KEY_WORDS):
                        continue
                    lv = str(v).strip()
                    if not lv or "@" in lv or lv.lower().startswith(("http://", "https://", "www.")):
                        continue
                    if lv.lower() not in seen:
                        loc_parts.append(lv)
                        seen.add(lv.lower())
            location = ", ".join(loc_parts)

    return phone, location

@router.post("/leads/bulk-approve")
def bulk_approve_leads(req: BulkApproveRequest, user_id: str | None = Header(None, alias="X-User-Id")):
    """
    Approves multiple leads at once by setting status to 'Contacted'.
    """
    try:
        conn = get_db_connection()
        cur = conn.cursor()

        cur.execute("""
            UPDATE leads_raw
            SET email_status = 'Contacted', updated_at = NOW()
            WHERE id = ANY(%s)
        """, (req.lead_ids,))

        conn.commit()
        return {"success": True, "count": len(req.lead_ids)}
    except Exception as e:
        logger.exception("bulk_approve_error", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if 'conn' in locals():
            conn.close()

@router.get("/leads/all")
def get_all_leads_admin(
    user_id: str | None = Header(None, alias="X-User-Id"),
    page: int = 1,
    limit: int = 50,
    type: str | None = None,
    status: str | None = None,
    intent: str | None = None,
    owner: str | None = None,
    sector: str | None = None,
    search: str | None = None,
    period: str | None = None
):
    """
    Returns paginated leads for the admin dashboard with global filtering.
    """
    cache_key = f"admin_leads:{user_id}:{page}:{limit}:{type}:{status}:{intent}:{owner}:{sector}:{search}:{period}"
    if redis_available and redis_client:
        try:
            cached = redis_client.get(cache_key)
            if cached:
                return json.loads(cached)
        except Exception:
            pass

    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

        # 1. Verify Admin Role
        cur.execute("SELECT username FROM users WHERE id = %s", (normalize_user_id(user_id),))
        user = cur.fetchone()
        if not user or user['username'].lower() != 'admin' and normalize_user_id(user_id) != 1:
             if user_id != 'admin':
                raise HTTPException(status_code=403, detail="Admin access required")

        offset = (page - 1) * limit

        # 2. Build Dynamic WHERE Clause — admin sees ALL leads (including freshly imported)
        where_clauses = ["1=1"]
        params = []

        if type and type != 'ALL':
            where_clauses.append(f"({TYPE_CASE_SQL}) = %s")
            params.append(type.upper())
        # REPLIED status filters by replied_at (the actual reply timestamp); all
        # other statuses keep filtering on updated_at. replied_at IS NULL means
        # the lead was flagged replied without event evidence (unsourced) — such
        # leads only appear when no period filter is applied.
        _replied_view = bool(status and status.upper() == 'REPLIED')
        _date_col = 'l.replied_at' if _replied_view else 'l.updated_at'
        if status and status != 'ALL':
            if status.upper() == 'REPLIED':
                # STRICT: Must have is_responded flag (on a non-bounced lead) OR status is explicitly REPLIED.
                # BOUNCED leads are never 'replied' — the bounce handler must not mark them responded.
                where_clauses.append("(l.email_status ILIKE 'REPLIED' OR (l.is_responded = TRUE AND l.email_status NOT ILIKE 'BOUNCED'))")
            elif status == 'Interested':
                where_clauses.append("l.reply_intent = 'INTERESTED'")
            else:
                where_clauses.append("l.email_status ILIKE %s")
                params.append(status)
        if intent and intent != 'ALL':
            where_clauses.append("l.reply_intent ILIKE %s")
            params.append(intent)
        if owner and owner != 'ALL':
            where_clauses.append("u.username ILIKE %s")
            params.append(owner)
        if sector and sector != 'ALL':
            # Sector filter also matches investing-sector keys inside the investor payload
            where_clauses.append(f"""(
                ({SECTOR_CASE_SQL}) = %s
                OR COALESCE(l.sector, '') ILIKE '%%' || %s || '%%'
                OR (({TYPE_CASE_SQL}) = 'INVESTOR' AND (
                        l.raw_payload->>'Investment Sectors' ILIKE '%%' || %s || '%%'
                     OR l.raw_payload->>'Investing Sector' ILIKE '%%' || %s || '%%'
                     OR l.raw_payload->>'Sector Focus' ILIKE '%%' || %s || '%%'
                     OR l.raw_payload->>'Target Sectors' ILIKE '%%' || %s || '%%'
                     OR l.raw_payload->>'Preferred Sectors' ILIKE '%%' || %s || '%%'
                     OR l.raw_payload->>'Focus Sectors' ILIKE '%%' || %s || '%%'
                     OR l.raw_payload->>'Investment Focus' ILIKE '%%' || %s || '%%'
                     OR l.raw_payload->>'Portfolio Focus' ILIKE '%%' || %s || '%%'
                     OR l.raw_payload->>'Category' ILIKE '%%' || %s || '%%'
                ))
            )""")
            params.extend([sector.upper(), sector])
            params.extend([sector] * 9)
        if search:
            where_clauses.append("(l.first_name ILIKE %s OR l.last_name ILIKE %s OR l.company_name ILIKE %s OR l.email ILIKE %s)")
            s_param = f"%{search}%"
            params.extend([s_param, s_param, s_param, s_param])
        if period and period != 'ALL':
            if period == 'DAILY':
                where_clauses.append(f"{_date_col} AT TIME ZONE 'Asia/Kolkata' >= (NOW() AT TIME ZONE 'Asia/Kolkata')::date")
            elif period == 'WEEKLY':
                where_clauses.append(f"{_date_col} AT TIME ZONE 'Asia/Kolkata' >= (NOW() AT TIME ZONE 'Asia/Kolkata')::date - INTERVAL '6 days'")
            elif period == 'MONTHLY':
                where_clauses.append(f"{_date_col} AT TIME ZONE 'Asia/Kolkata' >= (NOW() AT TIME ZONE 'Asia/Kolkata')::date - INTERVAL '29 days'")
            elif period == 'QUARTERLY':
                where_clauses.append(f"{_date_col} AT TIME ZONE 'Asia/Kolkata' >= (NOW() AT TIME ZONE 'Asia/Kolkata')::date - INTERVAL '89 days'")

        where_sql = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""

        # 3. Fetch leads
        query = f"""
            SELECT l.id, l.first_name, l.last_name, l.email, l.phone, l.city, l.country, l.raw_payload, l.company_name, l.family_office_name, l.designation,
                   ({SECTOR_CASE_SQL}) as sector, ({TYPE_CASE_SQL}) as lead_type, l.reply_intent, l.sentiment_score, l.deal_size, l.check_size, l.source,
                   l.user_id, l.created_at, l.updated_at, l.replied_at, l.rag_advice, l.rag_intelligence,
                   l.followup_stage, l.followup_status, l.last_outreach_at, l.email_status,
                   l.persona, l.email_draft, l.first_outreach_subject, l.last_outreach_subject, l.remarks, l.rejection_reason,
                   u.username as owner_name,
                   (
                       SELECT al.details FROM activity_log al
                       WHERE al.lead_id = l.id AND al.action = 'BOUNCED'
                       ORDER BY al.created_at DESC LIMIT 1
                   ) as bounce_reason
            FROM leads_raw l
            LEFT JOIN users u ON l.user_id = u.id
            {where_sql}
            ORDER BY l.updated_at DESC
            LIMIT %s OFFSET %s
        """
        cur.execute(query, tuple(params + [limit, offset]))
        leads = cur.fetchall()

        # Get total count for pagination UI
        count_query = f"SELECT COUNT(*) FROM leads_raw l LEFT JOIN users u ON l.user_id = u.id {where_sql}"
        cur.execute(count_query, tuple(params))
        total_count = cur.fetchone()[0]

        # 5. Dynamic Filters — sectors including both derived + individual raw values
        #    + investing-sector keys from investor payloads (company DB / family office)
        cur.execute(f"""
            SELECT DISTINCT sector_name FROM (
                SELECT ({SECTOR_CASE_SQL}) as sector_name FROM leads_raw l
                UNION
                SELECT UPPER(TRIM(BOTH FROM s)) as sector_name
                FROM leads_raw, regexp_split_to_table(COALESCE(sector, 'Other'), ',') as s
                WHERE TRIM(BOTH FROM s) != '' AND UPPER(TRIM(BOTH FROM s)) != 'OTHER'
                UNION
                SELECT UPPER(TRIM(BOTH FROM sec)) as sector_name
                FROM leads_raw,
                regexp_split_to_table(
                    {_PAYLOAD_SECTOR_KEYS_SQL},
                    ','
                ) as sec
                WHERE TRIM(BOTH FROM sec) != '' AND UPPER(TRIM(BOTH FROM sec)) != 'OTHER'
            ) combined ORDER BY 1 ASC
        """)
        all_sectors = [r[0] for r in cur.fetchall() if r[0]]

        cur.execute("SELECT DISTINCT username FROM users ORDER BY username ASC")
        all_owners = [r[0] for r in cur.fetchall()]

        # Transform leads: fill company_name from email domain if missing
        generic_domains = {"gmail", "yahoo", "hotmail", "outlook", "protonmail", "icloud", "qvscl", "me", "live", "microsoft", "samsung", "sea", "example"}
        lead_list = []
        for l in leads:
            row = dict(l)
            if not row.get("company_name") or row["company_name"] == "Independent":
                if row.get("family_office_name"):
                    row["company_name"] = row["family_office_name"]
                else:
                    email = row.get("email", "") or ""
                    if "@" in email:
                        domain_part = email.split("@")[-1].split(".")[0].lower()
                        if domain_part not in generic_domains:
                            row["company_name"] = domain_part.capitalize()
            # Phone + Location — from the lead's own data / company-db payload
            phone, location = extract_phone_location(row)
            row["phone"] = phone
            row["location"] = location
            # For investor leads, surface the investing sector when present in the data
            investor_sector = extract_investor_sector(row)
            if investor_sector:
                row["sector"] = investor_sector
            # raw_payload is only needed server-side for extraction — keep responses lean
            row.pop("raw_payload", None)
            lead_list.append(row)

        result = {
            "leads": lead_list,
            "sectors": all_sectors,
            "owners": all_owners,
            "pagination": {
                "total": total_count,
                "page": page,
                "limit": limit,
                "pages": (total_count + limit - 1) // limit
            }
        }
        if redis_available and redis_client:
            with contextlib.suppress(Exception):
                redis_client.setex(cache_key, 5, json.dumps(result, cls=DateTimeEncoder))
        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("admin_all_leads_error", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if 'conn' in locals():
            conn.close()

@router.get("/leads/export")
def export_all_leads_admin(
    period: str | None = "ALL",
    type: str | None = None,
    status: str | None = None,
    intent: str | None = None,
    owner: str | None = None,
    sector: str | None = None,
    search: str | None = None,
    user_id: str | None = Header(None, alias="X-User-Id")
):
    """
    Returns filtered leads in the system without pagination for full master export.
    Supports period: DAILY, WEEKLY, MONTHLY, QUARTERLY, YEARLY, ALL
    Also filters by type, status, intent, owner, sector, search when provided.
    """
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

        # 1. Verify Admin Role
        cur.execute("SELECT username FROM users WHERE id = %s", (normalize_user_id(user_id),))
        user = cur.fetchone()
        if not user or user['username'].lower() != 'admin' and normalize_user_id(user_id) != 1:
             if user_id != 'admin':
                raise HTTPException(status_code=403, detail="Admin access required")

        # 2. Build Dynamic WHERE Clause
        where_clauses = ["1=1"]
        params = []

        if type and type != 'ALL':
            where_clauses.append(f"({TYPE_CASE_SQL}) = %s")
            params.append(type.upper())
        # REPLIED status filters by replied_at (the actual reply timestamp); all
        # other statuses keep filtering on updated_at.
        _replied_view = bool(status and status.upper() == 'REPLIED')
        _date_col = 'l.replied_at' if _replied_view else 'l.updated_at'
        if status and status != 'ALL':
            if status.upper() == 'REPLIED':
                # BOUNCED leads are never 'replied' — exclude them from the replied filter.
                where_clauses.append("(l.email_status ILIKE 'REPLIED' OR (l.is_responded = TRUE AND l.email_status NOT ILIKE 'BOUNCED'))")
            elif status == 'Interested':
                where_clauses.append("l.reply_intent = 'INTERESTED'")
            else:
                where_clauses.append("l.email_status ILIKE %s")
                params.append(status)
        if intent and intent != 'ALL':
            where_clauses.append("l.reply_intent ILIKE %s")
            params.append(intent)
        if owner and owner != 'ALL':
            where_clauses.append("u.username ILIKE %s")
            params.append(owner)
        if sector and sector != 'ALL':
            # Sector filter also matches investing-sector keys inside the investor payload
            where_clauses.append(f"""(
                ({SECTOR_CASE_SQL}) = %s
                OR COALESCE(l.sector, '') ILIKE '%%' || %s || '%%'
                OR (({TYPE_CASE_SQL}) = 'INVESTOR' AND (
                        l.raw_payload->>'Investment Sectors' ILIKE '%%' || %s || '%%'
                     OR l.raw_payload->>'Investing Sector' ILIKE '%%' || %s || '%%'
                     OR l.raw_payload->>'Sector Focus' ILIKE '%%' || %s || '%%'
                     OR l.raw_payload->>'Target Sectors' ILIKE '%%' || %s || '%%'
                     OR l.raw_payload->>'Preferred Sectors' ILIKE '%%' || %s || '%%'
                     OR l.raw_payload->>'Focus Sectors' ILIKE '%%' || %s || '%%'
                     OR l.raw_payload->>'Investment Focus' ILIKE '%%' || %s || '%%'
                     OR l.raw_payload->>'Portfolio Focus' ILIKE '%%' || %s || '%%'
                     OR l.raw_payload->>'Category' ILIKE '%%' || %s || '%%'
                ))
            )""")
            params.extend([sector.upper(), sector])
            params.extend([sector] * 9)
        if search:
            where_clauses.append("(l.first_name ILIKE %s OR l.last_name ILIKE %s OR l.company_name ILIKE %s OR l.email ILIKE %s)")
            s_param = f"%{search}%"
            params.extend([s_param, s_param, s_param, s_param])
        if period and period != 'ALL':
            if period == 'DAILY':
                where_clauses.append(f"{_date_col} AT TIME ZONE 'Asia/Kolkata' >= (NOW() AT TIME ZONE 'Asia/Kolkata')::date")
            elif period == 'WEEKLY':
                where_clauses.append(f"{_date_col} AT TIME ZONE 'Asia/Kolkata' >= (NOW() AT TIME ZONE 'Asia/Kolkata')::date - INTERVAL '6 days'")
            elif period == 'MONTHLY':
                where_clauses.append(f"{_date_col} AT TIME ZONE 'Asia/Kolkata' >= (NOW() AT TIME ZONE 'Asia/Kolkata')::date - INTERVAL '29 days'")
            elif period == 'QUARTERLY':
                where_clauses.append(f"{_date_col} AT TIME ZONE 'Asia/Kolkata' >= (NOW() AT TIME ZONE 'Asia/Kolkata')::date - INTERVAL '89 days'")
            elif period == 'YEARLY':
                where_clauses.append(f"{_date_col} AT TIME ZONE 'Asia/Kolkata' >= (NOW() AT TIME ZONE 'Asia/Kolkata')::date - INTERVAL '364 days'")

        where_sql = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""

        # 3. Fetch leads with derived + raw sector
        query = f"""
            SELECT l.id, l.first_name, l.last_name, l.email, l.phone, l.city, l.country, l.raw_payload, l.company_name, l.family_office_name, l.designation,
                   ({SECTOR_CASE_SQL}) as sector, l.sector as raw_sector, ({TYPE_CASE_SQL}) as lead_type, l.reply_intent, l.sentiment_score, l.deal_size, l.check_size,
                   l.user_id, l.created_at, l.updated_at, l.replied_at, l.rag_advice, l.rag_intelligence,
                   l.email_status, l.followup_status,
                   l.persona, l.email_draft, l.first_outreach_subject, l.last_outreach_subject,
                   u.username as owner_name
            FROM leads_raw l
            LEFT JOIN users u ON l.user_id = u.id
            {where_sql}
            ORDER BY l.created_at DESC
        """
        cur.execute(query, tuple(params))
        leads = cur.fetchall()

        export_rows = []
        for l in leads:
            row = dict(l)
            # Phone + Location — from the lead's own data / company-db payload
            phone, location = extract_phone_location(row)
            row["phone"] = phone
            row["location"] = location
            # For investor leads, surface the investing sector when present in the data
            investor_sector = extract_investor_sector(row)
            if investor_sector:
                row["sector"] = investor_sector
            # raw_payload is only needed server-side for extraction — keep responses lean
            row.pop("raw_payload", None)
            export_rows.append(row)

        return {"leads": export_rows}

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("admin_export_leads_error", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if 'conn' in locals():
            conn.close()

@router.get("/stats/global")
def get_global_stats(
    user_id: Any = Header(None, alias="X-User-Id"),
    owner: str | None = None,
    period: str | None = 'ALL',
    _t: Any = None
):
    """
    Aggregates metrics across the entire workspace.
    Supports owner (sender) filter and time range (DAILY/WEEKLY/MONTHLY/QUARTERLY/ALL).
    """
    cache_key = f"admin_stats_global:{user_id}:{owner}:{period}"
    if redis_available and redis_client:
        try:
            cached = redis_client.get(cache_key)
            if cached:
                return json.loads(cached)
        except Exception:
            pass

    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

        uid = normalize_user_id(user_id)

        is_admin = False
        if uid:
            cur.execute("SELECT role FROM users WHERE id = %s", (uid,))
            role_row = cur.fetchone()
            if role_row:
                role_val = role_row['role'] if isinstance(role_row, dict) else role_row[0]
                if role_val and str(role_val).upper() == 'ADMIN':
                    is_admin = True

        if not is_admin and not uid:
            return {"total_leads": 0, "interested": 0, "meetings": 0, "active_flows": 0, "avg_score": 0, "total_followups": 0, "engaged": 0}

        # Build lead-level filters
        l_clauses = ["TRUE"]
        l_params = []

        if not is_admin and uid:
            l_clauses.append("l.user_id = %s")
            l_params.append(uid)
        if owner and owner != 'ALL':
            l_clauses.append("u.username ILIKE %s")
            l_params.append(owner)
        if period and period != 'ALL':
            if period == 'DAILY':
                l_clauses.append("l.updated_at AT TIME ZONE 'Asia/Kolkata' >= (NOW() AT TIME ZONE 'Asia/Kolkata')::date")
            elif period == 'WEEKLY':
                l_clauses.append("l.updated_at AT TIME ZONE 'Asia/Kolkata' >= (NOW() AT TIME ZONE 'Asia/Kolkata')::date - INTERVAL '6 days'")
            elif period == 'MONTHLY':
                l_clauses.append("l.updated_at AT TIME ZONE 'Asia/Kolkata' >= (NOW() AT TIME ZONE 'Asia/Kolkata')::date - INTERVAL '29 days'")
            elif period == 'QUARTERLY':
                l_clauses.append("l.updated_at AT TIME ZONE 'Asia/Kolkata' >= (NOW() AT TIME ZONE 'Asia/Kolkata')::date - INTERVAL '89 days'")

        l_where = f"WHERE {' AND '.join(l_clauses)}"
        from_l = "FROM leads_raw l LEFT JOIN users u ON l.user_id = u.id"

        # Build activity_log-level filters
        a_clauses = ["TRUE"]
        a_params = []

        if not is_admin and uid:
            a_clauses.append("al.user_id = %s")
            a_params.append(uid)
        if owner and owner != 'ALL':
            a_clauses.append("u.username ILIKE %s")
            a_params.append(owner)
        if period and period != 'ALL':
            if period == 'DAILY':
                a_clauses.append("al.created_at AT TIME ZONE 'Asia/Kolkata' >= (NOW() AT TIME ZONE 'Asia/Kolkata')::date")
            elif period == 'WEEKLY':
                a_clauses.append("al.created_at AT TIME ZONE 'Asia/Kolkata' >= (NOW() AT TIME ZONE 'Asia/Kolkata')::date - INTERVAL '6 days'")
            elif period == 'MONTHLY':
                a_clauses.append("al.created_at AT TIME ZONE 'Asia/Kolkata' >= (NOW() AT TIME ZONE 'Asia/Kolkata')::date - INTERVAL '29 days'")
            elif period == 'QUARTERLY':
                a_clauses.append("al.created_at AT TIME ZONE 'Asia/Kolkata' >= (NOW() AT TIME ZONE 'Asia/Kolkata')::date - INTERVAL '89 days'")

        a_where = f"WHERE {' AND '.join(a_clauses)}"
        from_act = "FROM activity_log al JOIN leads_raw l ON al.lead_id = l.id LEFT JOIN users u ON l.user_id = u.id"

        # Total leads (all dispatched outreach statuses — NOT just exact 'SENT',
        # since leads that progressed to OPENED/CLICKED/REPLIED are no longer 'SENT')
        # Same literal values as metrics.py's sent set — PostgreSQL IN is
        # case-sensitive, so both endpoints must count the exact same statuses.
        _SENT_STATUSES = "('SENT', 'OPENED', 'CLICKED', 'REPLIED', 'CLOSED', 'Meeting Scheduled', 'Contacted', 'Interested')"
        cur.execute(f"SELECT COUNT(*) {from_l} {l_where} AND l.email_status IN {_SENT_STATUSES}", tuple(l_params))
        total_leads = cur.fetchone()[0]

        # Interested (Intent)
        cur.execute(f"SELECT COUNT(*) {from_l} {l_where} AND l.reply_intent ILIKE 'INTERESTED'", tuple(l_params))
        interested = cur.fetchone()[0]

        # Meetings
        cur.execute(f"SELECT COUNT(*) {from_l} {l_where} AND (l.email_status ILIKE 'Meeting Scheduled' OR l.meeting_time IS NOT NULL)", tuple(l_params))
        meetings = cur.fetchone()[0]

        # Active Flows
        cur.execute(f"SELECT COUNT(*) {from_l} {l_where} AND (l.followup_status ILIKE 'ACTIVE' OR l.campaign_id IS NOT NULL)", tuple(l_params))
        active_flows = cur.fetchone()[0]

        # Avg Score
        cur.execute(f"SELECT AVG(l.sentiment_score) {from_l} {l_where} AND l.sentiment_score IS NOT NULL", tuple(l_params))
        avg_score = cur.fetchone()[0] or 0

        # Total Followups Sent
        cur.execute(f"SELECT COUNT(*) {from_act} {a_where} AND al.action IN ('AUTO_FOLLOWUP_SENT', 'FOLLOWUP_APPROVED')", tuple(a_params))
        total_followups = cur.fetchone()[0]

        # Engaged Leads
        cur.execute(f"SELECT COUNT(*) {from_l} {l_where} AND (l.reply_intent ILIKE 'INTERESTED' OR l.reply_intent ILIKE 'MEETING_SCHEDULED' OR l.is_responded = TRUE)", tuple(l_params))
        engaged = cur.fetchone()[0]

        # System Reach = delivered (sent minus bounced)
        # Bounce Rate (invalid emails) — computed BEFORE rates so delivered is accurate
        cur.execute(f"SELECT COUNT(*) {from_l} {l_where} AND l.email_status = 'BOUNCED'", tuple(l_params))
        bounced = cur.fetchone()[0]
        system_reach = max(total_leads - bounced, 0)

        # Unique opens/clicks from the tracking-pixel activity log, measured over
        # the SAME sent cohort as total_leads/delivered (COHORT METHOD). Filtering
        # open events by their own date would misalign numerator vs denominator
        # (e.g. leads sent in June opening in July) and produce >100% rates.
        cur.execute(
            f"SELECT COUNT(DISTINCT al.lead_id) FROM activity_log al WHERE al.action = 'OPENED' AND al.lead_id IN (SELECT l.id {from_l} {l_where} AND l.email_status IN {_SENT_STATUSES})",
            tuple(l_params),
        )
        opened = cur.fetchone()[0]

        cur.execute(
            f"SELECT COUNT(DISTINCT al.lead_id) FROM activity_log al WHERE al.action = 'CLICKED' AND al.lead_id IN (SELECT l.id {from_l} {l_where} AND l.email_status IN {_SENT_STATUSES})",
            tuple(l_params),
        )
        clicked = cur.fetchone()[0]

        # Opt-outs
        cur.execute(f"SELECT COUNT(*) {from_l} {l_where} AND l.reply_intent = 'NOT_INTERESTED'", tuple(l_params))
        opt_outs = cur.fetchone()[0]

        # Rates — all over delivered (sent - bounced)
        open_rate = round((opened / system_reach * 100), 1) if system_reach > 0 else 0
        click_rate = round((clicked / system_reach * 100), 1) if system_reach > 0 else 0
        bounce_rate = round((bounced / total_leads * 100), 1) if total_leads > 0 else 0

        # Conversion Rate
        conversion_rate = round((engaged / total_leads * 100), 1) if total_leads > 0 else 0

        # Intent Breakdown
        cur.execute(f"""
            SELECT COALESCE(l.reply_intent, 'UNKNOWN') as label, COUNT(*) as value
            {from_l} {l_where}
            GROUP BY 1
            ORDER BY 2 DESC
        """, tuple(l_params))
        intent_breakdown = [dict(r) for r in cur.fetchall()]

        # Owner Breakdown
        cur.execute("""
            SELECT COALESCE(u.username, 'Unassigned') as label, COUNT(l.id) as value
            FROM users u
            LEFT JOIN leads_raw l ON l.user_id = u.id
            GROUP BY 1
            ORDER BY 2 DESC
        """)
        owner_breakdown = [dict(r) for r in cur.fetchall()]

        # Type Breakdown
        cur.execute(f"""
            SELECT ({TYPE_CASE_SQL}) as label, COUNT(*) as value
            {from_l} {l_where}
            GROUP BY 1
            ORDER BY 2 DESC
        """, tuple(l_params))
        type_breakdown = [dict(r) for r in cur.fetchall()]

        # Sector Breakdown — cleanup pass
        try:
            cur.execute("""
                SELECT id, company_name, designation, raw_payload->>'remarks' as remarks, sector, lead_type
                FROM leads_raw
                WHERE UPPER(COALESCE(sector, '')) IN ('INVESTOR', 'CLIENT', 'OTHER', '')
                LIMIT 20
            """)
            to_fix = cur.fetchall()
            if to_fix:
                from app.utils.classification import infer_lead_classification
                for row in to_fix:
                    try:
                        new_type, new_sector = infer_lead_classification(
                            row['company_name'],
                            row['designation'],
                            row['remarks'] or '',
                            None
                        )
                        if new_sector.upper() in ['INVESTOR', 'CLIENT']:
                            new_sector = 'Other'
                        cur.execute("""
                            UPDATE leads_raw
                            SET lead_type = %s, sector = %s, updated_at = NOW()
                            WHERE id = %s
                        """, (new_type, new_sector, row['id']))
                        conn.commit()
                    except Exception as row_err:
                        logger.warning("row_update_skipped", error=str(row_err))
                        continue
        except Exception as e:
            logger.warning("stats_cleanup_skipped", error=str(e))
            if conn:
                conn.rollback()

        cur.execute(f"""
            SELECT ({SECTOR_CASE_SQL}) as label, COUNT(*) as value
            {from_l} {l_where}
            GROUP BY 1
            ORDER BY 2 DESC
            LIMIT 10
        """, tuple(l_params))
        sector_breakdown = [dict(r) for r in cur.fetchall()]

        # Source Breakdown
        cur.execute(f"""
            SELECT COALESCE(l.source, 'Direct') as label, COUNT(*) as value
            {from_l} {l_where}
            GROUP BY 1
            ORDER BY 2 DESC
        """, tuple(l_params))
        source_breakdown = [dict(r) for r in cur.fetchall()]

        result = {
            "total_leads": total_leads,
            "interested": interested,
            "meetings": meetings,
            "active_flows": active_flows,
            "total_followups": total_followups,
            "avg_score": round(float(avg_score), 2),
            "engaged": engaged,
            "system_reach": system_reach,
            "open_rate": open_rate,
            "click_rate": click_rate,
            "bounced": bounced,
            "bounce_rate": bounce_rate,
            "conversion_rate": conversion_rate,
            "opt_outs": opt_outs,
            "intent_breakdown": intent_breakdown,
            "owner_breakdown": owner_breakdown,
            "type_breakdown": type_breakdown,
            "sector_breakdown": sector_breakdown,
            "source_breakdown": source_breakdown
        }
        if redis_available and redis_client:
            with contextlib.suppress(Exception):
                redis_client.setex(cache_key, 5, json.dumps(result, cls=DateTimeEncoder))
        return result

    except Exception as e:
        logger.exception("admin_global_stats_error", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if 'cur' in locals(): cur.close()
        if 'conn' in locals(): conn.close()

@router.get("/stats/breakdown")
def get_filtered_breakdowns(
    user_id: str | None = Header(None, alias="X-User-Id"),
    type: str | None = None,
    status: str | None = None,
    owner: str | None = None,
    sector: str | None = None,
    period: str | None = None,
    _t: Any = None
):
    """
    Returns chart breakdowns filtered by type/status/owner/sector.
    """
    cache_key = f"admin_breakdowns:{user_id}:{type}:{status}:{owner}:{sector}:{period}"
    if redis_available and redis_client:
        try:
            cached = redis_client.get(cache_key)
            if cached:
                return json.loads(cached)
        except Exception:
            pass

    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        uid = normalize_user_id(user_id)

        is_admin = False
        if uid:
            cur.execute("SELECT role FROM users WHERE id = %s", (uid,))
            role_row = cur.fetchone()
            if role_row:
                role_val = role_row['role'] if isinstance(role_row, dict) else role_row[0]
                if role_val and str(role_val).upper() == 'ADMIN':
                    is_admin = True

        clauses = []
        params = []

        if not is_admin and uid:
            clauses.append("l.user_id = %s")
            params.append(uid)

        if type and type != 'ALL':
            clauses.append(f"({TYPE_CASE_SQL}) = %s")
            params.append(type.upper())
        if status and status != 'ALL':
            clauses.append("l.email_status ILIKE %s")
            params.append(status)
        if owner and owner != 'ALL':
            clauses.append("u.username ILIKE %s")
            params.append(owner)
        if sector and sector != 'ALL':
            # Sector filter also matches investing-sector keys inside the investor payload
            clauses.append(f"""(
                ({SECTOR_CASE_SQL}) = %s
                OR COALESCE(l.sector, '') ILIKE '%%' || %s || '%%'
                OR (({TYPE_CASE_SQL}) = 'INVESTOR' AND (
                        l.raw_payload->>'Investment Sectors' ILIKE '%%' || %s || '%%'
                     OR l.raw_payload->>'Investing Sector' ILIKE '%%' || %s || '%%'
                     OR l.raw_payload->>'Sector Focus' ILIKE '%%' || %s || '%%'
                     OR l.raw_payload->>'Target Sectors' ILIKE '%%' || %s || '%%'
                     OR l.raw_payload->>'Preferred Sectors' ILIKE '%%' || %s || '%%'
                     OR l.raw_payload->>'Focus Sectors' ILIKE '%%' || %s || '%%'
                     OR l.raw_payload->>'Investment Focus' ILIKE '%%' || %s || '%%'
                     OR l.raw_payload->>'Portfolio Focus' ILIKE '%%' || %s || '%%'
                     OR l.raw_payload->>'Category' ILIKE '%%' || %s || '%%'
                ))
            )""")
            params.extend([sector.upper(), sector])
            params.extend([sector] * 9)
        if period and period != 'ALL':
            if period == 'DAILY':
                clauses.append("l.updated_at AT TIME ZONE 'Asia/Kolkata' >= (NOW() AT TIME ZONE 'Asia/Kolkata')::date")
            elif period == 'WEEKLY':
                clauses.append("l.updated_at AT TIME ZONE 'Asia/Kolkata' >= (NOW() AT TIME ZONE 'Asia/Kolkata')::date - INTERVAL '6 days'")
            elif period == 'MONTHLY':
                clauses.append("l.updated_at AT TIME ZONE 'Asia/Kolkata' >= (NOW() AT TIME ZONE 'Asia/Kolkata')::date - INTERVAL '29 days'")
            elif period == 'QUARTERLY':
                clauses.append("l.updated_at AT TIME ZONE 'Asia/Kolkata' >= (NOW() AT TIME ZONE 'Asia/Kolkata')::date - INTERVAL '89 days'")

        where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ""

        from_clause = "FROM leads_raw l LEFT JOIN users u ON l.user_id = u.id"

        # Intent Breakdown
        cur.execute(f"""
            SELECT COALESCE(l.reply_intent, 'UNKNOWN') as label, COUNT(*) as value
            {from_clause} {where_sql}
            GROUP BY 1 ORDER BY 2 DESC
        """, tuple(params))
        intent_breakdown = [dict(r) for r in cur.fetchall()]

        # Type Breakdown
        cur.execute(f"""
            SELECT ({TYPE_CASE_SQL}) as label, COUNT(*) as value
            {from_clause} {where_sql}
            GROUP BY 1 ORDER BY 2 DESC
        """, tuple(params))
        type_breakdown = [dict(r) for r in cur.fetchall()]

        # Sector Breakdown
        cur.execute(f"""
            SELECT ({SECTOR_CASE_SQL}) as label, COUNT(*) as value
            {from_clause} {where_sql}
            GROUP BY 1 ORDER BY 2 DESC LIMIT 10
        """, tuple(params))
        sector_breakdown = [dict(r) for r in cur.fetchall()]

        # Source Breakdown
        cur.execute(f"""
            SELECT COALESCE(l.source, 'Direct') as label, COUNT(*) as value
            {from_clause} {where_sql}
            GROUP BY 1 ORDER BY 2 DESC
        """, tuple(params))
        source_breakdown = [dict(r) for r in cur.fetchall()]

        # Followup Stage Breakdown
        cur.execute(f"""
            SELECT COALESCE(l.followup_stage, 0) as stage, COUNT(*) as value
            {from_clause} {where_sql}
            GROUP BY 1 ORDER BY 1
        """, tuple(params))
        followup_stage_breakdown = [dict(r) for r in cur.fetchall()]

        result = {
            "intent_breakdown": intent_breakdown,
            "type_breakdown": type_breakdown,
            "sector_breakdown": sector_breakdown,
            "source_breakdown": source_breakdown,
            "followup_stage_breakdown": followup_stage_breakdown
        }
        if redis_available and redis_client:
            with contextlib.suppress(Exception):
                redis_client.setex(cache_key, 5, json.dumps(result, cls=DateTimeEncoder))
        return result

    except Exception as e:
        logger.exception("admin_filtered_breakdown_error", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if 'cur' in locals(): cur.close()
        if 'conn' in locals(): conn.close()

@router.get("/stats/settings")
def get_system_settings(user_id: Any = Header(None, alias="X-User-Id"), _t: Any = None):
    """Fetches the current Auto-Pilot and system settings for the user."""
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        uid = normalize_user_id(user_id)

        cur.execute("SELECT auto_followup, outreach_daily_limit FROM users WHERE id = %s", (uid,))
        settings = cur.fetchone()

        return {
            "auto_followup": settings['auto_followup'] if settings else False,
            "outreach_daily_limit": settings['outreach_daily_limit'] if (settings and settings['outreach_daily_limit'] is not None) else 999999
        }
    except Exception as e:
        logger.exception("get_settings_error", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if 'cur' in locals(): cur.close()
        if 'conn' in locals(): conn.close()

@router.post("/stats/settings")
def update_system_settings(req: dict[str, Any], user_id: str | None = Header(None, alias="X-User-Id")):
    """Updates Auto-Pilot and system settings."""
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        uid = normalize_user_id(user_id)

        auto_followup = req.get("auto_followup", False)
        daily_limit = req.get("outreach_daily_limit")
        # 0/None means "unlimited" — matches the GET default (999999) so the
        # value shown on the Followups page matches what check_daily_email_limit
        # actually enforces.
        if daily_limit is None or daily_limit == 0:
            daily_limit = 999999

        cur.execute("""
            UPDATE users
            SET auto_followup = %s, outreach_daily_limit = %s
            WHERE id = %s
        """, (auto_followup, daily_limit, uid))

        conn.commit()

        return {"success": True}
    except Exception as e:
        logger.exception("update_settings_error", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if 'cur' in locals(): cur.close()
        if 'conn' in locals(): conn.close()
