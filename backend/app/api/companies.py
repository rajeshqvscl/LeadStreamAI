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

@router.get("/companies/unique-tabs")
def get_unique_tabs(user_id: Optional[str] = Header(None, alias="X-User-Id")):
    """Returns a list of unique _source_tab values present in the registry."""
    conn = get_db_connection()
    cur = conn.cursor()
    
    uid = normalize_user_id(user_id)
    is_admin = (str(user_id or '').lower() == 'admin')
    
    where_clause = ""
    params = []
    if is_admin:
        where_clause = "WHERE row_data->>'_source_tab' IS NOT NULL"
    elif uid:
        where_clause = "WHERE user_id = %s AND row_data->>'_source_tab' IS NOT NULL"
        params.append(uid)
    else:
        where_clause = "WHERE user_id IS NULL AND row_data->>'_source_tab' IS NOT NULL"
        
    try:
        query = f"SELECT DISTINCT row_data->>'_source_tab' FROM company_registry {where_clause}"
        cur.execute(query, params)
        tabs = [r[0] for r in cur.fetchall() if r[0]]
        return {"tabs": tabs}
    except Exception as e:
        print(f"Error fetching unique tabs: {str(e)}")
        return {"tabs": []}
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
        print(f"DEBUG: import_companies started for user {uid} with {len(rows)} raw rows")
        if processed_rows:
            print(f"DEBUG: First processed row keys: {list(processed_rows[0].keys())}")
            print(f"DEBUG: First processed row sample: {processed_rows[0]}")
            print(f"DEBUG: Source tab for first row: {processed_rows[0].get('_source_tab')}")
        
        # Smart Sync vs Full Purge
        if processed_rows:
            # Extract unique source tabs from incoming data
            tabs_to_clear = {r["_source_tab"] for r in processed_rows if "_source_tab" in r}
            
            # If the user is importing ALL tabs (or we have no tab info), we do a full wipe
            # as requested ("purge old one and new should appear")
            # We detect this if there are multiple tabs or if it's the "ALL_TABS" case
            if len(tabs_to_clear) > 1 or not tabs_to_clear:
                print(f"DEBUG: Performing FULL Registry Purge for user {uid}")
                cur.execute("DELETE FROM company_registry WHERE user_id = %s", (uid,))
            else:
                # Specific Tab Sync: Only delete rows from that specific tab
                tab_name = list(tabs_to_clear)[0]
                print(f"DEBUG: Performing SMART Purge for tab '{tab_name}'")
                cur.execute("""
                    DELETE FROM company_registry 
                    WHERE user_id = %s AND row_data->>'_source_tab' = %s
                """, (uid, tab_name))
                
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
        for idx, (k, v) in enumerate(row.items()):
            k_str = str(k).strip()
            # Preserve original key exactly as in sheet
            val = str(v).strip() if v else ""
            clean_row[k_str] = val
        
        # Trigger AI enrichment for missing critical data (Limit to first 30)
        # We search for email/phone in any field for logic, but don't create new columns
        has_email = any("@" in str(v) and "." in str(v) for v in clean_row.values())
        has_phone = any(any(c.isdigit() for c in str(v)) and len(str(v)) > 7 for v in clean_row.values())
            
        if (not has_email or not has_phone) and i < 30:
            try:
                enriched = enrich_row_data_internal(clean_row)
                # Update but don't overwrite if we already have it
                # We use a more flexible mapping to match your sheet's headers
                for ek, ev in enriched.items():
                    if ek == "email":
                        target = "Email" if "Email" in clean_row else ("Emails" if "Emails" in clean_row else "Email")
                        if not clean_row.get(target): clean_row[target] = ev
                    elif ek == "phone":
                        target = "Mobile" if "Mobile" in clean_row else ("Phone" if "Phone" in clean_row else "Mobile")
                        if not clean_row.get(target): clean_row[target] = ev
                    elif ek == "linkedin_url" and not clean_row.get("LinkedIn Profile"): clean_row["LinkedIn Profile"] = ev
                    elif ek == "designation" and not clean_row.get("Designation"): clean_row["Designation"] = ev
                    elif ek == "industry" and not clean_row.get("Industry"): clean_row["Industry"] = ev
            except:
                pass
        
        results.append(clean_row)
    return results

