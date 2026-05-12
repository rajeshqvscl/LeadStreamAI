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
    """Imports a batch of data, automatically enriching missing fields."""
    uid = normalize_user_id(user_id)
    conn = get_db_connection()
    cur = conn.cursor()
    
    # --- AUTOMATION: Enrich rows before insertion ---
    processed_rows = process_and_enrich_rows(rows)
    
    conn = None
    cur = None
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        
        # Fetch existing lead emails for this user to preserve "Generated" status
        cur.execute("SELECT email FROM leads_raw WHERE user_id = %s", (uid,))
        existing_emails = {r[0].lower() for r in cur.fetchall() if r[0]}
        print(f"DEBUG: Found {len(existing_emails)} existing leads for user {uid}")

        cur.execute("DELETE FROM company_registry WHERE user_id = %s", (uid,))
        if processed_rows:
            data_to_insert = []
            match_count = 0
            for row in processed_rows:
                # Robust email detection across all fields (case-insensitive)
                row_email = None
                for val in row.values():
                    if isinstance(val, str) and '@' in val and '.' in val:
                        row_email = val.strip().lower()
                        break
                
                is_generated = row_email in existing_emails if row_email else False
                if is_generated: match_count += 1
                data_to_insert.append((json.dumps(row), uid, is_generated))
            
            print(f"DEBUG: Marked {match_count} as Generated out of {len(processed_rows)} rows")
                
            execute_values(
                cur,
                "INSERT INTO company_registry (row_data, user_id, _is_generated) VALUES %s",
                data_to_insert
            )
        conn.commit()
        return {"success": True, "count": len(processed_rows)}
    except Exception as e:
        if conn: conn.rollback()
        print(f"ERROR: Import failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Import failed: {str(e)}")
    finally:
        if cur: cur.close()
        if conn: conn.close()

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

