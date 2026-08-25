from fastapi import APIRouter, HTTPException, Header
from app.database import get_db_connection
import psycopg2.extras
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import json
import csv
import io
import re
import sys
import httpx

# Dynamically raise the CSV field size limit to the maximum possible for this platform
# to prevent _csv.Error: field larger than field limit (131072) on large GSheets
max_limit = sys.maxsize
while True:
    try:
        csv.field_size_limit(max_limit)
        break
    except OverflowError:
        max_limit = int(max_limit / 10)

from app.models.lead import insert_lead, save_email_draft
from app.services.llm_services import EmailGenerator
from psycopg2.extras import execute_values
import time
from concurrent.futures import ThreadPoolExecutor
from app.utils.auth_helpers import normalize_user_id, check_daily_email_limit, get_daily_email_limit

# --- REDIS CACHE INITIALIZATION ---
import os
import logging

logger = logging.getLogger(__name__)

redis_client = None
redis_available = False

try:
    import redis
    REDIS_URL = os.getenv("REDIS_URL") or os.getenv("REDIS_TLS_URL") or "redis://localhost:6379"
    redis_client = redis.Redis.from_url(
        REDIS_URL,
        decode_responses=True,
    )
    redis_client.ping()
    redis_available = True
    logger.info(f"SUCCESS: Connected to Redis Cache inside companies.py at {REDIS_URL.split('@')[-1]}")
except Exception as re_err:
    logger.warning(f"NOTICE: Redis is not active inside companies.py. Falling back to direct database. Error: {re_err}")
    redis_client = None
    redis_available = False


def _redis_delete_pattern(pattern: str):
    """Delete Redis keys matching pattern using SCAN (non-blocking)."""
    if not (redis_available and redis_client):
        return
    try:
        cursor = 0
        deleted = 0
        while True:
            cursor, keys = redis_client.scan(cursor=cursor, match=pattern, count=100)
            if keys:
                redis_client.delete(*keys)
                deleted += len(keys)
            if cursor == 0:
                break
        if deleted:
            logger.info(f"SUCCESS: Invalidated {deleted} cache keys for pattern: {pattern}")
    except Exception as ie:
        logger.error(f"Failed to invalidate cache for pattern {pattern}: {ie}")


def invalidate_companies_cache(user_id: str = "*"):
    _redis_delete_pattern(f"companies:{user_id}:*")


router = APIRouter()
@router.get("/companies")
def list_companies(
    page: int = 1, 
    limit: int = 100, 
    search: Optional[str] = None,
    filters: Optional[str] = None, # JSON string of key-value filters
    user_id: Optional[str] = Header(None, alias="X-User-Id")
):
    """Returns company profiles from the internal company registry database with pagination and global search."""
    uid = normalize_user_id(user_id)
    
    # Build unique composite cache key for companies list queries
    cache_key = f"companies:{uid}:{page}:{limit}:{search}:{filters}"
    
    if redis_available and redis_client:
        try:
            cached = redis_client.get(cache_key)
            if cached:
                logger.info(f"INFO: Cache HIT for companies query of user {uid} on page {page}")
                return json.loads(cached)
        except Exception as ce:
            logger.warning(f"WARNING: Redis companies cache read error: {ce}")
            
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    offset = (page - 1) * limit
    
    # Base query construction - strictly separate data per user
    base_where = ""
    params = []
    
    conditions = []
    if uid:
        conditions.append("user_id = %s")
        try:
            params.append(int(uid))
        except Exception:
            params.append(uid)
        
    # Apply Global Search — split into individual terms so each can match in different fields
    if search:
        terms = search.strip().split()
        for term in terms:
            search_term = f"%{term}%"
            conditions.append(f"row_data::text ILIKE %s")
            params.append(search_term)
        
    # Apply Column Filters
    if filters:
        try:
            filter_map = json.loads(filters)
            for key, value in filter_map.items():
                if value:
                    if key == "generated":
                        if str(value).lower() == "true":
                            conditions.append("_is_generated = TRUE")
                        elif str(value).lower() == "false":
                            conditions.append("_is_generated = FALSE")
                    else:
                        safe_key = re.sub(r'[^\w\s\-]', '', key)
                        conditions.append(f"row_data->>%s ILIKE %s")
                        params.extend([safe_key, f"%{value}%"])
        except Exception:
            pass
    
    base_where = ""
    if conditions:
        base_where = "WHERE " + " AND ".join(conditions)

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

        result = {
            "companies": companies,
            "total": total,
            "page": page,
            "limit": limit,
            "pages": (total + limit - 1) // limit
        }
        
        if redis_available and redis_client:
            try:
                redis_client.setex(cache_key, 60, json.dumps(result))
                logger.info(f"INFO: Cached companies query for user {uid} on page {page}")
            except Exception as ce:
                logger.warning(f"WARNING: Redis companies cache write error: {ce}")
                
        return result
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
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    
    uid = normalize_user_id(user_id)
    
    conditions = []
    params = []
    if uid:
        conditions.append("user_id = %s")
        try:
            params.append(int(uid))
        except Exception:
            params.append(uid)
    conditions.append("row_data->>'_source_tab' IS NOT NULL")
    where_clause = "WHERE " + " AND ".join(conditions)
        
    try:
        query = f"SELECT DISTINCT row_data->>'_source_tab' AS tab_name FROM company_registry {where_clause}"
        cur.execute(query, params)
        tabs = [r['tab_name'] for r in cur.fetchall() if r['tab_name']]
        return {"tabs": tabs}
    except Exception as e:
        logger.error(f"Error fetching unique tabs: {str(e)}")
        return {"tabs": []}
    finally:
        cur.close()
        conn.close()

