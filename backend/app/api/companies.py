from fastapi import APIRouter, HTTPException, Header
from app.database import get_db_connection
import psycopg2.extras
from typing import List, Optional, Dict, Any
import json

router = APIRouter()

def normalize_user_id(user_id: Optional[str]) -> str:
    if not user_id or user_id.strip() == "" or user_id.lower() == "admin":
        return "1"
    return user_id

@router.get("/companies")
def list_companies(user_id: Optional[str] = Header(None, alias="X-User-Id")):
    """Returns company profiles from the internal company registry database."""
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    
    try:
        # Fetch from the internal registry instead of external sheets
        cur.execute("SELECT id, row_data FROM company_registry ORDER BY id ASC")
        rows = cur.fetchall()
        
        companies = []
        for r in rows:
            data = r['row_data']
            if isinstance(data, str):
                data = json.loads(data)
            companies.append({ "id": r['id'], **data })

        return {
            "companies": companies,
            "total": len(companies)
        }
    except Exception as e:
        return { "companies": [], "error": str(e) }
    finally:
        cur.close()
        conn.close()

@router.post("/companies/import")
def import_companies(rows: List[Dict[str, Any]], user_id: Optional[str] = Header(None, alias="X-User-Id")):
    """Clears the current registry and imports a new batch of spreadsheet data."""
    uid = normalize_user_id(user_id)
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        # Clear existing data for a fresh import (or we could append, but clear is usually cleaner for 'Replace')
        cur.execute("DELETE FROM company_registry")
        
        # Batch Insert
        for row in rows:
            cur.execute(
                "INSERT INTO company_registry (row_data, user_id) VALUES (%s, %s)",
                (json.dumps(row), uid)
            )
        
        conn.commit()
        return {"success": True, "count": len(rows)}
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=f"Import failed: {str(e)}")
    finally:
        cur.close()
        conn.close()

@router.patch("/companies/{row_id}")
def update_company(row_id: int, row_data: Dict[str, Any], user_id: Optional[str] = Header(None, alias="X-User-Id")):
    """Updates a specific row in the company registry."""
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        cur.execute(
            "UPDATE company_registry SET row_data = %s, updated_at = NOW() WHERE id = %s",
            (json.dumps(row_data), row_id)
        )
        conn.commit()
        return {"success": True}
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        cur.close()
        conn.close()

@router.delete("/companies/clear")
def clear_companies():
    """Wipes the entire company registry."""
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("DELETE FROM company_registry")
        conn.commit()
        return {"success": True}
    finally:
        cur.close()
        conn.close()

@router.post("/companies/request-access")
def request_db_access(user_id: Optional[str] = Header(None, alias="X-User-Id")):
    """Submits access request (Legacy - keeping for route compatibility if needed)."""
    return {"message": "Access restriction removed. You have full system clearance."}