def discover_gsheet_tabs(doc_id: str) -> List[Dict[str, str]]:
    """
    Scrapes the real GIDs (Grid IDs) from the Google Sheet HTML.
    Uses multiple regex patterns for maximum reliability.
    """
    try:
        url = f"https://docs.google.com/spreadsheets/d/{doc_id}/edit"
        # We use a standard user agent to ensure we get the full HTML bootstrap
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        resp = requests.get(url, headers=headers, timeout=20)
        if resp.status_code != 200:
            return []
            
        html = resp.text
        import re
        
        # Primary Pattern: Modern Google Sheets bootstrap structure
        # Look for combinations of name and id/gid
        patterns = [
            r'\{"name":"([^"]+)","id":(\d+)',           # Standard id
            r'"sheetName":"([^"]+)","sheetId":(\d+)',   # Modern sheetId
            r'"name":"([^"]+)","gid":(\d+)',            # Alternative gid
            r'\{"1":"([^"]+)","2":(\d+)',               # Obfuscated internal
        ]
        
        tabs_map = {} # Using map to prevent duplicates
        for pattern in patterns:
            matches = re.findall(pattern, html)
            for name, gid in matches:
                if name not in tabs_map:
                    tabs_map[name] = str(gid)
        
        tabs = [{"name": name, "gid": gid} for name, gid in tabs_map.items()]
        
        if not tabs:
            # Final Fallback: If no numeric GIDs found, use name-based tabs from XLSX
            print("DEBUG: HTML GID discovery failed. Falling back to XLSX sheet names.")
            return discover_gsheet_tabs_xlsx(doc_id)
            
        print(f"DEBUG: Discovered {len(tabs)} tabs with real GIDs: {[t['name'] for t in tabs]}")
        return tabs
    except Exception as e:
        print(f"Tab Discovery Error: {str(e)}")
        return []
    except Exception as e:
        print(f"Tab Discovery Error: {str(e)}")
        return []

