
from fastapi import APIRouter, Depends, HTTPException, Header
from typing import List, Optional, Dict, Any
import psycopg2.extras
from app.database import get_db_connection
import structlog
import json
import os
import datetime
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
    REDIS_URL = os.getenv("REDIS_URL") or os.getenv("REDIS_TLS_URL") or "redis://localhost:6379"
    redis_client = redis.Redis.from_url(
        REDIS_URL,
        decode_responses=True,
    )
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

SECTOR_CASE_SQL = """
CASE
    -- Vismaya templates: explicit template-name mapping
    WHEN l.draft_template_used = 'vismaya_leadstream'
      THEN 'SAAS'

    -- Kajal templates: explicit template-name mapping (highest priority)
    WHEN l.draft_template_used = 'kajal_mam_jv'
      THEN 'REAL ESTATE'
    WHEN l.draft_template_used = 'kajal_mam_hyphen'
      THEN 'LOGISTICS'
    WHEN l.draft_template_used = 'kajal_mam_health_ecosystem'
      THEN 'HEALTHCARE'
    WHEN l.draft_template_used = 'kajal_mam_agritech'
      THEN 'AGRITECH'
    WHEN l.draft_template_used = 'kajal_mam_qvscl_intro'
      THEN 'CORPORATE ADVISORY'

    -- Yashika templates: explicit template-name mapping
    WHEN l.draft_template_used = 'yashika_draft_ai_tech'
      THEN 'AI HIRING'
    WHEN l.draft_template_used = 'yashika_draft_agritech'
      THEN 'AGRITECH'

    -- Palak templates: explicit template-name mapping
    WHEN l.draft_template_used = 'palak_mam_corporate_advisory'
      THEN 'CORPORATE ADVISORY'
    WHEN l.draft_template_used = 'palak_mam_mna_fundraising'
      THEN 'M&A / FUNDRAISING'
    WHEN l.draft_template_used = 'palak_mam_Draft_1'
      THEN 'M&A / STRATEGIC PARTNERSHIP'

    -- 1. Real Estate (JV / Noida NCR)
    WHEN COALESCE(l.email_draft, '') ~* 'JV & Investment|JV, Investment|Noida NCR|Leasing \\| Noida NCR'
      OR COALESCE(l.first_outreach_subject, '') ~* 'JV & Investment|JV, Investment|Noida NCR|Leasing \\| Noida NCR'
      THEN 'REAL ESTATE'

    -- 2. Logistics (Warehousing & Fulfilment)
    WHEN COALESCE(l.email_draft, '') ~* 'Warehousing & Fulfilment|67K\\+ Warehouses'
      OR COALESCE(l.first_outreach_subject, '') ~* 'Warehousing & Fulfilment|67K\\+ Warehouses'
      THEN 'LOGISTICS'

    -- 3. AI Hiring (Gigin)
    WHEN COALESCE(l.email_draft, '') ~* 'vertical AI-powered hiring|hiring intelligence|gigin|hiring platform'
      OR COALESCE(l.first_outreach_subject, '') ~* 'vertical AI-powered hiring|hiring intelligence|gigin|hiring platform'
      THEN 'AI HIRING'

    -- 4. Corporate Advisory (content fallback)
    WHEN COALESCE(l.email_draft, '') ~* 'Corporate Advisory/ Equity Fund Raising|Corporate Advisory/Equity Fund|QVSCL: Capital & Growth Solutions'
      OR COALESCE(l.first_outreach_subject, '') ~* 'Corporate Advisory/ Equity Fund Raising|Corporate Advisory/Equity Fund|QVSCL: Capital & Growth Solutions'
      THEN 'CORPORATE ADVISORY'

    -- 5. M&A / Fundraising (content fallback)
    WHEN COALESCE(l.email_draft, '') ~* 'Supporting Growth Through M&A and Fundraising'
      OR COALESCE(l.first_outreach_subject, '') ~* 'Supporting Growth Through M&A and Fundraising'
      THEN 'M&A / FUNDRAISING'

    -- 6. M&A / Strategic Partnership (content fallback)
    WHEN COALESCE(l.email_draft, '') ~* 'India Entry Advisory|Partnership Opportunity|Strategic Partnership'
      OR COALESCE(l.first_outreach_subject, '') ~* 'India Entry Advisory|Partnership Opportunity|Strategic Partnership'
      THEN 'M&A / STRATEGIC PARTNERSHIP'

    -- 7. Climate Tech
    WHEN COALESCE(l.email_draft, '') ~* 'climate|carbon|solar|renewable|green tech|clean tech|cleantech|sustainability'
      OR COALESCE(l.remarks, '') ~* 'climate|carbon|solar|renewable|green tech|clean tech|cleantech|sustainability'
      OR COALESCE(l.persona, '') ~* 'climate|carbon|solar|renewable|green tech|clean tech|cleantech|sustainability'
      OR COALESCE(l.first_outreach_subject, '') ~* 'climate|carbon|solar|renewable|green tech|clean tech|cleantech|sustainability'
      OR COALESCE(l.last_outreach_subject, '') ~* 'climate|carbon|solar|renewable|green tech|clean tech|cleantech|sustainability'
      OR COALESCE(l.sector, '') ~* 'climate|carbon|solar|renewable|green tech|clean tech|cleantech|sustainability'
      OR COALESCE(l.industry, '') ~* 'climate|carbon|solar|renewable|green tech|clean tech|cleantech|sustainability'
      THEN 'CLIMATE TECH'

    -- 8. AI Hiring (Fallback)
    WHEN COALESCE(l.email_draft, '') ~* 'hiring|recruitment|talent|hrtech'
      OR COALESCE(l.remarks, '') ~* 'hiring|recruitment|talent|hrtech'
      OR COALESCE(l.persona, '') ~* 'hiring|recruitment|talent|hrtech'
      OR COALESCE(l.first_outreach_subject, '') ~* 'hiring|recruitment|talent|hrtech'
      OR COALESCE(l.last_outreach_subject, '') ~* 'hiring|recruitment|talent|hrtech'
      OR COALESCE(l.sector, '') ~* 'hiring|recruitment|talent|hrtech'
      OR COALESCE(l.industry, '') ~* 'hiring|recruitment|talent|hrtech'
      THEN 'AI HIRING'

    -- 9. Healthcare
    WHEN COALESCE(l.email_draft, '') ~* 'hospital|healthcare|medical|health tech|clinical|pharma|clinic'
      OR COALESCE(l.remarks, '') ~* 'hospital|healthcare|medical|health tech|clinical|pharma|clinic'
      OR COALESCE(l.persona, '') ~* 'hospital|healthcare|medical|health tech|clinical|pharma|clinic'
      OR COALESCE(l.first_outreach_subject, '') ~* 'hospital|healthcare|medical|health tech|clinical|pharma|clinic'
      OR COALESCE(l.last_outreach_subject, '') ~* 'hospital|healthcare|medical|health tech|clinical|pharma|clinic'
      OR COALESCE(l.sector, '') ~* 'hospital|healthcare|medical|health tech|clinical|pharma|clinic'
      OR COALESCE(l.industry, '') ~* 'hospital|healthcare|medical|health tech|clinical|pharma|clinic'
      THEN 'HEALTHCARE'

    -- 10. Agritech — word-boundary matching to avoid over-matching
    WHEN COALESCE(l.email_draft, '') ~* '\yagritech\y|\yagriculture\y|\yagri\y|\yfarming\y|\yfoodtech\y|\yagtech\y|\yagribusiness\y'
      OR COALESCE(l.remarks, '') ~* '\yagritech\y|\yagriculture\y|\yagri\y|\yfarming\y|\yfoodtech\y|\yagtech\y|\yagribusiness\y'
      OR COALESCE(l.persona, '') ~* '\yagritech\y|\yagriculture\y|\yagri\y|\yfarming\y|\yfoodtech\y|\yagtech\y|\yagribusiness\y'
      OR COALESCE(l.first_outreach_subject, '') ~* '\yagritech\y|\yagriculture\y|\yagri\y|\yfarming\y|\yfoodtech\y|\yagtech\y|\yagribusiness\y'
      OR COALESCE(l.last_outreach_subject, '') ~* '\yagritech\y|\yagriculture\y|\yagri\y|\yfarming\y|\yfoodtech\y|\yagtech\y|\yagribusiness\y'
      OR COALESCE(l.sector, '') ~* '\yagritech\y|\yagriculture\y|\yagri\y|\yfarming\y|\yfoodtech\y|\yagtech\y|\yagribusiness\y'
      OR COALESCE(l.industry, '') ~* '\yagritech\y|\yagriculture\y|\yagri\y|\yfarming\y|\yfoodtech\y|\yagtech\y|\yagribusiness\y'
      THEN 'AGRITECH'

    -- 11. Edtech
    WHEN COALESCE(l.email_draft, '') ~* 'edtech|education|school|learning'
      OR COALESCE(l.remarks, '') ~* 'edtech|education|school|learning'
      OR COALESCE(l.persona, '') ~* 'edtech|education|school|learning'
      OR COALESCE(l.first_outreach_subject, '') ~* 'edtech|education|school|learning'
      OR COALESCE(l.last_outreach_subject, '') ~* 'edtech|education|school|learning'
      OR COALESCE(l.sector, '') ~* 'edtech|education|school|learning'
      OR COALESCE(l.industry, '') ~* 'edtech|education|school|learning'
      THEN 'EDTECH'

    -- 12. Fintech
    WHEN COALESCE(l.email_draft, '') ~* 'fintech|banking|finance|payments'
      OR COALESCE(l.remarks, '') ~* 'fintech|banking|finance|payments'
      OR COALESCE(l.persona, '') ~* 'fintech|banking|finance|payments'
      OR COALESCE(l.first_outreach_subject, '') ~* 'fintech|banking|finance|payments'
      OR COALESCE(l.last_outreach_subject, '') ~* 'fintech|banking|finance|payments'
      OR COALESCE(l.sector, '') ~* 'fintech|banking|finance|payments'
      OR COALESCE(l.industry, '') ~* 'fintech|banking|finance|payments'
      THEN 'FINTECH'

    -- 13. SaaS
    WHEN COALESCE(l.email_draft, '') ~* 'saas|software|b2b saas'
      OR COALESCE(l.remarks, '') ~* 'saas|software|b2b saas'
      OR COALESCE(l.persona, '') ~* 'saas|software|b2b saas'
      OR COALESCE(l.first_outreach_subject, '') ~* 'saas|software|b2b saas'
      OR COALESCE(l.last_outreach_subject, '') ~* 'saas|software|b2b saas'
      OR COALESCE(l.sector, '') ~* 'saas|software|b2b saas'
      OR COALESCE(l.industry, '') ~* 'saas|software|b2b saas'
      THEN 'SAAS'

    ELSE COALESCE(NULLIF(TRIM(UPPER(l.sector)), 'OTHER'), NULLIF(TRIM(UPPER(l.industry)), 'OTHER'), 'OTHER')
END
"""

