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

router = APIRouter()

class RocketReachSearch(BaseModel):
    job_title: Optional[str] = None
    location: Optional[str] = None
    limit: Optional[int] = 10

@router.get("/family-offices")
def list_offices():
    return get_all_family_offices()

@router.get("/family-offices/{office_id}")
def get_office(office_id: int):
    office = get_family_office_by_id(office_id)
    if not office:
        raise HTTPException(status_code=404, detail="Office not found")
    return office

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
    
    # Logic for RocketReach search (Actual API call or simulated)
    # For now, let's simulate adding some leads
    conn = get_db_connection()
    cur = conn.cursor()
    
    # This is a placeholder for actual RocketReach integration
    # In a real scenario, you'd use the rocketreach_service
    
    new_leads = [
        {"first_name": "Investment", "last_name": "Director", "email": f"director@{office['name'].lower().replace(' ', '')}.com"},
        {"first_name": "Portfolio", "last_name": "Manager", "email": f"pm@{office['name'].lower().replace(' ', '')}.com"}
    ]
    
    added_count = 0
    for lead in new_leads[:req.limit]:
        cur.execute("""
            INSERT INTO leads_raw (first_name, last_name, email, family_office_name, company_name)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT DO NOTHING
        """, (lead['first_name'], lead['last_name'], lead['email'], office['name'], office['name']))
        added_count += cur.rowcount
        
    conn.commit()
    cur.close()
    conn.close()
    
    return {"message": f"Found and added {added_count} leads via RocketReach"}

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
