from fastapi import APIRouter, HTTPException, Depends, Header
from app.database import get_db_connection
import psycopg2.extras
from typing import List, Optional
import os

router = APIRouter()

def normalize_user_id(user_id: Optional[str]) -> str:
    if not user_id or user_id.strip() == "" or user_id.lower() == "admin":
        return "1"
    return user_id

@router.get("/companies")
def list_companies(user_id: Optional[str] = Header(None, alias="X-User-Id")):
    """Returns company profiles fetched directly from a static Google Sheets Drive link."""
    uid = normalize_user_id(user_id)
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    
    try:
        # Check access
        cur.execute("SELECT role, has_db_access FROM users WHERE id = %s", (uid,))
        user = cur.fetchone()
        
        if not user:
            raise HTTPException(status_code=401, detail="User not found")
        
        if user['role'] != 'ADMIN' and not user['has_db_access']:
            return {
                "access_denied": True,
                "message": "Company database access requires administrative approval.",
                "companies": []
            }
            
        # Fetch from Sheets
        import requests as req_lib
        import csv
        import io

        sheet_url = os.getenv("COMPANY_DATABASE_PATH")
        if not sheet_url or "your_google_sheets" in sheet_url:
             return {
                "access_denied": False,
                "companies": [],
                "error": "Company database source is not configured by admin."
            }

        try:
            # Automatic URL transformation for Google Sheets
            if "/d/" in sheet_url:
                doc_id = sheet_url.split('/d/')[1].split('/')[0]
                export_url = f"https://docs.google.com/spreadsheets/d/{doc_id}/export?format=csv"
            else:
                export_url = sheet_url

            response = req_lib.get(export_url, timeout=10)
            if not response.ok:
                raise Exception(f"Failed to fetch sheet: {response.status_code}")
            
            # Parse CSV
            f = io.StringIO(response.text)
            reader = csv.DictReader(f)
            companies = [row for row in reader]

            return {
                "access_denied": False,
                "companies": companies,
                "total": len(companies)
            }
        except Exception as e:
            return {
                "access_denied": False,
                "companies": [],
                "error": f"Drive Link Error: {str(e)}"
            }

    finally:
        cur.close()
        conn.close()

@router.post("/companies/request-access")
def request_db_access(user_id: Optional[str] = Header(None, alias="X-User-Id")):
    """Submits a request to the admin for database access pulse."""
    uid = normalize_user_id(user_id)
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        # In a real app, this might create a request record. 
        # For now, we'll just log it in activity_log for the admin to see.
        cur.execute("""
            INSERT INTO activity_log (user_id, action, details)
            VALUES (%s, 'DB_ACCESS_REQUEST', 'User requested access to the global company database.')
        """, (uid,))
        conn.commit()
        return {"message": "Access request submitted to system administrators."}
    finally:
        cur.close()
        conn.close()
