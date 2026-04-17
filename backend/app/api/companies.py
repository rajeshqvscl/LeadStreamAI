from fastapi import APIRouter, HTTPException, Header
from app.database import get_db_connection
import psycopg2.extras
from typing import List, Optional, Dict, Any
import json
import requests
import csv
import io
import re
from app.models.lead import insert_lead, save_email_draft
from app.services.llm_services import EmailGenerator
from psycopg2.extras import execute_values
import time

router = APIRouter()

def normalize_user_id(user_id: Optional[str]) -> str:
    if not user_id or user_id.strip() == "":
        return None
    return user_id

@router.get("/companies")
def list_companies(
    page: int = 1, 
    limit: int = 500, 
    search: Optional[str] = None,
    filters: Optional[str] = None, # JSON string of key-value filters
    user_id: Optional[str] = Header(None, alias="X-User-Id")
):
    """Returns company profiles from the internal company registry database with pagination and global search."""
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    offset = (page - 1) * limit
    
    uid = normalize_user_id(user_id)
    is_admin = (str(user_id or '').lower() == 'admin')
    
    # Base query construction
    base_where = ""
    params = []
    
    if is_admin:
        base_where = "WHERE 1=1"
    elif uid:
        base_where = "WHERE user_id = %s"
        params.append(uid)
    else:
        base_where = "WHERE user_id IS NULL"
        
    # Apply Global Search
    if search:
        search_term = f"%{search}%"
        base_where += " AND (row_data::text ILIKE %s)"
        params.append(search_term)
        
    # Apply Column Filters
    if filters:
        try:
            filter_map = json.loads(filters)
            for key, value in filter_map.items():
                if value:
                    base_where += f" AND (row_data->>'{key}' ILIKE %s)"
                    params.append(f"%{value}%")
        except:
            pass # Ignore malformed filters

    try:
        # Total count with filters
        count_query = f"SELECT COUNT(*) FROM company_registry {base_where}"
        cur.execute(count_query, params)
        total = cur.fetchone()[0]
        
        # Fetch with pagination
        fetch_params = params + [limit, offset]
        fetch_query = f"""
            SELECT id, row_data 
            FROM company_registry 
            {base_where} 
            ORDER BY id ASC 
            LIMIT %s OFFSET %s
        """
        cur.execute(fetch_query, fetch_params)
        rows = cur.fetchall()
        
        companies = []
        for r in rows:
            data = r['row_data']
            if isinstance(data, str):
                data = json.loads(data)
            companies.append({ "id": r['id'], **data })

        return {
            "companies": companies,
            "total": total,
            "page": page,
            "limit": limit,
            "pages": (total + limit - 1) // limit
        }
    except Exception as e:
        import traceback
        print(traceback.format_exc())
        return { "companies": [], "error": str(e), "total": 0 }
    finally:
        cur.close()
        conn.close()

