
from fastapi import APIRouter, Depends, HTTPException, Header
from typing import List, Optional
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
    if not uid: return None
    try: return int(uid)
    except: return uid

@router.get("/leads/all")
def get_all_leads_admin(user_id: Optional[str] = Header(None, alias="X-User-Id")):
    """
    Returns ALL leads from ALL users in the database.
    Only accessible by 'admin' role.
    """
    # Simple role check (In a real app, this would check a 'role' column in users table)
    # For now, we use the 'admin' convention or user_id=1 as admin.
    
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        
        # 1. Verify Admin Role
        cur.execute("SELECT username FROM users WHERE id = %s", (normalize_user_id(user_id),))
        user = cur.fetchone()
        if not user or user['username'].lower() != 'admin' and normalize_user_id(user_id) != 1:
             # If you want to be strict, uncomment this. For now we allow if user_id is 'admin' string too.
             if user_id != 'admin':
                raise HTTPException(status_code=403, detail="Admin access required")


        # 2. Fetch all leads with owner names
        query = """
            SELECT l.*, u.username as owner_name, u.full_name as owner_full_name
            FROM leads_raw l
            LEFT JOIN users u ON l.user_id = u.id
            ORDER BY l.updated_at DESC
        """
        cur.execute(query)
        leads = cur.fetchall()
        
        return [dict(l) for l in leads]
        
    except Exception as e:
        logger.error("admin_all_leads_error", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if 'conn' in locals():
            conn.close()

@router.get("/stats/global")
def get_global_stats(user_id: Optional[str] = Header(None, alias="X-User-Id")):
    """
    Aggregates metrics across the entire workspace.
    """
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        
        # Total leads
        cur.execute("SELECT COUNT(*) FROM leads_raw")
        total_leads = cur.fetchone()[0]
        
        # Interested (Intent)
        cur.execute("SELECT COUNT(*) FROM leads_raw WHERE reply_intent = 'INTERESTED'")
        interested = cur.fetchone()[0]
        
        # Meetings
        cur.execute("SELECT COUNT(*) FROM leads_raw WHERE email_status = 'Meeting Scheduled' OR meeting_time IS NOT NULL")
        meetings = cur.fetchone()[0]
        
        # Avg Score (Sentiment)
        cur.execute("SELECT AVG(sentiment_score) FROM leads_raw WHERE sentiment_score IS NOT NULL")
        avg_score = cur.fetchone()[0] or 0
        
        # Active Followups
        cur.execute("SELECT COUNT(*) FROM leads_raw WHERE followup_status = 'ACTIVE'")
        active_followups = cur.fetchone()[0]

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
            SELECT UPPER(COALESCE(lead_type, 'CLIENT')) as label, COUNT(*) as value
            FROM leads_raw
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
            """)
            to_fix = cur.fetchall()
            
            if to_fix:
                from app.utils.classification import infer_lead_classification
                for row in to_fix:
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
                        SET lead_type = %s, sector = %s 
                        WHERE id = %s
                    """, (new_type, new_sector, row['id']))
            conn.commit()
        except Exception as e:
            logger.warning("stats_cleanup_skipped", error=str(e))
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
            "interested_leads": interested,
            "meetings_scheduled": meetings,
            "conversion_rate": round((interested / total_leads * 100), 1) if total_leads > 0 else 0,
            "avg_score": round(float(avg_score), 1),
            "active_followups": active_followups,
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
        if 'conn' in locals():
            conn.close()
