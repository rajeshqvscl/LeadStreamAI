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
                    if key == "generated":
                        # Handle BOOLEAN filter for _is_generated
                        if str(value).lower() == "true":
                            base_where += " AND _is_generated = TRUE"
                        elif str(value).lower() == "false":
                            base_where += " AND _is_generated = FALSE"
                    else:
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
            SELECT id, row_data, _is_generated 
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
            companies.append({ "id": r['id'], "_is_generated": r["_is_generated"], **data })

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
def generate_company_draft(row_id: int, template_name: Optional[str] = None, user_id: Optional[str] = Header(None, alias="X-User-Id")):
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
            
        # Normalize keys for mapping
        norm = {str(k).lower().replace(" ", "").replace("-", "").replace("_", ""): v for k, v in data.items() if v}
        
        email = norm.get("email") or norm.get("emailaddress") or norm.get("workemail")
        if not email:
            raise HTTPException(status_code=400, detail="Company record is missing an email address.")
            
        name = (
            norm.get("teammember") or norm.get("name") or norm.get("fullname") or 
            norm.get("leadname") or norm.get("contactname") or norm.get("contact") or
            norm.get("investor") or norm.get("person") or
            f"{norm.get('firstname', '')} {norm.get('lastname', '')}".strip()
        )
        if not name or name.strip() == "":
            email_prefix = email.split('@')[0]
            name = email_prefix.replace(".", " ").replace("_", " ").replace("-", " ").title()
            
        company = norm.get("companyname") or norm.get("company") or norm.get("investorname") or norm.get("org") or norm.get("firm") or norm.get("account")
        
        parts = name.split(" ", 1)
        f_name = parts[0]
        l_name = parts[1] if len(parts) > 1 else ""
        
        sender_name = "the team"
        if uid:
            cur.execute("SELECT full_name, username FROM users WHERE id = %s", (uid,))
            u = cur.fetchone()
            if u: sender_name = u['full_name'] or u['username']
            
        insert_lead(f_name, l_name, email, "", norm.get("linkedin", ""), company, "intelligence", data, user_id=uid, user_name=sender_name)

        cur.execute("SELECT id FROM leads_raw WHERE email = %s AND user_id = %s ORDER BY created_at DESC LIMIT 1", (email, uid))
        lead_row = cur.fetchone()
        lead_id = lead_row[0]
        
        # --- NEW: Reuse universal generator logic ---
        from app.api.drafts import generate_email_internal, DraftRequest
        req = DraftRequest(lead_id=lead_id, template_type=template_name or 'standard')
        res = generate_email_internal(req, user_id)
        
        subject = res.get("subject")
        body = res.get("body")
        gmail_draft_id = res.get("gmail_draft_id")
        email_content = f"Subject: {subject}\n\n{body}"

        # Mark as generated in company registry
        cur.execute("UPDATE company_registry SET _is_generated = TRUE, updated_at = NOW() WHERE id = %s AND user_id = %s", (row_id, uid))
        conn.commit()

        return {"success": True, "lead_id": lead_id, "message": "Draft generated and moved to Lead Pipeline."}
        
        # --- Step 1: Create Gmail Draft FIRST (so we have the ID) ---
        gmail_draft_id = None
        try:
            from app.services.google_service import get_gmail_service
            import base64
            from email.mime.text import MIMEText
            
            service = get_gmail_service(int(uid))
            if service:
                # Render body as plain text (converts \n to \r\n for MIME)
                message = MIMEText(body, 'plain')
                message['to'] = email
                message['subject'] = subject
                raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode('utf-8')
                
                # Create Gmail Draft
                draft_body = {'message': {'raw': raw_message}}
                created_draft = service.users().drafts().create(userId='me', body=draft_body).execute()
                gmail_draft_id = created_draft.get('id')
                print(f"✅ Created Gmail draft {gmail_draft_id} for Lead {lead_id} (from Registry)")
        except Exception as ge:
            print(f"⚠️  Gmail draft sync failed for Registry lead (non-blocking): {ge}")

        # --- Step 2: Save to DB with gmail_draft_id ---
        cur.execute("""
            UPDATE leads_raw 
            SET email_draft = %s, 
                email_status = 'PENDING_APPROVAL', 
                updated_at = NOW(), 
                gmail_draft_id = %s
            WHERE id = %s
        """, (email_content, gmail_draft_id, lead_id))

        # Mark as generated in company registry - it's now in the lead pipeline
        cur.execute("UPDATE company_registry SET _is_generated = TRUE, updated_at = NOW() WHERE id = %s AND user_id = %s", (row_id, uid))
        conn.commit()

        # Log activity
        try:
            from app.models.lead import add_activity_log
            add_activity_log(lead_id, "DRAFT_GENERATED", f"Draft generated from Intelligence Grid {'(Gmail synced ✅)' if gmail_draft_id else ''}", sender_name)
        except:
            pass
        
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