@router.post("/companies/import")
def import_companies(rows: List[Dict[str, Any]], user_id: Optional[str] = Header(None, alias="X-User-Id")):
    """Imports a batch of data, automatically enriching missing fields. Uses upsert to preserve existing data."""
    uid = normalize_user_id(user_id)
    
    # --- AUTOMATION: Enrich rows before insertion ---
    try:
        processed_rows = process_and_enrich_rows(rows)
    except Exception as enrich_err:
        print(f"ERROR: Row enrichment crashed: {enrich_err}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Import failed during enrichment: {str(enrich_err)}")
    
    if not processed_rows:
        return {"success": True, "count": 0, "message": "No valid rows to import"}
    
    print(f"DEBUG: import_companies started for user {uid} with {len(processed_rows)} processed rows")
    if processed_rows:
        print(f"DEBUG: First processed row keys: {list(processed_rows[0].keys())}")
        print(f"DEBUG: First processed row sample: {processed_rows[0]}")
        print(f"DEBUG: Source tab for first row: {processed_rows[0].get('_source_tab')}")
    
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    
    try:
        # Fetch existing lead emails for this user to preserve "Generated" status
        cur.execute("SELECT email FROM leads_raw WHERE user_id = %s", (uid,))
        existing_emails = {r[0].lower() for r in cur.fetchall() if r[0]}
        
        # Fetch existing company registry emails to preserve _is_generated status
        cur.execute("SELECT row_data->>'Email' as email, _is_generated FROM company_registry WHERE user_id = %s", (uid,))
        existing_registry = {r['email'].lower(): r['_is_generated'] for r in cur.fetchall() if r['email']}
        
        upsert_data = []
        insert_count = 0
        update_count = 0
        match_count = 0
        
        for row in processed_rows:
            # Robust email detection across all fields (case-insensitive)
            row_email = None
            for val in row.values():
                if isinstance(val, str) and '@' in val and '.' in val:
                    row_email = val.strip().lower()
                    break
            
            # Determine _is_generated: preserve existing if present, else check against leads_raw
            if row_email and row_email in existing_registry:
                is_generated = existing_registry[row_email]
            else:
                is_generated = row_email in existing_emails if row_email else False
            
            if is_generated: 
                match_count += 1
            
            upsert_data.append((json.dumps(row), uid, is_generated, row_email))
            
            if row_email and row_email in existing_registry:
                update_count += 1
            else:
                insert_count += 1
        
        print(f"DEBUG: Upserting {insert_count} new, {update_count} existing rows. Marked {match_count} as Generated")
        
        # Deduplicate by the EXACT constrained value (row_data->>'Email') to prevent
        # ON CONFLICT "cannot affect row a second time". The old logic scanned any
        # '@' value in the row, which can differ from the indexed "Email" field.
        # Keep the last occurrence of each email (more complete data).
        seen_constrained = set()
        deduped_upsert_data = []
        for row in reversed(upsert_data):
            try:
                constrained_email = json.loads(row[0]).get("Email")
            except Exception:
                constrained_email = None
            if constrained_email:
                if constrained_email in seen_constrained:
                    continue
                seen_constrained.add(constrained_email)
            deduped_upsert_data.append(row)
        deduped_upsert_data.reverse()
        
        if len(deduped_upsert_data) < len(upsert_data):
            print(f"DEBUG: Deduplicated {len(upsert_data)} rows to {len(deduped_upsert_data)} by email")
        
        # Upsert using ON CONFLICT on the unique index (user_id, email)
        # We need to extract email from row_data for the conflict target
        upsert_query = """
            INSERT INTO company_registry (row_data, user_id, _is_generated)
            VALUES %s
            ON CONFLICT (user_id, (row_data->>'Email')) DO UPDATE SET
                row_data = EXCLUDED.row_data,
                _is_generated = EXCLUDED._is_generated,
                updated_at = NOW()
        """
        
        # Prepare data without email for execute_values (email is in row_data)
        insert_values = [(row[0], row[1], row[2]) for row in deduped_upsert_data]
        
        # Use ::jsonb cast so psycopg2 text values are accepted by the JSONB column
        execute_values(cur, upsert_query, insert_values, template="(%s::jsonb, %s, %s)")
        conn.commit()
        invalidate_companies_cache(str(uid))
        return {"success": True, "count": len(processed_rows), "inserted": insert_count, "updated": update_count}
    except Exception as e:
        conn.rollback()
        print(f"ERROR: Import failed: {str(e)}")
        import traceback
        traceback.print_exc()
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
        invalidate_companies_cache(str(uid))
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
        invalidate_companies_cache(str(uid))
        return {"success": True}
    finally:
        cur.close()
        conn.close()

@router.post("/companies/request-access")
def request_db_access(user_id: Optional[str] = Header(None, alias="X-User-Id")):
    """Submits access request (Legacy - keeping for route compatibility if needed)."""
    return {"message": "Access restriction removed. You have full system clearance."}

