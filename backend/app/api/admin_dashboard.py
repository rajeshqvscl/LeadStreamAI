
from fastapi import APIRouter, Depends, HTTPException, Header
from typing import List, Optional, Dict, Any
import psycopg2.extras
from app.database import get_db_connection
import structlog
import json
from pydantic import BaseModel

router = APIRouter()
logger = structlog.get_logger(__name__)

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
    search: Optional[str] = None
):
    """
    Returns paginated leads for the admin dashboard with global filtering.
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

        offset = (page - 1) * limit
        
        # 2. Build Dynamic WHERE Clause
        where_clauses = []
        params = []
        
        if type and type != 'ALL':
            t_upper = type.upper()
            if t_upper == 'GIGIN AI':
                where_clauses.append("u.username ILIKE '%%yashika%%' AND (l.sector NOT ILIKE '%%agri%%' OR l.sector IS NULL)")
            elif t_upper == 'AGRIVIJAY':
                where_clauses.append("u.username ILIKE '%%yashika%%' AND l.sector ILIKE '%%agri%%'")
            else:
                where_clauses.append("l.lead_type ILIKE %s")
                params.append(type)
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
            where_clauses.append("l.sector ILIKE %s")
            params.append(sector)
        if search:
            where_clauses.append("(l.first_name ILIKE %s OR l.last_name ILIKE %s OR l.company_name ILIKE %s OR l.email ILIKE %s)")
            s_param = f"%{search}%"
            params.extend([s_param, s_param, s_param, s_param])
            
        where_sql = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""

        # 3. Fetch leads
        query = f"""
            SELECT l.id, l.first_name, l.last_name, l.email, l.phone, l.company_name, l.designation, 
                   l.sector, l.lead_type, l.reply_intent, l.sentiment_score, l.deal_size,
                   l.user_id, l.created_at, l.updated_at, l.rag_advice, l.rag_intelligence,
                   u.username as owner_name
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
        
        # 5. Dynamic Filters (Fetch all unique sectors and owners for the dropdowns)
        cur.execute("SELECT DISTINCT sector FROM leads_raw WHERE sector IS NOT NULL AND sector != '' ORDER BY sector ASC")
        all_sectors = [r[0] for r in cur.fetchall()]
        
        cur.execute("SELECT DISTINCT username FROM users ORDER BY username ASC")
        all_owners = [r[0] for r in cur.fetchall()]
        
        return {
            "leads": [dict(l) for l in leads],
            "sectors": all_sectors,
            "owners": all_owners,
            "pagination": {
                "total": total_count,
                "page": page,
                "limit": limit,
                "pages": (total_count + limit - 1) // limit
            }
        }
        
    except Exception as e:
        logger.error("admin_all_leads_error", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if 'conn' in locals():
            conn.close()

@router.get("/leads/export")
def export_all_leads_admin(
    range: Optional[str] = "ALL", 
    user_id: Optional[str] = Header(None, alias="X-User-Id")
):
    """
    Returns filtered leads in the system without pagination for full master export.
    Supports range: DAILY, WEEKLY, MONTHLY, QUARTERLY, YEARLY, ALL
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

        # 2. Build Range Filter
        range_clause = ""
        if range == 'DAILY':
            range_clause = "AND l.created_at >= NOW() - INTERVAL '1 day'"
        elif range == 'WEEKLY':
            range_clause = "AND l.created_at >= NOW() - INTERVAL '7 days'"
        elif range == 'MONTHLY':
            range_clause = "AND l.created_at >= NOW() - INTERVAL '30 days'"
        elif range == 'QUARTERLY':
            range_clause = "AND l.created_at >= NOW() - INTERVAL '90 days'"
        elif range == 'YEARLY':
            range_clause = "AND l.created_at >= NOW() - INTERVAL '365 days'"

        # 3. Fetch leads
        query = f"""
            SELECT l.id, l.first_name, l.last_name, l.email, l.phone, l.company_name, l.designation, 
                   l.sector, l.lead_type, l.reply_intent, l.sentiment_score, l.deal_size,
                   l.user_id, l.created_at, l.updated_at, l.rag_advice, l.rag_intelligence,
                   l.email_status, l.followup_status,
                   u.username as owner_name
            FROM leads_raw l
            LEFT JOIN users u ON l.user_id = u.id
            WHERE 1=1 {range_clause}
            ORDER BY l.created_at DESC
        """
        cur.execute(query)
        leads = cur.fetchall()
        
        return {"leads": [dict(l) for l in leads]}
        
    except Exception as e:
        logger.error("admin_export_leads_error", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if 'conn' in locals():
            conn.close()

@router.get("/stats/global")
def get_global_stats(user_id: Any = Header(None, alias="X-User-Id"), _t: Any = None):
    """
    Aggregates metrics across the entire workspace.
    """
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        
        uid = normalize_user_id(user_id)
        
        # Determine if user is admin
        is_admin = False
        if uid:
            cur.execute("SELECT role FROM users WHERE id = %s", (uid,))
            role_row = cur.fetchone()
            if role_row:
                role_val = role_row['role'] if isinstance(role_row, dict) else role_row[0]
                if role_val and str(role_val).upper() == 'ADMIN':
                    is_admin = True

        # Base filter
        base_filter = ""
        params = []
        if not is_admin:
            if uid:
                base_filter = " WHERE user_id = %s"
                params = [uid]
            else:
                return {"total_leads": 0, "interested": 0, "meetings": 0, "active_flows": 0, "avg_score": 0, "total_followups": 0, "engaged": 0}

        # Total leads
        cur.execute(f"SELECT COUNT(*) FROM leads_raw {base_filter}", tuple(params))
        total_leads = cur.fetchone()[0]
        
        # Interested (Intent)
        cur.execute(f"SELECT COUNT(*) FROM leads_raw {base_filter} {'AND' if base_filter else 'WHERE'} reply_intent ILIKE 'INTERESTED'", tuple(params))
        interested = cur.fetchone()[0]
        
        # Meetings
        cur.execute(f"SELECT COUNT(*) FROM leads_raw {base_filter} {'AND' if base_filter else 'WHERE'} (email_status ILIKE 'Meeting Scheduled' OR meeting_time IS NOT NULL)", tuple(params))
        meetings = cur.fetchone()[0]
        
        # Active Flows
        cur.execute(f"SELECT COUNT(*) FROM leads_raw {base_filter} {'AND' if base_filter else 'WHERE'} (followup_status ILIKE 'ACTIVE' OR campaign_id IS NOT NULL)", tuple(params))
        active_flows = cur.fetchone()[0]
        
        # Avg Score
        cur.execute(f"SELECT AVG(sentiment_score) FROM leads_raw {base_filter} {'AND' if base_filter else 'WHERE'} sentiment_score IS NOT NULL", tuple(params))
        avg_score = cur.fetchone()[0] or 0
        
        # Total Followups Sent (Stage 1+)
        # Note: activity_log also has user_id
        act_filter = f" WHERE user_id = %s" if not is_admin else ""
        cur.execute(f"SELECT COUNT(*) FROM activity_log {act_filter} {'AND' if act_filter else 'WHERE'} action IN ('AUTO_FOLLOWUP_SENT', 'FOLLOWUP_APPROVED')", tuple(params))
        total_followups = cur.fetchone()[0]
        
        # Engaged Leads
        cur.execute(f"SELECT COUNT(*) FROM leads_raw {base_filter} {'AND' if base_filter else 'WHERE'} (reply_intent ILIKE 'INTERESTED' OR reply_intent ILIKE 'MEETING_SCHEDULED' OR is_responded = TRUE)", tuple(params))
        engaged = cur.fetchone()[0]
        
        # System Reach (leads with emails sent)
        cur.execute("SELECT COUNT(*) FROM leads_raw WHERE email_status IS NOT NULL")
        system_reach = cur.fetchone()[0]
        
        # Open Rate (using email_status - SENT means delivered)
        cur.execute("SELECT COUNT(*) FROM leads_raw WHERE email_status = 'OPENED'")
        opened = cur.fetchone()[0]
        
        # Click Rate (leads who clicked)
        cur.execute("SELECT COUNT(*) FROM leads_raw WHERE email_status = 'CLICKED'")
        clicked = cur.fetchone()[0]
        
        # Bounce Rate (invalid emails)
        cur.execute("SELECT COUNT(*) FROM leads_raw WHERE email_status = 'BOUNCED'")
        bounced = cur.fetchone()[0]
        
        # Opt-outs
        cur.execute("SELECT COUNT(*) FROM leads_raw WHERE reply_intent = 'NOT_INTERESTED'")
        opt_outs = cur.fetchone()[0]
        
        # Open Rate %
        open_rate = round((opened / system_reach * 100), 1) if system_reach > 0 else 0
        click_rate = round((clicked / system_reach * 100), 1) if system_reach > 0 else 0
        bounce_rate = round((bounced / system_reach * 100), 1) if system_reach > 0 else 0
        
        # Conversion Rate
        conversion_rate = round((engaged / total_leads * 100), 1) if total_leads > 0 else 0

        # Intent Breakdown
        cur.execute("""
            SELECT COALESCE(reply_intent, 'UNKNOWN') as label, COUNT(*) as value 
            FROM leads_raw 
            GROUP BY 1 
            ORDER BY 2 DESC
        """)
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
        cur.execute("""
            SELECT 
                CASE 
                    WHEN u.username ILIKE '%%yashika%%' AND l.sector ILIKE '%%agri%%' THEN 'AGRIVIJAY'
                    WHEN u.username ILIKE '%%yashika%%' THEN 'GIGIN AI'
                    ELSE UPPER(COALESCE(l.lead_type, 'CLIENT'))
                END as label, 
                COUNT(*) as value
            FROM leads_raw l
            LEFT JOIN users u ON l.user_id = u.id
            GROUP BY 1
            ORDER BY 2 DESC
        """)
        type_breakdown = [dict(r) for r in cur.fetchall()]

        # Sector Breakdown (Excluding Type categories like Investor/Client)
        # First, a quick cleanup to ensure consistency (Case Insensitive)
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
                            None # Pass None to force re-inference
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
        
        cur.execute("""
            SELECT COALESCE(sector, 'Other') as label, COUNT(*) as value
            FROM leads_raw
            WHERE UPPER(COALESCE(sector, 'Other')) NOT IN ('INVESTOR', 'CLIENT')
            GROUP BY 1
            ORDER BY 2 DESC
            LIMIT 10
        """)
        sector_breakdown = [dict(r) for r in cur.fetchall()]

        # Source Breakdown
        cur.execute("""
            SELECT COALESCE(source, 'Direct') as label, COUNT(*) as value
            FROM leads_raw
            GROUP BY 1
            ORDER BY 2 DESC
        """)
        source_breakdown = [dict(r) for r in cur.fetchall()]
        
        return {
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
            "bounce_rate": bounce_rate,
            "opt_outs": opt_outs,
            "intent_breakdown": intent_breakdown,
            "owner_breakdown": owner_breakdown,
            "type_breakdown": type_breakdown,
            "sector_breakdown": sector_breakdown,
            "source_breakdown": source_breakdown
        }
        
    except Exception as e:
        logger.error("admin_global_stats_error", error=str(e))
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
            "outreach_daily_limit": settings['outreach_daily_limit'] if (settings and settings['outreach_daily_limit'] is not None) else 200
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