class BulkApproveRequest(BaseModel):
    lead_ids: List[int]

@router.post("/leads/bulk-approve")
def bulk_approve_leads(req: BulkApproveRequest, user_id: Optional[str] = Header(None, alias="X-User-Id")):
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
        logger.error("bulk_approve_error", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if 'conn' in locals():
            conn.close()

def normalize_user_id(uid):
    if not uid or str(uid).strip() == "":
        return None
    if str(uid).lower() == "admin":
        return 1
    if str(uid).isdigit():
        return int(uid)
        
    # Resolve username or email or full_name to integer ID
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            SELECT id FROM users 
            WHERE LOWER(username) = LOWER(%s) 
            OR LOWER(email) = LOWER(%s)
            OR LOWER(full_name) = LOWER(%s)
            LIMIT 1
        """, (str(uid), str(uid), str(uid)))
        res = cur.fetchone()
        cur.close()
        conn.close()
        if res:
            return res[0]
    except Exception as e:
        logger.error(f"Error resolving user identity {uid} in admin_dashboard: {e}")
        
    return None

@router.get("/leads/all")
def get_all_leads_admin(
    user_id: Optional[str] = Header(None, alias="X-User-Id"),
    page: int = 1,
    limit: int = 50,
    type: Optional[str] = None,
    status: Optional[str] = None,
    intent: Optional[str] = None,
    owner: Optional[str] = None,
    sector: Optional[str] = None,
    search: Optional[str] = None,
    period: Optional[str] = None
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
        if status and status != 'ALL':
            if status.upper() == 'REPLIED':
                # STRICT: Must have is_responded flag OR status is explicitly REPLIED
                where_clauses.append("(l.email_status ILIKE 'REPLIED' OR l.is_responded = TRUE)")
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
            where_clauses.append(f"( ({SECTOR_CASE_SQL}) = %s OR COALESCE(l.sector, '') ILIKE '%%' || %s || '%%' )")
            params.append(sector.upper())
            params.append(sector)
        if search:
            where_clauses.append("(l.first_name ILIKE %s OR l.last_name ILIKE %s OR l.company_name ILIKE %s OR l.email ILIKE %s)")
            s_param = f"%{search}%"
            params.extend([s_param, s_param, s_param, s_param])
        if period and period != 'ALL':
            if period == 'DAILY':
                where_clauses.append("l.updated_at AT TIME ZONE 'Asia/Kolkata' >= (NOW() AT TIME ZONE 'Asia/Kolkata')::date")
            elif period == 'WEEKLY':
                where_clauses.append("l.updated_at AT TIME ZONE 'Asia/Kolkata' >= (NOW() AT TIME ZONE 'Asia/Kolkata')::date - INTERVAL '6 days'")
            elif period == 'MONTHLY':
                where_clauses.append("l.updated_at AT TIME ZONE 'Asia/Kolkata' >= (NOW() AT TIME ZONE 'Asia/Kolkata')::date - INTERVAL '29 days'")
            elif period == 'QUARTERLY':
                where_clauses.append("l.updated_at AT TIME ZONE 'Asia/Kolkata' >= (NOW() AT TIME ZONE 'Asia/Kolkata')::date - INTERVAL '89 days'")
            
        where_sql = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""

        # 3. Fetch leads
        query = f"""
            SELECT l.id, l.first_name, l.last_name, l.email, l.phone, l.company_name, l.family_office_name, l.designation, 
                   ({SECTOR_CASE_SQL}) as sector, ({TYPE_CASE_SQL}) as lead_type, l.reply_intent, l.sentiment_score, l.deal_size, l.check_size, l.source,
                   l.user_id, l.created_at, l.updated_at, l.rag_advice, l.rag_intelligence,
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
        cur.execute(f"""
            SELECT DISTINCT sector_name FROM (
                SELECT ({SECTOR_CASE_SQL}) as sector_name FROM leads_raw l
                UNION
                SELECT TRIM(BOTH FROM s) as sector_name
                FROM leads_raw, regexp_split_to_table(COALESCE(sector, 'Other'), ',') as s
                WHERE TRIM(BOTH FROM s) != '' AND TRIM(BOTH FROM s) != 'Other'
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
            try:
                redis_client.setex(cache_key, 5, json.dumps(result, cls=DateTimeEncoder))
            except Exception:
                pass
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("admin_all_leads_error", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if 'conn' in locals():
            conn.close()

@router.get("/leads/export")
def export_all_leads_admin(
    period: Optional[str] = "ALL", 
    user_id: Optional[str] = Header(None, alias="X-User-Id")
):
    """
    Returns filtered leads in the system without pagination for full master export.
    Supports period: DAILY, WEEKLY, MONTHLY, QUARTERLY, YEARLY, ALL
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

        # 2. Build Range Filter (IST timezone — filter by updated_at)
        range_clause = ""
        if period == 'DAILY':
            range_clause = "AND l.updated_at AT TIME ZONE 'Asia/Kolkata' >= (NOW() AT TIME ZONE 'Asia/Kolkata')::date"
        elif period == 'WEEKLY':
            range_clause = "AND l.updated_at AT TIME ZONE 'Asia/Kolkata' >= (NOW() AT TIME ZONE 'Asia/Kolkata')::date - INTERVAL '6 days'"
        elif period == 'MONTHLY':
            range_clause = "AND l.updated_at AT TIME ZONE 'Asia/Kolkata' >= (NOW() AT TIME ZONE 'Asia/Kolkata')::date - INTERVAL '29 days'"
        elif period == 'QUARTERLY':
            range_clause = "AND l.updated_at AT TIME ZONE 'Asia/Kolkata' >= (NOW() AT TIME ZONE 'Asia/Kolkata')::date - INTERVAL '89 days'"
        elif period == 'YEARLY':
            range_clause = "AND l.updated_at AT TIME ZONE 'Asia/Kolkata' >= (NOW() AT TIME ZONE 'Asia/Kolkata')::date - INTERVAL '364 days'"

        # 3. Fetch leads with derived + raw sector
        query = f"""
            SELECT l.id, l.first_name, l.last_name, l.email, l.phone, l.company_name, l.family_office_name, l.designation, 
                   ({SECTOR_CASE_SQL}) as sector, l.sector as raw_sector, l.lead_type, l.reply_intent, l.sentiment_score, l.deal_size, l.check_size,
                   l.user_id, l.created_at, l.updated_at, l.rag_advice, l.rag_intelligence,
                   l.email_status, l.followup_status,
                   l.persona, l.email_draft, l.first_outreach_subject, l.last_outreach_subject,
                   u.username as owner_name
            FROM leads_raw l
            LEFT JOIN users u ON l.user_id = u.id
            WHERE 1=1 {range_clause}
            ORDER BY l.created_at DESC
        """
        cur.execute(query)
        leads = cur.fetchall()
        
        return {"leads": [dict(l) for l in leads]}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("admin_export_leads_error", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if 'conn' in locals():
            conn.close()

@router.get("/stats/global")
def get_global_stats(
    user_id: Any = Header(None, alias="X-User-Id"),
    owner: Optional[str] = None,
    period: Optional[str] = 'ALL',
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

        # Total leads (only sent, not all records)
        cur.execute(f"SELECT COUNT(*) {from_l} {l_where} AND l.email_status = 'SENT'", tuple(l_params))
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
        
        # System Reach (leads with emails sent)
        cur.execute(f"SELECT COUNT(*) {from_l} {l_where} AND l.email_status IS NOT NULL", tuple(l_params))
        system_reach = cur.fetchone()[0]
        
        # Open Rate (using email_status - SENT means delivered)
        cur.execute(f"SELECT COUNT(*) {from_l} {l_where} AND l.email_status = 'OPENED'", tuple(l_params))
        opened = cur.fetchone()[0]
        
        # Click Rate (leads who clicked)
        cur.execute(f"SELECT COUNT(*) {from_l} {l_where} AND l.email_status = 'CLICKED'", tuple(l_params))
        clicked = cur.fetchone()[0]
        
        # Bounce Rate (invalid emails)
        cur.execute(f"SELECT COUNT(*) {from_l} {l_where} AND l.email_status = 'BOUNCED'", tuple(l_params))
        bounced = cur.fetchone()[0]
        
        # Opt-outs
        cur.execute(f"SELECT COUNT(*) {from_l} {l_where} AND l.reply_intent = 'NOT_INTERESTED'", tuple(l_params))
        opt_outs = cur.fetchone()[0]
        
        # Open Rate %
        open_rate = round((opened / system_reach * 100), 1) if system_reach > 0 else 0
        click_rate = round((clicked / system_reach * 100), 1) if system_reach > 0 else 0
        bounce_rate = round((bounced / system_reach * 100), 1) if system_reach > 0 else 0
        
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
        cur.execute(f"""
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
            "opt_outs": opt_outs,
            "intent_breakdown": intent_breakdown,
            "owner_breakdown": owner_breakdown,
            "type_breakdown": type_breakdown,
            "sector_breakdown": sector_breakdown,
            "source_breakdown": source_breakdown
        }
        if redis_available and redis_client:
            try:
                redis_client.setex(cache_key, 5, json.dumps(result, cls=DateTimeEncoder))
            except Exception:
                pass
        return result
        
    except Exception as e:
        logger.error("admin_global_stats_error", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if 'cur' in locals(): cur.close()
        if 'conn' in locals(): conn.close()

@router.get("/stats/breakdown")
def get_filtered_breakdowns(
    user_id: Optional[str] = Header(None, alias="X-User-Id"),
    type: Optional[str] = None,
    status: Optional[str] = None,
    owner: Optional[str] = None,
    sector: Optional[str] = None,
    period: Optional[str] = None,
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
            clauses.append(f"( ({SECTOR_CASE_SQL}) = %s OR COALESCE(l.sector, '') ILIKE '%%' || %s || '%%' )")
            params.append(sector.upper())
            params.append(sector)
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
            try:
                redis_client.setex(cache_key, 5, json.dumps(result, cls=DateTimeEncoder))
            except Exception:
                pass
        return result
        
    except Exception as e:
        logger.error("admin_filtered_breakdown_error", error=str(e))
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
        logger.error("get_settings_error", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if 'cur' in locals(): cur.close()
        if 'conn' in locals(): conn.close()

@router.post("/stats/settings")
def update_system_settings(req: Dict[str, Any], user_id: Optional[str] = Header(None, alias="X-User-Id")):
    """Updates Auto-Pilot and system settings."""
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        uid = normalize_user_id(user_id)
        
        auto_followup = req.get("auto_followup", False)
        daily_limit = req.get("outreach_daily_limit")
        if daily_limit is None or daily_limit == 0:
            daily_limit = 100
        
        cur.execute("""
            UPDATE users 
            SET auto_followup = %s, outreach_daily_limit = %s 
            WHERE id = %s
        """, (auto_followup, daily_limit, uid))
        
        conn.commit()
        
        return {"success": True}
    except Exception as e:
        logger.error("update_settings_error", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if 'cur' in locals(): cur.close()
        if 'conn' in locals(): conn.close()