def process_and_enrich_rows(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Cleans and auto-enriches a list of rows, ensuring critical columns exist and are named correctly."""
    results = []
    
    # First pass: Identify types of unnamed columns by scanning values in ALL rows
    unnamed_types = {} 
    
    for row in rows:
        for idx, (k, v) in enumerate(row.items()):
            k_str = str(k).strip()
            # If header is missing, empty, or generic
            if not k or k_str == "" or k_str.lower() in ["none", "null", "field_"]:
                s_val = str(v).strip().lower()
                if "@" in s_val and "." in s_val and len(s_val) > 5 and idx not in unnamed_types:
                    unnamed_types[idx] = "Email"
                elif any(c.isdigit() for c in s_val) and len(s_val) > 7 and idx not in unnamed_types:
                    unnamed_types[idx] = "Mobile"

    for i, row in enumerate(rows):
        clean_row = {}
        # Ensure these core keys ALWAYS exist in the result object
        clean_row["Email"] = ""
        clean_row["Mobile"] = ""
        
        for idx, (k, v) in enumerate(row.items()):
            k_str = str(k).strip()
            target_key = k_str
            
            # Use detected name if original is missing/generic
            if not k or k_str == "" or k_str.lower() in ["none", "null"] or "field" in k_str.lower():
                target_key = unnamed_types.get(idx, f"Field_{idx}")
            
            val = str(v).strip() if v else ""
            
            # Map common variations to standard keys
            tk_low = target_key.lower().replace(" ", "").replace("_", "")
            if tk_low in ["email", "emailaddress", "workemail", "mail"]:
                clean_row["Email"] = val
            elif tk_low in ["mobile", "phone", "contact", "contactnumber", "phonenumber", "tel"]:
                clean_row["Mobile"] = val
            else:
                # Keep original key but avoid empty ones
                final_key = target_key if target_key else f"Column_{idx}"
                clean_row[final_key] = val
        
        # Double check: if Email/Mobile are still empty but we found them in unnamed columns
        # this acts as a safety net
        if not clean_row["Email"]:
            for k, v in clean_row.items():
                if "@" in str(v) and "." in str(v) and k not in ["Company Name", "Person Name"]:
                    clean_row["Email"] = str(v)
                    break
        
        if not any(v for k, v in clean_row.items() if k not in ["id", "_is_generated", "Email", "Mobile"]): 
            continue
        
        # Trigger AI enrichment for missing critical data (Limit to first 30)
        has_email = "@" in clean_row.get("Email", "")
        has_phone = any(c.isdigit() for c in clean_row.get("Mobile", "")) and len(clean_row.get("Mobile", "")) > 7
            
        if (not has_email or not has_phone) and i < 30:
            try:
                enriched = enrich_row_data_internal(clean_row)
                # Update but don't overwrite if we already have it
                for ek, ev in enriched.items():
                    # Map AI keys to our standard keys
                    if ek == "email" and not clean_row["Email"]: clean_row["Email"] = ev
                    elif ek == "phone" and not clean_row["Mobile"]: clean_row["Mobile"] = ev
                    elif ek == "linkedin_url" and not clean_row.get("LinkedIn Profile"): clean_row["LinkedIn Profile"] = ev
                    elif ek == "designation" and not clean_row.get("Designation"): clean_row["Designation"] = ev
                    elif ek == "industry" and not clean_row.get("Industry"): clean_row["Industry"] = ev
            except:
                pass
        
        results.append(clean_row)
    return results

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
        
        # CLEANUP: Remove leading empty lines or garbage before the actual headers
        lines = resp.text.splitlines()
        header_index = 0
        
        # Key headers we expect to find in a valid sheet
        keywords = ['email', 'name', 'company', 'linkedin', 'person', 'investor', 'contact', 'designation', 'note', 'sector']
        
        for i, line in enumerate(lines):
            # Count how many of our keywords are in this line
            lower_line = line.lower()
            matches = sum(1 for kw in keywords if kw in lower_line)
            
            # If a line has at least 2 matching keywords, it's likely our header row
            if matches >= 2:
                header_index = i
                break
            
            # Fallback: if it's the first line with any significant content
            if line.strip() and not line.strip().startswith(",,,") and header_index == 0:
                header_index = i
        
        cleaned_csv = "\n".join(lines[header_index:])
        reader = csv.reader(io.StringIO(cleaned_csv))
        
        # Extract headers and handle rows
        header_row = next(reader, [])
        rows = []
        for row_data in reader:
            # Create a dict with numeric indices as keys to be safe
            row_dict = {}
            for idx, val in enumerate(row_data):
                key = header_row[idx] if idx < len(header_row) and header_row[idx].strip() else f"Field_{idx}"
                row_dict[key] = val
            rows.append(row_dict)
        
        # This will call the enriched import_companies
        return import_companies(rows, user_id)
    except Exception as e:
        print(f"GSheet import error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

def enrich_row_data_internal(data: Dict[str, Any]) -> Dict[str, Any]:
    """Helper to enrich a single row's data using AI."""
    try:
        company_name = data.get("Company Name") or data.get("company") or data.get("Company") or data.get("name")
        if not company_name: return data
        
        prompt = f"""
        Find professional contact details for: "{company_name}".
        Person: "{data.get('Person Name') or data.get('person') or ''}"
        Return ONLY valid JSON: {{"domain":"", "linkedin_url":"", "email":"", "designation":"", "industry":"", "phone":""}}
        """
        from app.services.llm_services import LLMService
        llm = LLMService()
        ai_response = llm.generate_response(prompt)
        
        json_str = ai_response.strip()
        if "```json" in json_str: json_str = json_str.split("```json")[1].split("```")[0].strip()
        elif "```" in json_str: json_str = json_str.split("```")[1].split("```")[0].strip()
        
        enrichment = json.loads(json_str)
        field_map = {
            "email": ["Email", "Email Address", "Work Email"],
            "linkedin_url": ["LinkedIn Profile", "LinkedIn", "LinkedIn URL"],
            "designation": ["Designation", "Role", "Job Title", "Title"],
            "domain": ["Domain", "Website"],
            "industry": ["Industry", "Sector"],
            "phone": ["Mobile", "Phone", "Contact Number", "Phone Number"]
        }
        
        for ai_key, ui_candidates in field_map.items():
            ai_val = enrichment.get(ai_key)
            if not ai_val: continue
            
            # Check for existing value
            exists = False
            target_key = ui_candidates[0]
            for cand in ui_candidates:
                for k in data.keys():
                    if k.lower().replace(" ","") == cand.lower().replace(" ",""):
                        if data.get(k): exists = True
                        target_key = k
                        break
            if not exists: data[target_key] = ai_val
            
        return data
    except:
        return data

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
        
        # 1. Smart Email Detection
        email = (
            norm.get("email") or norm.get("emailaddress") or 
            norm.get("workemail") or norm.get("primaryemail")
        )
        
        # Fallback: scan all values for @ if no explicit email header
        if not email:
            for k, v in data.items():
                val = str(v).strip()
                if "@" in val and "." in val and len(val) > 5 and " " not in val:
                    email = val
                    break
                    
        if not email:
            raise HTTPException(status_code=400, detail="Profile is missing a valid email address. Use 'Fetch Details' (Globe Icon) to find it first.")
            
        # 2. Smart Name Detection
        name = (
            norm.get("teammember") or norm.get("name") or norm.get("fullname") or 
            norm.get("leadname") or norm.get("contactname") or norm.get("contact") or
            norm.get("investor") or norm.get("person") or norm.get("personname") or
            f"{norm.get('firstname', '')} {norm.get('lastname', '')}".strip()
        )
        
        if not name or name.strip() == "":
            # Try to guess from email prefix
            email_prefix = email.split('@')[0]
            name = email_prefix.replace(".", " ").replace("_", " ").replace("-", " ").title()
            
        # 3. Smart Company Detection
        company = (
            norm.get("companyname") or norm.get("company") or 
            norm.get("investorname") or norm.get("org") or 
            norm.get("firm") or norm.get("account") or norm.get("organization")
        )
        if not company:
            company = "—"
        
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
        if not lead_row:
             raise HTTPException(status_code=500, detail="Lead synchronization fault: Record failed to propagate to pipeline.")
        
        lead_id = lead_row['id'] if isinstance(lead_row, dict) else lead_row[0]
        
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

@router.post("/companies/{row_id}/enrich")
def enrich_company_data(row_id: int, user_id: Optional[str] = Header(None, alias="X-User-Id")):
    """Uses AI to fetch missing details (LinkedIn, Domain, etc.) for a company record."""
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
            
        # Get company name
        company_name = data.get("Company Name") or data.get("company") or data.get("Company") or data.get("name")
        if not company_name:
             raise HTTPException(status_code=400, detail="No company name found to search for.")

        # Use AI to find LinkedIn/Domain/etc.
        prompt = f"""
        Find the following professional contact details for the company: "{company_name}".
        Target Person: "{data.get('Person Name') or data.get('person') or ''}"
        
        Required Details (JSON format):
        - domain: (e.g. apple.com)
        - linkedin_url: (official LinkedIn profile URL for the company or person)
        - email: (likely professional email address)
        - designation: (the person's role in the company)
        - industry: (e.g. Healthcare, Technology, Finance)
        
        Return ONLY valid JSON.
        """
        
        from app.services.llm_services import LLMService
        llm = LLMService()
        ai_response = llm.generate_response(prompt)
        
        # Parse AI response
        try:
            json_str = ai_response.strip()
            if "```json" in json_str:
                json_str = json_str.split("```json")[1].split("```")[0].strip()
            elif "```" in json_str:
                json_str = json_str.split("```")[1].split("```")[0].strip()
            
            enrichment = json.loads(json_str)
            
            # Update data with enriched fields using case-insensitive fuzzy matching
            updated = False
            
            # Helper to find existing key in data (case-insensitive)
            def find_key(search_key):
                search_key_norm = search_key.lower().replace(" ", "").replace("_", "")
                for k in data.keys():
                    if k.lower().replace(" ", "").replace("_", "") == search_key_norm:
                        return k
                return None

            # Mapping of AI keys to likely UI keys
            field_map = {
                "email": ["Email", "Email Address", "Work Email"],
                "linkedin_url": ["LinkedIn Profile", "LinkedIn", "LinkedIn URL"],
                "designation": ["Designation", "Role", "Job Title", "Title"],
                "domain": ["Domain", "Website", "Official Website"],
                "industry": ["Industry", "Sector"]
            }
            
            for ai_key, ui_candidates in field_map.items():
                ai_val = enrichment.get(ai_key)
                if not ai_val: continue
                
                # Check if we already have a value for any candidate key
                existing_key = None
                has_value = False
                for cand in ui_candidates:
                    k = find_key(cand)
                    if k:
                        existing_key = k
                        if data.get(k):
                            has_value = True
                            break
                
                # If no value, update it
                if not has_value:
                    target_key = existing_key or ui_candidates[0]
                    data[target_key] = ai_val
                    updated = True
            
            if updated:
                cur.execute(
                    "UPDATE company_registry SET row_data = %s, updated_at = NOW() WHERE id = %s",
                    (json.dumps(data), row_id)
                )
                conn.commit()
                return {"success": True, "enriched": enrichment}
            else:
                return {"success": True, "message": "Metadata already synchronized."}
                
        except Exception as parse_err:
            print(f"AI Parse Error: {parse_err} | Response: {ai_response}")
            raise HTTPException(status_code=500, detail="AI returned malformed data.")

    except Exception as e:
        print(f"Enrichment Error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        cur.close()
        conn.close()