@router.post("/companies/import")
def import_companies(rows: List[Dict[str, Any]], user_id: Optional[str] = Header(None, alias="X-User-Id")):
    """Clears the current registry and imports a new batch of spreadsheet data using fast batch insertion."""
    uid = normalize_user_id(user_id)
    conn = get_db_connection()
    cur = conn.cursor()
    
    start_time = time.time()
    try:
        # Clear existing data for a fresh import
        cur.execute("DELETE FROM company_registry WHERE user_id = %s", (uid,))
        
        # Fast Batch Insert
        if rows:
            data_to_insert = [(json.dumps(row), uid) for row in rows]
            execute_values(
                cur,
                "INSERT INTO company_registry (row_data, user_id) VALUES %s",
                data_to_insert
            )
        
        conn.commit()
        end_time = time.time()
        print(f"Imported {len(rows)} companies in {end_time - start_time:.2f} seconds.")
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
    uid = normalize_user_id(user_id)
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        cur.execute(
            "UPDATE company_registry SET row_data = %s, updated_at = NOW() WHERE id = %s AND user_id = %s",
            (json.dumps(row_data), row_id, uid)
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
def clear_companies(user_id: Optional[str] = Header(None, alias="X-User-Id")):
    """Wipes the entire company registry."""
    uid = normalize_user_id(user_id)
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("DELETE FROM company_registry WHERE user_id = %s", (uid,))
        conn.commit()
        return {"success": True}
    finally:
        cur.close()
        conn.close()

@router.post("/companies/request-access")
def request_db_access(user_id: Optional[str] = Header(None, alias="X-User-Id")):
    """Submits access request (Legacy - keeping for route compatibility if needed)."""
    return {"message": "Access restriction removed. You have full system clearance."}

@router.post("/companies/import-gsheet")
def import_companies_gsheet(req: Dict[str, str], user_id: Optional[str] = Header(None, alias="X-User-Id")):
    """Syncs a public Google Sheet into the company registry."""
    url = req.get("url")
    if not url:
        raise HTTPException(status_code=400, detail="URL is required")
    
    raw_url = url.strip()
    if "/d/" not in raw_url:
        raise HTTPException(status_code=400, detail="Invalid Google Sheet URL format.")
    
    doc_id = raw_url.split("/d/")[1].split("/")[0]
    gid_match = re.search(r"[?&#]gid=(\d+)", raw_url)
    gid = gid_match.group(1) if gid_match else "0"
    
    export_url = f"https://docs.google.com/spreadsheets/d/{doc_id}/export?format=csv&gid={gid}"
    
    try:
        print(f"Fetching GSheet export from: {export_url}")
        resp = requests.get(export_url, allow_redirects=True, timeout=60)
        if resp.status_code != 200:
            raise HTTPException(status_code=400, detail="Sheet is private or not found.")
        
        reader = csv.DictReader(io.StringIO(resp.text))
        rows = [dict(row) for row in reader]
        print(f"Parsed {len(rows)} rows from GSheet.")
        
        # Reuse existing import logic
        return import_companies(rows, user_id)
    except Exception as e:
        print(f"GSheet import error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/companies/{row_id}/generate-draft")
def generate_company_draft(row_id: int, user_id: Optional[str] = Header(None, alias="X-User-Id")):
    """Converts a company registry record to a lead and generates an email draft."""
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    
    uid = normalize_user_id(user_id)
    
    try:
        cur.execute("SELECT row_data FROM company_registry WHERE id = %s AND user_id = %s", (row_id, uid))
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Company record not found")
            
        data = row['row_data']
        if isinstance(data, str):
            data = json.loads(data)
            
        # Normalize keys for mapping (remove spaces, underscores, and dashes)
        norm = {str(k).lower().replace(" ", "").replace("-", "").replace("_", ""): v for k, v in data.items() if v}
        
        email = norm.get("email") or norm.get("emailaddress") or norm.get("workemail")
        if not email:
            raise HTTPException(status_code=400, detail="Company record is missing an email address.")
            
        # Robust Name Extraction: Order matters - specific first
        name = (
            norm.get("teammember") or 
            norm.get("name") or 
            norm.get("fullname") or 
            norm.get("leadname") or 
            norm.get("contactname") or
            norm.get("contact") or
            norm.get("investor") or
            norm.get("person") or
            f"{norm.get('firstname', '')} {norm.get('lastname', '')}".strip()
        )
        
        # If still no name, try to extract it from the email prefix
        if not name or name.strip() == "":
            email_prefix = email.split('@')[0]
            # Handle formats like "john.doe" or "j.doe" or "john_doe"
            name_guess = email_prefix.replace(".", " ").replace("_", " ").replace("-", " ").title()
            name = name_guess if name_guess else "Contact"
            
        company = (
            norm.get("companyname") or 
            norm.get("company") or 
            norm.get("investorname") or
            norm.get("org") or
            norm.get("firm") or
            norm.get("account")
        )
        
        # Split name for lead insertion
        parts = name.split(" ", 1)
        f_name = parts[0]
        l_name = parts[1] if len(parts) > 1 else ""
        
        # Add the lead to the main pipeline (source: intelligence)
        sender_name = "the team"
        if uid:
            cur.execute("SELECT full_name, username FROM users WHERE id = %s", (uid,))
            u = cur.fetchone()
            if u: sender_name = u['full_name'] or u['username']
            
        insert_lead(
            f_name, l_name, email, "", norm.get("linkedin", ""), 
            company, "intelligence", data, user_id=uid, user_name=sender_name
        )

        # Get the new/updated lead ID - filter by UID for strict isolation
        cur.execute("SELECT id FROM leads_raw WHERE email = %s AND user_id = %s ORDER BY created_at DESC LIMIT 1", (email, uid))
        lead_row = cur.fetchone()
        if not lead_row:
            # Fallback for cases where UID might be NULL
            cur.execute("SELECT id FROM leads_raw WHERE email = %s ORDER BY created_at DESC LIMIT 1", (email,))
            lead_row = cur.fetchone()
            
        if not lead_row:
            raise HTTPException(status_code=500, detail="Lead creation failed — could not retrieve lead ID.")
        lead_id = lead_row[0]
        
        # Generate Draft
        generator = EmailGenerator()
        email_data = generator.generate_email({"first_name": f_name, "last_name": l_name, "company_name": company}, sender_name=sender_name)
        subject = email_data.get("subject", "Following up")
        body = email_data.get("body", "Hello, we would love to connect.")
        email_content = f"Subject: {subject}\n\n{body}"
        
        save_email_draft(lead_id, email_content)

        # Remove from company registry - it's now in the lead pipeline
        cur.execute("DELETE FROM company_registry WHERE id = %s AND user_id = %s", (row_id, uid))
        conn.commit()
        
        return {"success": True, "lead_id": lead_id, "message": "Draft generated and moved to Lead Pipeline."}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        cur.close()
        conn.close()

@router.post("/companies/{row_id}/send")
def send_company_email(row_id: int, user_id: Optional[str] = Header(None, alias="X-User-Id")):
    """Generates and actually dispatches an email for a company record."""
    from app.services.email_service import send_email
    
    # 1. Generate the draft and lead record
    res = generate_company_draft(row_id, user_id)
    lead_id = res["lead_id"]
    
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    try:
        # 2. Fetch the Lead and Draft for sending
        cur.execute("SELECT email, email_draft FROM leads_raw WHERE id = %s", (lead_id,))
        lead = cur.fetchone()
        
        # 3. Fetch Sender Identity
        sender_email = None
        sender_name = "the team"
        if user_id:
            cur.execute("SELECT email, full_name, username FROM users WHERE id = %s", (normalize_user_id(user_id),))
            u = cur.fetchone()
            if u:
                sender_email = u['email']
                sender_name = u['full_name'] or u['username']

        # 4. Parse Draft
        draft_content = lead['email_draft'] or ""
        subject = "Following up"
        body = draft_content
        if "Subject: " in draft_content:
            parts = draft_content.split("\n\n", 1)
            subject = parts[0].replace("Subject: ", "").strip()
            body = parts[1].strip() if len(parts) > 1 else ""

        # 5. Real Dispatch
        success = send_email(
            to_email=lead['email'],
            subject=subject,
            html_content=body.replace("\n", "<br>"),
            from_email=sender_email,
            from_name=sender_name
        )
        
        if success:
            cur.execute("UPDATE leads_raw SET email_status = 'SENT', updated_at = NOW() WHERE id = %s", (lead_id,))
            conn.commit()
            return {"success": True, "message": f"Email dispatched via Resend to {lead['email']}"}
        else:
            raise HTTPException(status_code=500, detail="Dispatch failed. Check Resend configuration.")

    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        cur.close()
        conn.close()