def discover_gsheet_tabs_xlsx(doc_id: str) -> List[Dict[str, str]]:
    """Fallback method using XLSX structure."""
    try:
        import zipfile
        import xml.etree.ElementTree as ET
        import io
        
        xlsx_url = f"https://docs.google.com/spreadsheets/d/{doc_id}/export?format=xlsx"
        resp = requests.get(xlsx_url, timeout=20)
        if resp.status_code != 200: return []
            
        with zipfile.ZipFile(io.BytesIO(resp.content)) as z:
            with z.open('xl/workbook.xml') as f:
                tree = ET.parse(f)
                root = tree.getroot()
                ns = {'ns': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
                sheets = root.find('ns:sheets', ns)
                
                tabs = []
                if sheets is not None:
                    for i, s in enumerate(sheets.findall('ns:sheet', ns)):
                        tabs.append({
                            "name": s.get('name'),
                            "gid": s.get('sheetId') or str(i)
                        })
                return tabs
    except:
        return []

def save_sync_config(url: str, sheet_name: str, user_id: Optional[str]):
    """Persists a GSheet sync configuration for background auto-updates."""
    uid = normalize_user_id(user_id)
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        # Check if already exists for this user/url/sheet
        cur.execute("""
            SELECT id FROM gsheet_sync_configs 
            WHERE url = %s AND sheet_name = %s AND user_id = %s
        """, (url, sheet_name or 'Default', uid))
        
        if cur.fetchone():
            cur.execute("""
                UPDATE gsheet_sync_configs 
                SET last_sync = NOW(), is_auto_sync = TRUE
                WHERE url = %s AND sheet_name = %s AND user_id = %s
            """, (url, sheet_name or 'Default', uid))
        else:
            cur.execute("""
                INSERT INTO gsheet_sync_configs (url, sheet_name, user_id, last_sync)
                VALUES (%s, %s, %s, NOW())
            """, (url, sheet_name or 'Default', uid))
        conn.commit()
    except Exception as e:
        print(f"Error saving sync config: {e}")
        conn.rollback()
    finally:
        cur.close()
        conn.close()

def background_auto_sync():
    """Iterates through all auto-sync configs and re-triggers imports."""
    print("[background] Starting GSheet Auto-Sync cycle...")
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    try:
        cur.execute("SELECT * FROM gsheet_sync_configs WHERE is_auto_sync = TRUE")
        configs = cur.fetchall()
        for cfg in configs:
            try:
                print(f"[background] Auto-syncing: {cfg['url']} ({cfg['sheet_name']})")
                # Re-importing logic (simplified call to our own endpoint logic)
                # We can call import_companies_gsheet internal logic or just reuse the function
                import_companies_gsheet({
                    "url": cfg['url'],
                    "sheet_name": cfg['sheet_name'] if cfg['sheet_name'] != 'Default' else None,
                    "_is_background": "true" # Prevent re-saving config in loop
                }, str(cfg['user_id']) if cfg['user_id'] else None)
            except Exception as e:
                print(f"[background] Sync failed for {cfg['url']}: {e}")
    finally:
        cur.close()
        conn.close()

@router.post("/companies/gsheet-tabs")
def get_gsheet_tabs(req: Dict[str, str]):
    """Fetches the list of sheet tabs/names from a public Google Sheet using HTML scraping for maximum reliability."""
    url = req.get("url", "").strip()
    if not url or "/d/" not in url:
        raise HTTPException(status_code=400, detail="Invalid Google Sheet URL.")
    doc_id = url.split("/d/")[1].split("/")[0]
    tabs = discover_gsheet_tabs(doc_id)
    if tabs:
        return {"tabs": tabs}
    return {"tabs": [{"name": "Sheet1", "gid": "0"}]}

@router.post("/companies/import-gsheet")
def import_companies_gsheet(req: Dict[str, Any], user_id: Optional[str] = Header(None, alias="X-User-Id")):
    """Syncs a public Google Sheet into the company registry. Supports specific tabs or all tabs."""
    url = req.get("url")
    sheet_name = req.get("sheet_name")  # Optional: specific tab name or "ALL_TABS"
    auto_sync = req.get("auto_sync") == True or req.get("auto_sync") == "true"
    is_bg = req.get("_is_background") == "true"
    
    if not url:
        raise HTTPException(status_code=400, detail="URL is required")
    
    # Save config if requested and not already in background loop
    if auto_sync and not is_bg:
        save_sync_config(url, sheet_name, user_id)
    
    raw_url = url.strip()
    if "/d/" not in raw_url:
        raise HTTPException(status_code=400, detail="Invalid Google Sheet URL format.")
    
    doc_id = raw_url.split("/d/")[1].split("/")[0]
    gid_match = re.search(r"[?&#]gid=(\d+)", raw_url)
    default_gid = gid_match.group(1) if gid_match else "0"

    all_rows = []
    tabs_to_process = []

    # Resolve which tabs to process
    if sheet_name == "ALL_TABS":
        tabs_to_process = discover_gsheet_tabs(doc_id)
        if not tabs_to_process:
            tabs_to_process = [{"name": "Default", "gid": default_gid}]
    else:
        target_gid = default_gid
        if sheet_name:
            tabs = discover_gsheet_tabs(doc_id)
            print(f"DEBUG: Discovered {len(tabs)} tabs for sheet {doc_id}")
            for t in tabs:
                if t['name'].strip().lower() == sheet_name.strip().lower():
                    target_gid = t['gid']
                    print(f"DEBUG: Matched sheet_name '{sheet_name}' to GID {target_gid}")
                    break
        tabs_to_process = [{"name": sheet_name or "Sheet1", "gid": target_gid}]
    # Process each resolved tab
    for tab in tabs_to_process:
        try:
            # We try two endpoints for maximum reliability: 
            # 1. GID-based export (standard CSV)
            # 2. Name-based export (GViz)
            gid = tab.get('gid', '0')
            sheet_name_encoded = requests.utils.quote(tab['name'])
            
            # Try GID first as it's the primary identifier
            export_url = f"https://docs.google.com/spreadsheets/d/{doc_id}/export?format=csv&gid={gid}"
            print(f"DEBUG: Syncing tab '{tab['name']}' (GID: {gid})")
            
            resp = requests.get(export_url, timeout=30)
            
            # If GID fails (sometimes XLSX sheetId != GID), fallback to GViz Name-based export
            if resp.status_code != 200 or len(resp.text) < 10:
                print(f"DEBUG: GID export failed or empty for '{tab['name']}'. Falling back to GViz Name-based...")
                export_url = f"https://docs.google.com/spreadsheets/d/{doc_id}/gviz/tq?tqx=out:csv&sheet={sheet_name_encoded}&_t={int(time.time())}"
                resp = requests.get(export_url, timeout=30)
            
            if resp.status_code != 200:
                print(f"ERROR: Both GID and Name-based sync failed for tab '{tab['name']}'. Skipping.")
                continue
            
            csv_data = resp.text
            if not csv_data or len(csv_data) < 5:
                print(f"WARNING: Tab '{tab['name']}' returned no content. Skipping.")
                continue

            # CLEANUP: Remove leading empty lines or garbage before the actual headers
            lines = csv_data.splitlines()
            header_index = 0
            
            # Refined Header Detection: Find the first row with recognized keywords
            # A header row should match keywords but NOT look like a real data row (no long numbers/emails)
            header_index = -1
            keywords = ['name', 'email', 'company', 'website', 'contact', 'member', 'person', 'designation', 'role', 'phone', 'mobile']
            
            for i in range(min(15, len(lines))):
                lower_line = lines[i].lower()
                matches = sum(1 for kw in keywords if kw in lower_line)
                
                # Check if it looks like data (contains a long number or an actual email domain)
                has_long_number = any(len(re.sub(r'\D', '', part)) > 9 for part in lines[i].split(','))
                has_real_email = any('@' in part and '.' in part and len(part) > 5 for part in lines[i].split(','))
                
                # If a line has at least 1 matching keyword and doesn't look like data, it's a header
                if matches >= 1 and not has_long_number and not has_real_email:
                    header_index = i
                    break
            
            if header_index != -1:
                # We found a header row!
                cleaned_csv = "\n".join(lines[header_index:])
                reader = csv.reader(io.StringIO(cleaned_csv))
                header_row = next(reader, [])
                
                # TRIM: Find the actual end of data to avoid trailing empty columns (Field_10, Field_11...)
                last_non_empty = -1
                for idx, h in enumerate(header_row):
                    if h.strip(): last_non_empty = idx
                
                if last_non_empty != -1:
                    header_row = header_row[:last_non_empty + 1]
                
                data_reader = reader
            else:
                # No header found! Treat the whole sheet as data and use A, B, C...
                print(f"DEBUG: No recognizable headers found. Generating default headers (A, B, C...) for tab {tab['name']}")
                cleaned_csv = "\n".join(lines)
                data_reader = csv.reader(io.StringIO(cleaned_csv))
                
                # Peek to determine width
                first_row = next(data_reader, [])
                if not first_row: continue
                
                num_cols = len(first_row)
                import string
                header_row = []
                for i in range(num_cols):
                    col_name = ""
                    temp_i = i
                    while temp_i >= 0:
                        col_name = string.ascii_uppercase[temp_i % 26] + col_name
                        temp_i = (temp_i // 26) - 1
                    header_row.append(f"Column {col_name}")
                
                # Reset reader to include first row
                data_reader = csv.reader(io.StringIO(cleaned_csv))

            for row_data in data_reader:
                # Skip truly empty rows to avoid junk data
                if not any(val.strip() for val in row_data):
                    continue
                    
                row_dict = {}
                # Only take data up to the header length to prevent trailing empty fields
                for idx in range(len(header_row)):
                    val = row_data[idx] if idx < len(row_data) else ""
                    key = header_row[idx].strip()
                    row_dict[key] = val
                
                row_dict["_source_tab"] = tab["name"]
                all_rows.append(row_dict)
        except Exception as e:
            print(f"GSheet import error for tab {tab['name']}: {str(e)}")

    print(f"DEBUG: Finished processing all tabs. Total rows collected: {len(all_rows)}")
    if not all_rows:
        raise HTTPException(status_code=400, detail="No data found in selected tabs. Ensure the sheet is public and tabs contain data.")

    # This will call the enriched import_companies
    return import_companies(all_rows, user_id)

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
            
            # Check for existing column matching one of our candidates
            target_key = None
            for cand in ui_candidates:
                cand_clean = cand.lower().replace(" ","")
                for k in data.keys():
                    if k.lower().replace(" ","") == cand_clean:
                        target_key = k
                        break
                if target_key: break
            
            # Only update if the column EXISTS in the sheet
            if target_key and not data.get(target_key):
                data[target_key] = ai_val
            
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
