from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
import json
import psycopg2
import psycopg2.extras
from app.database import get_db_connection
from app.models.lead import get_lead_by_id, update_lead, get_activity_log, add_activity_log

router = APIRouter()

class LeadUpdate(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    company_name: Optional[str] = None
    industry: Optional[str] = None
    city: Optional[str] = None
    country: Optional[str] = None
    linkedin_url: Optional[str] = None
    persona: Optional[str] = None
    fit_score: Optional[int] = None
    campaign_id: Optional[int] = None
    family_office_name: Optional[str] = None

@router.get("/leads")
def get_leads(
    page: int = 1,
    search: Optional[str] = "",
    persona: Optional[str] = "",
    validation_status: Optional[str] = "",
    city: Optional[str] = "",
    country: Optional[str] = "",
    per_page: int = 25
):
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    
    query = "SELECT * FROM leads_raw WHERE 1=1"
    params = []
    
    if search:
        query += " AND (first_name ILIKE %s OR last_name ILIKE %s OR email ILIKE %s OR company_name ILIKE %s OR raw_payload->>'current_title' ILIKE %s OR persona ILIKE %s OR phone ILIKE %s)"
        s = f"%{search}%"
        params.extend([s, s, s, s, s, s, s])

    if persona:
        query += " AND persona = %s"
        params.append(persona)
        
    if validation_status:
        query += " AND validation_status = %s"
        params.append(validation_status)
        
    # count total
    count_query = query.replace("SELECT *", "SELECT COUNT(*)")
    cur.execute(count_query, tuple(params))
    total = cur.fetchone()[0]
    
    query += " ORDER BY id DESC LIMIT %s OFFSET %s"
    params.extend([per_page, (page - 1) * per_page])
    
    cur.execute(query, tuple(params))
    rows = cur.fetchall()
    
    cur.close()
    conn.close()

    leads = []
    for r in rows:
        payload = r.get("raw_payload")
        if isinstance(payload, str):
            try:
                payload = json.loads(payload)
            except:
                payload = {}
        elif not payload:
            payload = {}

        city = r.get("city") or payload.get("city") or ""
        country = r.get("country") or payload.get("country") or ""

        # Robust phone extraction
        phone = r.get("phone")
        if not phone and payload and "phones" in payload:
            phones = payload.get("phones")
            if phones and isinstance(phones, list) and len(phones) > 0:
                phone = phones[0].get("number")
 
        leads.append({
            "id": r["id"],
            "name": f"{r['first_name'] or ''} {r['last_name'] or ''}".strip(),
            "first_name": r["first_name"],
            "last_name": r["last_name"],
            "email": r["email"],
            "phone": phone or r.get("phone") or "",
            "persona": r["persona"],
            "fit_score": r.get("fit_score", 0),
            "family_office_name": r.get("family_office_name", ""),
            "company_name": r["company_name"],
            "industry": r.get("industry", ""),
            "city": city,
            "country": country,
            "linkedin": r["linkedin_url"],
            "validation_status": r["validation_status"],
            "is_unsubscribed": r.get("is_unsubscribed", False),
            "created_at": r["created_at"].isoformat() if r["created_at"] else None
        })

    return {
        "leads": leads,
        "total": total
    }

@router.get("/leads/{lead_id}")
def get_lead_detail(lead_id: int):
    lead = get_lead_by_id(lead_id)
    if not lead:
        return {"error": "Lead not found"}
    
    # Enrich with payload if needed
    payload = lead.get("raw_payload")
    if isinstance(payload, str):
        try:
            payload = json.loads(payload)
        except:
            payload = {}
    elif not payload:
        payload = {}
        
    city = lead.get("city") or payload.get("city") or ""
    country = lead.get("country") or payload.get("country") or ""
    
    lead["city"] = city
    lead["country"] = country
    
    # Robust phone extraction fallback for details
    phone = lead.get("phone")
    if not phone and payload and "phones" in payload:
        phones = payload.get("phones")
        if phones and isinstance(phones, list) and len(phones) > 0:
            phone = phones[0].get("number")
    lead["phone"] = phone or payload.get("phone") or ""
    
    # ensure job title is included (designation)
    if payload:
        lead["designation"] = payload.get("current_title", "")
    
    return lead

@router.patch("/leads/{lead_id}")
def update_lead_endpoint(lead_id: int, req: LeadUpdate):
    update_data = req.dict(exclude_unset=True)
    if not update_data:
        return {"message": "No changes provided"}
    
    success = update_lead(lead_id, update_data)
    if success:
        add_activity_log(lead_id, "UPDATE_LEAD", f"Updated fields: {', '.join(update_data.keys())}", "admin")
        return {"message": "Lead updated successfully"}
    return {"error": "Failed to update lead"}

@router.get("/leads/{lead_id}/activity")
def get_lead_activity(lead_id: int):
    logs = get_activity_log(lead_id)
    return logs
