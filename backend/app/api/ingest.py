from fastapi import APIRouter, HTTPException, Header
from pydantic import BaseModel
from typing import Optional
import random
import structlog

from app.services.rocketreach_service import search_leads
from app.models.lead import insert_lead

logger = structlog.get_logger(__name__)
router = APIRouter()

class LeadRequest(BaseModel):
    # Company search fields
    company: Optional[str] = None
    title: Optional[str] = None
    location: Optional[str] = None
    count: Optional[int] = 20
    
    # Bulk search fields
    bulk_title: Optional[str] = None
    bulk_location: Optional[str] = None
    industry: Optional[str] = None
    keyword: Optional[str] = None
    exclude: Optional[str] = None
    source_type: Optional[str] = "direct"
    
    # New Lookup Modes
    mode: Optional[str] = "search" # search, email, name, url
    email: Optional[str] = None
    name: Optional[str] = None
    linkedin_url: Optional[str] = None

def categorize_lead(payload):
    title = str(payload.get("current_title", "")).lower()
    
    # Skip pure engineering roles (no leadership indicator)
    engineer_keywords = ["software engineer", "senior engineer", "developer", "programmer", "coder", "data analyst"]
    leadership_override = any(x in title for x in ["cto", "vp", "head", "director", "chief", "lead engineer"])
    is_pure_engineer = any(x in title for x in engineer_keywords)
    if is_pure_engineer and not leadership_override:
        return "OTHER", random.randint(10, 30)
        
    # FOUNDER — top-level founders, CEOs, managing directors, C-suite execs
    founder_keywords = [
        "founder", "co-founder", "cofounder", "co finder",
        "ceo", "chief executive",
        "md", "managing director",
        "cto", "chief technology",
        "cfo", "chief financial",
        "coo", "chief operating",
        "cco", "chief commercial",
        "president", "group chairman", "owner"
    ]
    if any(x in title for x in founder_keywords):
        return "FOUNDER", random.randint(90, 99)
    
    # INVESTOR — vc, capital, equity, investors
    investor_keywords = [
        "investor", "venture", "vc", "capital", "equity", "investment"
    ]
    if any(x in title for x in investor_keywords):
        return "INVESTOR", random.randint(80, 95)
        
    # PARTNER — partner roles, VP
    partner_keywords = [
        "partner", "general partner", "managing partner",
        "vice president", "vp "
    ]
    if any(x in title for x in partner_keywords):
        return "PARTNER", random.randint(75, 90)
    
    # Other
    return "OTHER", random.randint(40, 65)

@router.post("/ingest")
@router.post("/ingest-leads")
def ingest_leads(req: LeadRequest, user_id: Optional[str] = Header(None, alias="X-User-Id")):
    from app.services.rocketreach_service import search_leads, lookup_by_email, lookup_by_name

    # Log search activity before processing
    try:
        from app.models.lead import add_activity_log
        summary = req.email if req.mode == "email" else (req.name if req.mode == "name" else f"{req.title or ''} at {req.company or ''}")
        add_activity_log(None, "LEAD_SEARCH", f"Mode [{req.mode}] search: {summary or 'Discovery'}", "admin", user_id=user_id)
    except:
        pass

    try:
        leads = []
        if req.mode == "email" and req.email:
            leads = lookup_by_email(req.email)
        elif req.mode == "name" and req.name:
            leads = lookup_by_name(req.name, req.company)
        elif req.mode == "url" and req.linkedin_url:
            from app.services.rocketreach_service import lookup_by_linkedin_url
            leads = lookup_by_linkedin_url(req.linkedin_url)
        else:
            # Default search mode
            employer = req.company or req.industry or ""
            job_title = req.title or req.bulk_title or ""
            loc = req.location or req.bulk_location or ""
            try:
                leads = search_leads(employer, job_title, loc, req.count or 10)
            except Exception as rr_err:
                err_str = str(rr_err)
                if "Insufficient Credits" in err_str or "quota" in err_str.lower() or "403" in err_str:
                    raise HTTPException(
                        status_code=402,
                        detail="RocketReach API quota exhausted. Your RocketReach account has run out of credits. Please top up your RocketReach plan at rocketreach.co to continue bulk discovery."
                    )
                elif "429" in err_str or "Rate Limit" in err_str:
                    raise HTTPException(
                        status_code=429,
                        detail="RocketReach rate limit hit. Please wait a few minutes and try again."
                    )
                raise HTTPException(status_code=500, detail=f"RocketReach search failed: {err_str}")


        if not leads:
            return { "success": True, "fetched": 0, "inserted": 0, "errors": 0, "message": "No results found" }

        # Process and insert leads
        inserted = 0
        errors = 0
        
        for lead in leads:
            if not lead: continue
                
            try:
                persona, fit_score = categorize_lead(lead.get("payload", {}))
                insert_lead(
                    lead["first_name"],
                    lead["last_name"],
                    lead["email"],
                    lead["domain"],
                    lead["linkedin"],
                    lead["company"],
                    req.source_type or lead["source"],
                    lead["payload"],
                    fit_score=fit_score,
                    persona=persona,
                    phone=lead.get("phone"),
                    user_id=user_id
                )
                inserted += 1
            except Exception as e:
                logger.error("lead_insertion_failed", error=str(e), lead_email=lead.get("email"))
                errors += 1
                continue

        if inserted > 0:
            try:
                from app.models.lead import add_activity_log
                details = f"Ingested {inserted} leads via {req.mode} mode"
                add_activity_log(None, "BULK_INGESTION", details, "admin", user_id=user_id)
            except: pass

        if len(leads) > 0 and user_id and str(user_id).lower() != "admin":
            try:
                from app.database import get_db_connection
                c_conn = get_db_connection()
                ccc = c_conn.cursor()
                ccc.execute("UPDATE users SET credits_used = COALESCE(credits_used, 0) + %s WHERE id = %s", (len(leads), user_id))
                c_conn.commit()
                ccc.close()
                c_conn.close()
            except Exception as metric_err:
                logger.error("rocketreach_credits_metric_failed", error=str(metric_err))

        return {
            "success": True,
            "fetched": len(leads),
            "inserted": inserted,
            "errors": errors
        }

    except HTTPException: raise
    except Exception as e:
        logger.error("ingest_leads_critical_error", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))