def process_and_enrich_rows(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Cleans and auto-enriches a list of rows in parallel, ensuring critical columns exist."""
    # Strip control chars (incl. NUL \x00) — PostgreSQL jsonb rejects them with a 500
    import re as _re_ctrl
    ctrl_chars = _re_ctrl.compile(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]')
    
    # Process all rows: clean keys and values synchronously (very fast, <0.05s for 10k rows)
    cleaned_rows = []
    for row in rows:
        clean_row = {}
        for k, v in row.items():
            k_str = ctrl_chars.sub('', str(k)).strip()
            val = ctrl_chars.sub('', str(v)).strip() if v else ""
            if not k_str:
                continue
            clean_row[k_str] = val
        cleaned_rows.append(clean_row)

    # Identify the first 100 rows missing email/phone for parallel AI enrichment
    rows_to_enrich = []
    for i in range(min(100, len(cleaned_rows))):
        row = cleaned_rows[i]
        # Skip rows that look like garbage header rows (no company name, no email, short values)
        name_val = (row.get("Company Name") or row.get("Person Name") or '').strip()
        if len(name_val) <= 2 and not any("@" in str(v) for v in row.values()):
            continue
        has_email = any("@" in str(v) and "." in str(v) for v in row.values())
        has_phone = any(any(c.isdigit() for c in str(v)) and len(str(v)) > 7 for v in row.values())
        if not has_email or not has_phone:
            rows_to_enrich.append((i, row))

    if rows_to_enrich:
        def enrich_single_row(args):
            idx, row = args
            try:
                enriched = enrich_row_data_internal(row)
                for ek, ev in enriched.items():
                    if ek == "email":
                        target = "Email" if "Email" in row else ("Emails" if "Emails" in row else "Email")
                        if not row.get(target): row[target] = ev
                    elif ek == "phone":
                        target = "Phone" if "Phone" in row else ("Mobile" if "Mobile" in row else "Phone")
                        if not row.get(target): row[target] = ev
                    elif ek == "linkedin_url":
                        target = "LinkedIn" if "LinkedIn" in row else ("LinkedIn URL" if "LinkedIn URL" in row else "LinkedIn")
                        if not row.get(target): row[target] = ev
            except Exception as e:
                print(f"Row enrichment error: {e}")
            return idx, row

        # Use dynamic max_workers based on task count up to 10 to avoid thread pool context-switching overhead
        with ThreadPoolExecutor(max_workers=min(10, len(rows_to_enrich))) as executor:
            enriched_results = list(executor.map(enrich_single_row, rows_to_enrich))
            
        for idx, row in enriched_results:
            cleaned_rows[idx] = row

    # Normalize email column: ensure every row has an "Email" key with the email value
    # This enables the unique index on (user_id, row_data->>'Email') to work correctly
    for row in cleaned_rows:
        email_val = None
        # Check common email column names
        for key in ["Email", "Emails", "email", "Email Address", "Work Email", "Primary Email", "Contact Email"]:
            if key in row and row[key]:
                val = str(row[key]).strip()
                if "@" in val and "." in val:
                    email_val = val
                    break
        # Fallback: scan all values for email-like string
        if not email_val:
            for val in row.values():
                val_str = str(val).strip()
                if "@" in val_str and "." in val_str and " " not in val_str:
                    email_val = val_str
                    break
        if email_val:
            row["Email"] = email_val
        else:
            # Empty "Email" values collide in the unique index (row_data->>'Email')
            # because '' == '' in Postgres (unlike NULL). Remove empty email keys
            # so the expression evaluates to NULL and never conflicts.
            for key in ["Email", "Emails", "email", "Email Address", "Work Email", "Primary Email", "Contact Email"]:
                if key in row and not str(row[key]).strip():
                    del row[key]

    return cleaned_rows

async def discover_gsheet_tabs(doc_id: str) -> List[Dict[str, str]]:
    """
    Discovers sheet tabs - returns sheet NAMES with gid=None (import uses name-based GViz fallback which works).
    Order: XLSX (Anyone with link) -> GViz (Anyone with link) -> HTML (Publish to web, returns real GID)
    """
    import re
    
    # Method 1: XLSX export - works with "Anyone with link", returns sheet names (gid=None)
    print(f"DEBUG: Trying XLSX discovery for doc_id={doc_id}")
    tabs = await discover_gsheet_tabs_xlsx(doc_id)
    if tabs:
        for tab in tabs:
            tab['gid'] = None  # XLSX sheetId != CSV GID
        print(f"DEBUG: Discovered {len(tabs)} tabs via XLSX: {[t['name'] for t in tabs]}")
        return tabs
    
    # Method 2: GViz API - works with "Anyone with link", returns sheet names (gid=None, it's index not GID)
    print(f"DEBUG: Trying GViz discovery for doc_id={doc_id}")
    tabs = await discover_gsheet_tabs_gviz(doc_id)
    if tabs:
        print(f"DEBUG: Discovered {len(tabs)} tabs via GViz: {[t['name'] for t in tabs]}")
        return tabs
    
    # Method 3: HTML scraping - requires "Publish to web", returns REAL GID
    print(f"DEBUG: Trying HTML discovery for doc_id={doc_id}")
    try:
        url = f"https://docs.google.com/spreadsheets/d/{doc_id}/edit"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        async with httpx.AsyncClient(timeout=20.0, follow_redirects=True) as client:
            resp = await client.get(url, headers=headers)
        print(f"DEBUG: HTML scrape status: {resp.status_code}")
        if resp.status_code == 200:
            html = resp.text
            patterns = [
                r'\{"name":"([^"]+)","id":(\d+)',
                r'"sheetName":"([^"]+)","sheetId":(\d+)',
                r'"name":"([^"]+)","gid":(\d+)',
                r'\{"1":"([^"]+)","2":(\d+)',
                r'{"label":"([^"]+)",.*?"id":(\d+)',
                r'{"name":"([^"]+)"[^}]*"id":(\d+)',
                r'sheets\[\d+\].*?gid["\']?\s*[:=]\s*["\']?(\d+)["\']?.*?title["\']?\s*[:=]\s*["\']([^"\']+)',
            ]
            
            tabs_map = {}
            for pattern in patterns:
                matches = re.findall(pattern, html)
                for name, gid in matches:
                    if name not in tabs_map:
                        tabs_map[name] = str(gid)
            
            tabs = [{"name": name, "gid": gid} for name, gid in tabs_map.items()]
            if tabs:
                print(f"DEBUG: Discovered {len(tabs)} tabs via HTML (real GIDs): {[t['name'] for t in tabs]}")
                return tabs
    except Exception as e:
        print(f"DEBUG: Tab Discovery HTML Error: {str(e)}")
    
    print("DEBUG: All tab discovery methods failed")
    return []

async def discover_gsheet_tabs_xlsx(doc_id: str) -> List[Dict[str, str]]:
    """Fallback method using XLSX structure."""
    try:
        import zipfile
        import xml.etree.ElementTree as ET
        import io
        
        xlsx_url = f"https://docs.google.com/spreadsheets/d/{doc_id}/export?format=xlsx"
        async with httpx.AsyncClient(timeout=20.0, follow_redirects=True) as client:
            resp = await client.get(xlsx_url)
        print(f"DEBUG: XLSX export status: {resp.status_code}, content-length: {len(resp.content)}")
        if resp.status_code != 200: 
            print(f"DEBUG: XLSX failed - status {resp.status_code}")
            return []
            
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
                print(f"DEBUG: XLSX found tabs: {tabs}")
                return tabs
    except Exception as e:
        print(f"DEBUG: XLSX discovery error: {e}")
        return []

async def discover_gsheet_tabs_gviz(doc_id: str) -> List[Dict[str, str]]:
    """Discover tabs using the Google Visualization API - returns sheet names (gid will be set to None by caller)."""
    try:
        import json as json_lib
        url = f"https://docs.google.com/spreadsheets/d/{doc_id}/gviz/tq?tqx=reqId:0&tq=&_t={int(time.time())}"
        async with httpx.AsyncClient(timeout=20.0, follow_redirects=True) as client:
            resp = await client.get(url)
        print(f"DEBUG: GViz API status: {resp.status_code}")
        if resp.status_code != 200:
            print(f"DEBUG: GViz failed - status {resp.status_code}")
            return []

        text = resp.text
        json_start = text.find('{')
        json_end = text.rfind('}')
        if json_start == -1 or json_end == -1:
            print("DEBUG: GViz - no JSON found in response")
            return []

        body = text[json_start:json_end + 1]
        data = json_lib.loads(body)
        sheets = data.get('sheets') or data.get('table', {}).get('sheets', [])
        if not sheets:
            print("DEBUG: GViz - no sheets in response")
            return []

        tabs = []
        for s in sheets:
            name = s.get('label') or s.get('name', '')
            if name:
                tabs.append({"name": name, "gid": None})  # GViz 'id' is index, not GID
        print(f"DEBUG: GViz found tabs: {tabs}")
        return tabs
    except Exception as e:
        print(f"DEBUG: GViz discovery error: {e}")
        return []


@router.post("/companies/gsheet-tabs")
async def get_gsheet_tabs(req: Dict[str, str]):
    """Fetches the list of sheet tabs/names from a Google Sheet.
    Requires: File > Share > 'Anyone with link' (Viewer) minimum.
    For best results: File > Share > Publish to web.
    """
    url = req.get("url", "").strip()
    if not url or "/d/" not in url:
        raise HTTPException(status_code=400, detail="Invalid Google Sheet URL.")
    doc_id = url.split("/d/")[1].split("/")[0]
    tabs = await discover_gsheet_tabs(doc_id)
    if tabs:
        return {"tabs": tabs}
    raise HTTPException(
        status_code=400, 
        detail="Could not discover sheet tabs. Fix: Open Google Sheet > Share > 'Anyone with link' (Viewer) > Done. For best results: File > Share > Publish to web > Entire Document > Publish."
    )

@router.post("/companies/import-gsheet")
async def import_companies_gsheet(req: Dict[str, Any], user_id: Optional[str] = Header(None, alias="X-User-Id")):
    """Syncs a public Google Sheet into the company registry. Supports specific tabs or all tabs."""
    url = req.get("url")
    sheet_name = req.get("sheet_name")  # Optional: specific tab name or "ALL_TABS"
    
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
        tabs = await discover_gsheet_tabs(doc_id)
        # To prevent memory crashes, restrict ALL_TABS to only load "ALL DATA"
        tabs_to_process = [t for t in tabs if t['name'].strip().upper() == "ALL DATA"]
        if not tabs_to_process and tabs:
            tabs_to_process = [tabs[0]] # fallback to first tab
        if not tabs_to_process:
            tabs_to_process = [{"name": "Default", "gid": default_gid}]
    else:
        target_gid = default_gid
        if sheet_name:
            tabs = await discover_gsheet_tabs(doc_id)
            for t in tabs:
                if t['name'].strip().lower() == sheet_name.strip().lower():
                    target_gid = t['gid']
                    break
        tabs_to_process = [{"name": sheet_name or "Sheet1", "gid": target_gid}]

    import threading
    all_rows_lock = threading.Lock()

    def _infer_column_names(sample_rows, num_cols):
        """Infer column names by analyzing sample data values using content heuristics."""
        inferred = []
        for col_idx in range(num_cols):
            values = []
            for row in sample_rows:
                if col_idx < len(row) and row[col_idx].strip():
                    values.append(row[col_idx].strip())
            n = len(values)
            if not values:
                inferred.append(None)
                continue
            email_hits = sum(1 for v in values if '@' in v and '.' in v.split('@')[-1])
            if email_hits > n * 0.5:
                inferred.append('Email')
                continue
            linkedin_hits = sum(1 for v in values if 'linkedin.com' in v.lower())
            if linkedin_hits > n * 0.5:
                inferred.append('LinkedIn Profile')
                continue
            url_hits = sum(1 for v in values if v.startswith(('http://', 'https://', 'www.')))
            if url_hits > n * 0.5:
                inferred.append('Website')
                continue
            phone_hits = 0
            for v in values:
                if '@' not in v and not v.startswith(('http://', 'https://', 'www.')):
                    digits = re.sub(r'\D', '', v)
                    if len(digits) >= 7:
                        phone_hits += 1
            if phone_hits > n * 0.5:
                inferred.append('Phone')
                continue
            designation_kw = ['partner', 'director', 'president', 'vice president', 'vp', 'head', 'lead',
                             'chief', 'officer', 'founder', 'ceo', 'cto', 'cfo', 'coo', 'manager', 'advisor',
                             'engineer', 'analyst', 'associate', 'consultant', 'chairman', 'board',
                             'owner', 'principal', 'senior', 'junior', 'intern']
            designation_hits = sum(1 for v in values if any(kw in v.lower() for kw in designation_kw))
            company_kw = ['ltd', 'inc', 'corp', 'llc', 'fund', 'capital', 'ventures', 'partners',
                         'limited', 'company', 'group', 'holdings', 'enterprises', 'industries',
                         'technologies', 'solutions', 'services', 'investments', 'advisors']
            company_hits = sum(1 for v in values if any(kw in v.lower() for kw in company_kw))
            name_hits = 0
            for v in values:
                words = v.split()
                if 2 <= len(words) <= 4 and all(w[0].isupper() for w in words if w):
                    if '@' not in v and '://' not in v:
                        if not any(kw in v.lower() for kw in company_kw + designation_kw):
                            name_hits += 1
            # Detect long descriptive text (notes/descriptions, not company names)
            long_text_hits = sum(1 for v in values if len(v.split()) >= 4 and not any(kw in v.lower() for kw in company_kw))
            avg_word_count = sum(len(v.split()) for v in values) / n if n else 0
            if designation_hits > n * 0.4:
                inferred.append('Designation')
            elif name_hits > n * 0.4:
                inferred.append('Person Name')
            elif company_hits > n * 0.25 and avg_word_count < 3:
                inferred.append('Company Name')
            elif company_hits > n * 0.25:
                inferred.append('Firm/Notes')
            else:
                label_kw = ['name', 'email', 'company', 'designation', 'role', 'phone',
                           'mobile', 'linkedin', 'website', 'domain', 'sector', 'industry',
                           'address', 'city', 'state', 'country', 'source', 'status',
                           'contact', 'member', 'person', 'investor', 'firm', 'organization',
                           'url', 'link', 'profile', 'mail', 'title', 'job']
                first_val = values[0] if values else ''
                matched = [kw for kw in label_kw if kw in first_val.lower()]
                if matched:
                    inferred.append(matched[0].title())
                elif any(c.isalpha() for c in first_val):
                    # Looks like a text column but unknown type
                    inferred.append('Text')
                else:
                    inferred.append(None)
        return inferred

    async def process_single_tab(tab):
        try:
            import sys
            import csv
            import urllib.parse
            max_limit = sys.maxsize
            while True:
                try:
                    csv.field_size_limit(max_limit)
                    break
                except OverflowError:
                    max_limit = int(max_limit / 10)

            gid = tab.get('gid')
            sheet_name_encoded = urllib.parse.quote(tab['name'])
            csv_data = ""
            
            # Try GID-based CSV export first (only if we have a valid numeric GID)
            if gid and str(gid).isdigit():
                export_url = f"https://docs.google.com/spreadsheets/d/{doc_id}/export?format=csv&gid={gid}"
                print(f"DEBUG: Syncing tab '{tab['name']}' via GID CSV export (GID: {gid})")
                
                async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
                    resp = await client.get(export_url)
                if resp.status_code == 200:
                    csv_data = resp.text
            
            # Fallback to GViz JSON by sheet name (works without GID)
            if not csv_data or len(csv_data) < 10:
                print(f"DEBUG: Falling back to GViz JSON by sheet name for '{tab['name']}'")
                export_url = f"https://docs.google.com/spreadsheets/d/{doc_id}/gviz/tq?sheet={sheet_name_encoded}&headers=0&_t={int(time.time())}"
                async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
                    resp = await client.get(export_url)
                if resp.status_code == 200:
                    import json, io
                    match = re.search(r'google\.visualization\.Query\.setResponse\((.*)\);', resp.text)
                    if match:
                        try:
                            data = json.loads(match.group(1))
                            rows = data.get('table', {}).get('rows', [])
                            output = io.StringIO()
                            writer = csv.writer(output)
                            for row in rows:
                                cols = row.get('c', [])
                                parsed_row = [str(c.get('v', '')) if c and c.get('v') is not None else '' for c in cols]
                                writer.writerow(parsed_row)
                            csv_data = output.getvalue()
                        except Exception as e:
                            print(f"ERROR processing GViz JSON: {e}")
                            
            if not csv_data or len(csv_data) < 5:
                print(f"ERROR: Sync failed for tab '{tab['name']}'. Skipping.")
                return

            lines = csv_data.splitlines()
            header_index = -1
            keywords = ['name', 'email', 'company', 'website', 'contact', 'member', 'person', 'designation', 'role', 'phone', 'mobile']
            for i in range(min(15, len(lines))):
                lower_line = lines[i].lower()
                parts = lines[i].split(',')
                short_cells = sum(1 for p in parts if p.strip() and len(p.strip()) < 3)
                total_cells = sum(1 for p in parts if p.strip())
                has_fragment = short_cells > total_cells * 0.4
                matches = sum(1 for kw in keywords if kw in lower_line)
                has_long_number = any(len(re.sub(r'\D', '', part)) > 9 for part in parts)
                has_real_email = any('@' in part and '.' in part and len(part) > 5 for part in parts)
                if not has_fragment and matches >= 2 and not has_long_number and not has_real_email:
                    header_index = i
                    break
            
            tab_rows = []
            if header_index != -1:
                cleaned_csv = "\n".join(lines[header_index:])
                reader = csv.reader(io.StringIO(cleaned_csv))
                header_row = next(reader, [])
                last_non_empty = -1
                for idx, h in enumerate(header_row):
                    if h.strip(): last_non_empty = idx
                if last_non_empty != -1:
                    header_row = header_row[:last_non_empty + 1]
                # Collect data rows for inference of empty/missing headers
                all_rows_for_inference = []
                for row in reader:
                    if any(val.strip() for val in row):
                        all_rows_for_inference.append(row)
                if all_rows_for_inference:
                    sample_rows = all_rows_for_inference[:20]
                    inferred = _infer_column_names(sample_rows, len(header_row))
                    for idx, name in enumerate(inferred):
                        if not header_row[idx].strip():
                            header_row[idx] = name if name else f"Column {chr(65 + idx) if idx < 26 else idx}"
                data_reader = all_rows_for_inference
            else:
                cleaned_csv = "\n".join(lines)
                data_reader = csv.reader(io.StringIO(cleaned_csv))
                first_row = next(data_reader, [])
                if not first_row: return
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
                # Collect all rows into memory for column name inference
                all_parsed_rows = [first_row]
                for row in data_reader:
                    if any(val.strip() for val in row):
                        all_parsed_rows.append(row)
                # Infer column names from sample data (skip first row which may be merged)
                sample_rows = all_parsed_rows[1:21]
                inferred = _infer_column_names(sample_rows, num_cols)
                for idx, name in enumerate(inferred):
                    if name:
                        header_row[idx] = name
                data_reader = all_parsed_rows

            for row_data in data_reader:
                if not any(val.strip() for val in row_data): continue
                row_dict = {}
                for idx in range(len(header_row)):
                    val = row_data[idx] if idx < len(row_data) else ""
                    key = header_row[idx].strip()
                    row_dict[key] = val
                row_dict["_source_tab"] = tab["name"]
                tab_rows.append(row_dict)
            
            with all_rows_lock:
                all_rows.extend(tab_rows)
        except Exception as e:
            print(f"GSheet import error for tab {tab['name']}: {str(e)}")

    # Run sequentially to save memory!
    for tab in tabs_to_process:
        await process_single_tab(tab)

    print(f"DEBUG: Finished processing all tabs. Total rows collected: {len(all_rows)}")
    if not all_rows:
        raise HTTPException(status_code=400, detail="No data found in selected tabs. Ensure the sheet is public and tabs contain data.")

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
    except Exception:
        return data

@router.post("/companies/{row_id}/generate-draft")
def generate_company_draft(row_id: int, template_name: Optional[str] = None, user_id: Optional[str] = Header(None, alias="X-User-Id")):
    """Converts a company registry record to a lead and generates an email draft."""
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    
    uid = normalize_user_id(user_id)
    
    try:
        # Secure Admin Check
        is_admin = False
        if uid:
            cur.execute("SELECT role FROM users WHERE id = %s", (uid,))
            role_row = cur.fetchone()
            if role_row:
                role_val = role_row['role'] if isinstance(role_row, dict) else role_row[0]
                if role_val and str(role_val).upper() == 'ADMIN':
                    is_admin = True

        if is_admin:
            cur.execute("SELECT row_data FROM company_registry WHERE id = %s", (row_id,))
        else:
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
            raise HTTPException(status_code=400, detail="Cannot generate draft: no email address found in this record. Add an email column (e.g. 'Email', 'Email Address') to your spreadsheet and re-import, or use the Edit button to add one.")
            
        # 2. Smart Name Detection
        name = (
            norm.get("name") or norm.get("fullname") or 
            norm.get("leadname") or norm.get("contactname") or norm.get("contact") or
            norm.get("investor") or norm.get("person") or norm.get("personname") or
            f"{norm.get('firstname', '')} {norm.get('lastname', '')}".strip()
        )
        
        # URL Safety Check: If name looks like a URL, discard it
        if name and ("http://" in name.lower() or "https://" in name.lower() or "linkedin.com" in name.lower()):
            name = ""
            
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
            company = None
        
        parts = name.split(" ", 1)
        f_name = parts[0]
        l_name = parts[1] if len(parts) > 1 else ""
        
        sender_name = "the team"
        if uid:
            cur.execute("SELECT full_name, username FROM users WHERE id = %s", (uid,))
            u = cur.fetchone()
            if u: sender_name = u['full_name'] or u['username']
            
        # Remove from unsubscribe_list if present — user explicitly chose to generate
        # a draft for this contact, so treat as an opt-back-in.
        cur.execute("DELETE FROM unsubscribe_list WHERE LOWER(email) = LOWER(%s)", (email,))
        if cur.rowcount > 0:
            logger.info(f"Removed {email} from unsubscribe_list (user-initiated draft generation)")
        # Also reset opt-out flags on the existing lead so it reappears in the review queue
        cur.execute(
            "UPDATE leads_raw SET is_unsubscribed = FALSE, email_opt_in = TRUE WHERE LOWER(email) = LOWER(%s) AND user_id = %s",
            (email, uid)
        )
        conn.commit()

        insert_lead(f_name, l_name, email, "", norm.get("linkedin", ""), company, "intelligence", data, user_id=uid, user_name=sender_name)

        cur.execute("SELECT id FROM leads_raw WHERE email = %s AND user_id = %s ORDER BY created_at DESC LIMIT 1", (email, uid))
        lead_row = cur.fetchone()
        if not lead_row:
             raise HTTPException(status_code=500, detail="Lead synchronization fault: Record failed to propagate to pipeline.")
        
        lead_id = lead_row['id'] if isinstance(lead_row, dict) else lead_row[0]
        
        try:
            # --- NEW: Reuse universal generator logic ---
            from app.api.drafts import generate_email_internal, DraftRequest
            req = DraftRequest(lead_id=lead_id, template_type=template_name or 'standard')
            res = generate_email_internal(req, user_id)
            # Mark as generated in company registry
            if is_admin:
                cur.execute("UPDATE company_registry SET _is_generated = TRUE, updated_at = NOW() WHERE id = %s", (row_id,))
            else:
                cur.execute("UPDATE company_registry SET _is_generated = TRUE, updated_at = NOW() WHERE id = %s AND user_id = %s", (row_id, uid))
            conn.commit()
            invalidate_companies_cache(str(uid))
            return res
        except Exception as e:
            import logging
            logging.getLogger(__name__).error(f"Draft Generation Error for lead {lead_id}: {e}")
            raise HTTPException(status_code=500, detail=f"Generation pipeline error: {str(e)}")
        
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
            from app.api.drafts import markdown_to_html
            
            service = get_gmail_service(int(uid))
            if service:
                # Use HTML for better consistency
                from app.services.email_service import get_user_email_font, get_user_email_font_size
                html_body = markdown_to_html(body, font_family=get_user_email_font(uid), font_size=get_user_email_font_size(uid))
                message = MIMEText(html_body, 'html')
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

        # Invalidate Redis cache so review queue shows the new draft
        try:
            from app.api.drafts import invalidate_pending_drafts_cache
            invalidate_pending_drafts_cache(str(uid) if uid else None)
        except Exception:
            pass

        # Log activity
        try:
            from app.models.lead import add_activity_log
            add_activity_log(lead_id, "DRAFT_GENERATED", f"Draft generated from Intelligence Grid {'(Gmail synced ✅)' if gmail_draft_id else ''}", sender_name)
        except Exception:
            pass
        
        return {"success": True, "lead_id": lead_id, "message": "Draft generated and moved to Lead Pipeline."}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        cur.close()
        conn.close()

class BulkCompanyDraftRequest(BaseModel):
    row_ids: list[int]
    template_name: Optional[str] = None
    signature_id: Optional[int] = None

import uuid as _uuid
import threading as _threading

_bulk_company_progress: dict = {}

@router.post("/companies/bulk-generate-drafts")
def bulk_generate_company_drafts(req: BulkCompanyDraftRequest, user_id: Optional[str] = Header(None, alias="X-User-Id")):
    """Bulk template draft generation for company registry records with parallel processing. Returns immediately with batch_id."""
    if not req.row_ids:
        return {"error": "No company IDs provided", "batch_id": None}

    batch_id = str(_uuid.uuid4())
    total = len(req.row_ids)
    _bulk_company_progress[batch_id] = {
        "total": total, "processed": 0, "success": 0, "failed": 0, "status": "running"
    }

    def _run():
        from concurrent.futures import ThreadPoolExecutor, as_completed
        from app.api.drafts import generate_email_internal, DraftRequest
        import logging, json
        logger = logging.getLogger(__name__)
        uid = normalize_user_id(user_id)

        try:
            conn = get_db_connection()
            cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
            
            # Secure Admin Check
            is_admin = False
            if uid:
                cur.execute("SELECT role FROM users WHERE id = %s", (uid,))
                role_row = cur.fetchone()
                if role_row:
                    role_val = role_row['role'] if isinstance(role_row, dict) else role_row[0]
                    if role_val and str(role_val).upper() == 'ADMIN':
                        is_admin = True

            if is_admin:
                cur.execute(
                    "SELECT id, row_data FROM company_registry WHERE id = ANY(%s)",
                    (req.row_ids,)
                )
            else:
                cur.execute(
                    "SELECT id, row_data FROM company_registry WHERE id = ANY(%s) AND user_id = %s",
                    (req.row_ids, uid)
                )
            rows = cur.fetchall()
            if not rows:
                _bulk_company_progress[batch_id]["status"] = "done"
                cur.close(); conn.close()
                return

            created_leads = []
            for row in rows:
                data = row['row_data']
                if isinstance(data, str):
                    data = json.loads(data)
                norm = {str(k).lower().replace(" ", "").replace("-", "").replace("_", ""): v for k, v in data.items() if v}

                email = (
                    norm.get("email") or norm.get("emailaddress") or
                    norm.get("workemail") or norm.get("primaryemail")
                )
                if not email:
                    for k, v in data.items():
                        val = str(v).strip()
                        if "@" in val and "." in val and len(val) > 5 and " " not in val:
                            email = val; break
                if not email:
                    _bulk_company_progress[batch_id]["processed"] += 1
                    _bulk_company_progress[batch_id]["failed"] += 1
                    continue

                name = (
                    norm.get("name") or norm.get("fullname") or
                    norm.get("leadname") or norm.get("contactname") or norm.get("contact") or
                    norm.get("investor") or norm.get("person") or norm.get("personname") or
                    f"{norm.get('firstname', '')} {norm.get('lastname', '')}".strip()
                )
                if name and ("http://" in name.lower() or "https://" in name.lower() or "linkedin.com" in name.lower()):
                    name = ""
                if not name or name.strip() == "":
                    email_prefix = email.split('@')[0]
                    name = email_prefix.replace(".", " ").replace("_", " ").replace("-", " ").title()

                company = (
                    norm.get("companyname") or norm.get("company") or
                    norm.get("investorname") or norm.get("org") or
                    norm.get("firm") or norm.get("account") or norm.get("organization")
                )
                parts = name.split(" ", 1)
                f_name, l_name = parts[0], (parts[1] if len(parts) > 1 else "")
                sender_name = "the team"
                if uid:
                    cur.execute("SELECT full_name, username FROM users WHERE id = %s", (uid,))
                    u = cur.fetchone()
                    if u: sender_name = u['full_name'] or u['username']

                # Remove from unsubscribe_list if present — user explicitly chose to generate
                # drafts for these contacts, so treat as an opt-back-in.
                cur.execute("DELETE FROM unsubscribe_list WHERE LOWER(email) = LOWER(%s)", (email,))
                # Also reset opt-out flags on any existing lead
                cur.execute(
                    "UPDATE leads_raw SET is_unsubscribed = FALSE, email_opt_in = TRUE WHERE LOWER(email) = LOWER(%s) AND user_id = %s",
                    (email, uid)
                )
                conn.commit()

                insert_lead(f_name, l_name, email, "", norm.get("linkedin", ""), company, "intelligence", data, user_id=uid, user_name=sender_name)
                created_leads.append((row['id'], email))

            lead_id_map = {}
            for row_id, email in created_leads:
                cur.execute(
                    "SELECT id FROM leads_raw WHERE email = %s AND user_id = %s ORDER BY created_at DESC LIMIT 1",
                    (email, uid)
                )
                lr = cur.fetchone()
                if lr:
                    lead_id_map[row_id] = lr['id']
            cur.close(); conn.close()

            if not lead_id_map:
                _bulk_company_progress[batch_id]["status"] = "done"
                return

            template_type = req.template_name or 'standard'
            success_ids, failed_ids = [], []
            lead_results = []  # [{lead_id, ok}] for frontend DB reconciliation

            with ThreadPoolExecutor(max_workers=3) as executor:
                def process_one(row_id):
                    lid = lead_id_map.get(row_id)
                    if not lid:
                        return (row_id, None, False, "lead not found")
                    try:
                        draft_req = DraftRequest(lead_id=lid, template_type=template_type)
                        res = generate_email_internal(draft_req, user_id)
                        return (row_id, lid, "error" not in res, res)
                    except Exception as e:
                        return (row_id, lid, False, str(e))

                futures = {executor.submit(process_one, rid): rid for rid in lead_id_map}
                for future in as_completed(futures):
                    rid, lid, ok, _ = future.result()
                    if lid:
                        lead_results.append({"lead_id": lid, "ok": ok})
                    if ok:
                        success_ids.append(rid)
                    else:
                        failed_ids.append(rid)
                    p = _bulk_company_progress[batch_id]
                    p["processed"] += 1
                    p["results"] = list(lead_results)  # snapshot for reconciliation
                    if ok:
                        p["success"] += 1
                    else:
                        p["failed"] += 1

            if success_ids:
                conn2 = get_db_connection()
                cur2 = conn2.cursor()
                if is_admin:
                    cur2.execute(
                        "UPDATE company_registry SET _is_generated = TRUE, updated_at = NOW() WHERE id = ANY(%s)",
                        (success_ids,)
                    )
                else:
                    cur2.execute(
                        "UPDATE company_registry SET _is_generated = TRUE, updated_at = NOW() WHERE id = ANY(%s) AND user_id = %s",
                        (success_ids, uid)
                    )
                conn2.commit()
                cur2.close(); conn2.close()

            invalidate_companies_cache(str(uid))
            _bulk_company_progress[batch_id]["status"] = "done"
        except Exception as e:
            _bulk_company_progress[batch_id]["status"] = "error"
            _bulk_company_progress[batch_id]["error"] = str(e)
        finally:
            _threading.Timer(300, lambda: _bulk_company_progress.pop(batch_id, None)).start()

    _threading.Thread(target=_run, daemon=True).start()
    return {"batch_id": batch_id, "total": total}

@router.get("/companies/bulk-progress/{batch_id}")
def get_bulk_company_progress(batch_id: str):
    prog = _bulk_company_progress.get(batch_id)
    if not prog:
        return {"status": "not_found"}
    return prog

@router.post("/companies/{row_id}/send")
def send_company_email(row_id: int, user_id: Optional[str] = Header(None, alias="X-User-Id")):
    """Generates and actually dispatches an email for a company record."""
    uid = normalize_user_id(user_id)
    if not check_daily_email_limit(user_id, 1):
        limit = get_daily_email_limit(user_id)
        raise HTTPException(status_code=400, detail=f"Daily Limit Exceeded: Sending this email would exceed your daily limit of {limit} emails. Please wait for the daily reset.")
        
    from app.services.email_service import send_email
    from app.api.drafts import markdown_to_html
    
    # 1. Generate the draft and lead record
    res = generate_company_draft(row_id, user_id=user_id)
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
        if uid:
            cur.execute("SELECT email, full_name, username FROM users WHERE id = %s", (uid,))
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
        from app.services.email_service import get_user_email_font, get_user_email_font_size
        success, error_msg, new_thread_id, new_rfc_message_id = send_email(
            to_email=lead['email'],
            subject=subject,
            html_content=markdown_to_html(body, font_family=get_user_email_font(uid), font_size=get_user_email_font_size(uid)),
            from_email=sender_email,
            from_name=sender_name,
            lead_id=lead_id,
            user_id=uid
        )
        
        if success:
            cur.execute("""
                UPDATE leads_raw 
                SET email_status = 'SENT', 
                    last_outreach_at = NOW(),
                    last_outreach_subject = %s,
                    first_outreach_subject = COALESCE(first_outreach_subject, %s),
                    first_outreach_at = COALESCE(first_outreach_at, NOW()),
                    gmail_thread_id = %s,
                    gmail_message_id = %s,
                    followup_status = 'ACTIVE',
                    followup_stage = 0,
                    is_responded = FALSE,
                    replied_at = NULL,
                    updated_at = NOW()
                WHERE id = %s
            """, (subject, subject, new_thread_id, new_rfc_message_id, lead_id))
            conn.commit()
            return {"success": True, "message": f"Email dispatched successfully to {lead['email']}"}
        else:
            raise HTTPException(status_code=500, detail=f"Dispatch failed: {error_msg}")

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
