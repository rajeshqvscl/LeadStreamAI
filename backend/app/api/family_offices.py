from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import List, Optional
import requests
import os
from app.models.family_office import (
    get_all_family_offices, 
    get_family_office_by_id, 
    sync_from_csv, 
    bulk_delete_office_leads,
    get_office_leads
)
from app.database import get_db_connection
import psycopg2
from datetime import datetime
import json

router = APIRouter()

class RocketReachSearch(BaseModel):
    job_title: Optional[str] = None
    location: Optional[str] = None
    limit: Optional[int] = 10

@router.get("/family-offices")
def list_offices(search: Optional[str] = None):
    return get_all_family_offices(search)

@router.get("/family-offices/{office_id}")
def get_office(office_id: int):
    office = get_family_office_by_id(office_id)
    if not office:
        raise HTTPException(status_code=404, detail="Office not found")
    return office

class FamilyOfficeUpdate(BaseModel):
    location: Optional[str] = None
    category: Optional[str] = None
    strategic_fit: Optional[str] = None

@router.patch("/family-offices/{office_id}")
def update_office(office_id: int, req: FamilyOfficeUpdate):
    from app.models.family_office import update_family_office
    updated = update_family_office(office_id, req.dict(exclude_unset=True))
    if not updated:
        raise HTTPException(status_code=404, detail="Office not found or no changes made")
    return updated

@router.get("/family-offices/{office_id}/leads")
def list_office_leads(office_id: int):
    office = get_family_office_by_id(office_id)
    if not office:
        raise HTTPException(status_code=404, detail="Office not found")
    return get_office_leads(office['name'])

@router.post("/family-offices/sync")
def sync_offices():
    sheet_url = os.getenv("FAMILY_OFFICES_PATH")
    if not sheet_url:
        raise HTTPException(status_code=400, detail="FAMILY_OFFICES_PATH not configured")
    
    # Convert Google Sheet URL to export URL
    if "/edit" in sheet_url:
        export_url = sheet_url.split("/edit")[0] + "/export?format=csv"
        if "gid=" in sheet_url:
            gid = sheet_url.split("gid=")[1].split("#")[0]
            export_url += f"&gid={gid}"
    else:
        export_url = sheet_url

    try:
        response = requests.get(export_url)
        response.raise_for_status()
        count = sync_from_csv(response.text)
        return {"message": f"Successfully synced {count} offices"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/family-offices/{office_id}/rocketreach")
def search_rocketreach(office_id: int, req: RocketReachSearch):
    office = get_family_office_by_id(office_id)
    if not office:
        raise HTTPException(status_code=404, detail="Office not found")
    
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
            if not lead:
                continue
                
            persona, fit_score = categorize_lead(lead.get("payload", {}))
            
            cur.execute("""
                INSERT INTO leads_raw 
                (first_name, last_name, email, domain, linkedin_url, company_name, family_office_name, source, raw_payload, fit_score, persona, phone)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (email) DO UPDATE SET family_office_name = EXCLUDED.family_office_name
            """, (
                lead.get("first_name", ""),
                lead.get("last_name", ""),
                lead.get("email", ""),
                lead.get("domain", ""),
                lead.get("linkedin", ""),
                lead.get("company", ""),
                office['name'],
                lead.get("source", "rocketreach"),
                json.dumps(lead.get("payload", {})),
                fit_score,
                persona,
                lead.get("phone", "")
            ))
            
            added_count += 1
            
        conn.commit()
        cur.close()
        conn.close()
        
        try:
            from app.models.lead import add_activity_log
            add_activity_log(None, "BULK_INGESTION", f"Extracted {added_count} leads for Family Office {office['name']}", "admin")
        except:
            pass
            
        return {"message": f"Found and added {added_count} leads via RocketReach API"}
        
    except Exception as e:
        print(f"Extraction error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/family-offices/bulk-sync")
def bulk_sync():
    # 1. Delete all existing leads associated with family offices
    bulk_delete_office_leads()
    
    # 2. Get all offices
    offices = get_all_family_offices()
    
    # 3. Search 5 fresh leads per office (simulated)
    conn = get_db_connection()
    cur = conn.cursor()
    
    total_added = 0
    for office in offices:
        # Simulate finding 5 leads
        for i in range(1, 6):
            lead_name = f"Contact {i}"
            email = f"contact{i}@{office['name'].lower().replace(' ', '')}.com"
            cur.execute("""
                INSERT INTO leads_raw (first_name, last_name, email, family_office_name, company_name)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT DO NOTHING
            """, (lead_name, "Office", email, office['name'], office['name']))
            total_added += cur.rowcount
            
    conn.commit()
    cur.close()
    conn.close()
    
    return {"message": f"Bulk sync completed. Added {total_added} leads across {len(offices)} offices."}
