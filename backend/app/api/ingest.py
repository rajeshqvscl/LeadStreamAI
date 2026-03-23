from fastapi import APIRouter, HTTPException
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
    count: Optional[str] = "10"
    
    # Bulk search fields
    bulk_title: Optional[str] = None
    bulk_location: Optional[str] = None
    industry: Optional[str] = None
    keyword: Optional[str] = None
    exclude: Optional[str] = None

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
        "founder", "co-founder", "cofounder", "co founder",
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
def ingest_leads(req: LeadRequest):
    # Map frontend fields to the search_leads backend logic
    employer = req.company or req.industry or ""
    job_title = req.title or req.bulk_title or ""
    loc = req.location or req.bulk_location or ""
    
    try:
        page_size = int(req.count)
    except Exception:
        page_size = 10

    try:
        # 1. Search leads via RocketReach
        try:
            leads = search_leads(
                employer,
                job_title,
                loc,
                page_size
            )
        except Exception as e:
            logger.error("search_leads_failed", error=str(e))
            raise HTTPException(status_code=400, detail=f"Search failed: {str(e)}")

        # 2. Process and insert leads
        inserted = 0
        errors = 0
        
        for lead in leads:
            if not lead:
                continue
                
            try:
                persona, fit_score = categorize_lead(lead.get("payload", {}))

                insert_lead(
                    lead["first_name"],
                    lead["last_name"],
                    lead["email"],
                    lead["domain"],
                    lead["linkedin"],
                    lead["company"],
                    lead["source"],
                    lead["payload"],
                    fit_score=fit_score,
                    persona=persona,
                    phone=lead.get("phone")
                )
                inserted += 1
            except Exception as e:
                logger.error("lead_insertion_failed", error=str(e), lead_email=lead.get("email"))
                errors += 1
                continue

        return {
            "success": True,
            "fetched": len(leads),
            "inserted": inserted,
            "errors": errors
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error("ingest_leads_critical_error", error=str(e))
        raise HTTPException(status_code=500, detail="Internal server error during ingestion process")