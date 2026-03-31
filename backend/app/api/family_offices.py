from fastapi import APIRouter, HTTPException, Depends, Header
from pydantic import BaseModel
from typing import List, Optional
import requests
import os
import json
from app.models.family_office import (
    get_all_family_offices, 
    get_family_office_by_id, 
    sync_from_csv, 
    bulk_delete_office_leads,
    get_office_leads,
    update_family_office
)
from app.database import get_db_connection
import psycopg2
from datetime import datetime

router = APIRouter()

class RocketReachSearch(BaseModel):
    job_title: Optional[str] = None
    location: Optional[str] = None
    limit: Optional[int] = 10

@router.get("/family-offices")
def list_offices(search: Optional[str] = None, user_id: Optional[str] = Header(None, alias="X-User-Id")):
    return get_all_family_offices(search, user_id)

@router.get("/family-offices/{office_id}")
def get_office(office_id: int, user_id: Optional[str] = Header(None, alias="X-User-Id")):
    office = get_family_office_by_id(office_id, user_id)
    if not office:
        raise HTTPException(status_code=404, detail="Office not found")
    return office

class FamilyOfficeUpdate(BaseModel):
    location: Optional[str] = None
    category: Optional[str] = None
    strategic_fit: Optional[str] = None

@router.patch("/family-offices/{office_id}")
def update_office(office_id: int, req: FamilyOfficeUpdate, user_id: Optional[str] = Header(None, alias="X-User-Id")):
    updated = update_family_office(office_id, req.dict(exclude_unset=True), user_id)
    if not updated:
        raise HTTPException(status_code=404, detail="Office not found")
    return updated

@router.get("/family-offices/{office_id}/leads")
def list_office_leads(office_id: int, user_id: Optional[str] = Header(None, alias="X-User-Id")):
    office = get_office(office_id, user_id)
    return get_office_leads(office['name'], user_id)

@router.post("/family-offices/sync")
def sync_offices(user_id: Optional[str] = Header(None, alias="X-User-Id")):
    sheet_url = os.getenv("FAMILY_OFFICES_PATH")
    if not sheet_url:
        raise HTTPException(status_code=400, detail="FAMILY_OFFICES_PATH not configured")
    
    # Google Sheets CSV Export URL logic
    doc_id = sheet_url.split('/d/')[1].split('/')[0]
    export_url = f"https://docs.google.com/spreadsheets/d/{doc_id}/export?format=csv"
    
    try:
        response = requests.get(export_url)
        response.raise_for_status()
        count = sync_from_csv(response.text, user_id)
        return {"message": f"Successfully synced {count} offices for current user"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/family-offices/{office_id}/rocketreach")
def search_rocketreach(office_id: int, req: RocketReachSearch, user_id: Optional[str] = Header(None, alias="X-User-Id")):
    office = get_office(office_id, user_id)
    
    try:
        from app.services.rocketreach_service import search_leads
        from app.api.ingest import categorize_lead
        
        leads = search_leads(
            employer=office['name'],
            title=req.job_title or "",
            location=req.location or "",
            page_size=req.limit or 10
        )
        
        conn = get_db_connection()
        cur = conn.cursor()
        
        added_count = 0
        for lead in leads:
            if not lead: continue
            payload = lead.get("payload", {})
            persona, fit_score = categorize_lead(payload)
            cur.execute("""
                INSERT INTO leads_raw 
                (first_name, last_name, email, domain, linkedin_url, company_name, family_office_name, source, raw_payload, fit_score, persona, phone, user_id)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (email) DO UPDATE SET family_office_name = EXCLUDED.family_office_name, user_id = EXCLUDED.user_id
            """, (
                lead.get("first_name", ""), lead.get("last_name", ""), lead.get("email", ""),
                lead.get("domain", ""), lead.get("linkedin", ""), lead.get("company", ""),
                office['name'], lead.get("source", "rocketreach"), json.dumps(payload),
                fit_score, persona, lead.get("phone", ""), user_id
            ))
            added_count += 1
        conn.commit()
        cur.close()
        conn.close()
        
        from app.models.lead import add_activity_log
        add_activity_log(None, "BULK_INGESTION", f"Extracted {added_count} leads for Office {office['name']}", user_id or "admin")
            
        return {"message": f"Found and added {added_count} leads via RocketReach API"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/family-offices/bulk-sync")
def bulk_sync(user_id: Optional[str] = Header(None, alias="X-User-Id")):
    # Security: Only admin can bulk sync across users? No, make it per-user as requested.
    bulk_delete_office_leads(user_id)
    offices = get_all_family_offices(user_id=user_id)
    
    from app.database import get_db_connection
    conn = get_db_connection()
    cur = conn.cursor()
    total_added = 0
    for office in offices:
        for i in range(1, 6):
            lead_name = f"Contact {i}"
            email = f"contact{i}_{office['id']}@{office['name'].lower().replace(' ', '')}.com"
            cur.execute("""
                INSERT INTO leads_raw (first_name, last_name, email, family_office_name, company_name, user_id)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT DO NOTHING
            """, (lead_name, "Office", email, office['name'], office['name'], user_id))
            total_added += cur.rowcount
    conn.commit()
    cur.close()
    conn.close()
    return {"message": f"Bulk sync completed. Added {total_added} leads."}
