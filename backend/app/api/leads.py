from fastapi import APIRouter, HTTPException, Header
from pydantic import BaseModel
from typing import Optional
import json
import psycopg2
import psycopg2.extras
from app.database import get_db_connection
from app.models.lead import get_lead_by_id, update_lead, get_activity_log, add_activity_log

router = APIRouter()

class LeadUpdate(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    company_name: Optional[str] = None
    industry: Optional[str] = None
    city: Optional[str] = None
    country: Optional[str] = None
    linkedin_url: Optional[str] = None
    persona: Optional[str] = None
    fit_score: Optional[int] = None
    campaign_id: Optional[int] = None
    family_office_name: Optional[str] = None
    source: Optional[str] = None
    remarks: Optional[str] = None

class LeadCreate(BaseModel):
    first_name: str
    last_name: Optional[str] = ""
    email: str
    company_name: Optional[str] = ""
    designation: Optional[str] = ""
    phone: Optional[str] = ""
    city: Optional[str] = ""
    country: Optional[str] = ""
    linkedin_url: Optional[str] = ""
    persona: Optional[str] = "OTHER"
    source: Optional[str] = "direct"
    remarks: Optional[str] = ""

from typing import List

class BulkLabelRequest(BaseModel):
    lead_ids: List[int]
    labels: List[str]

class LabelRemoveRequest(BaseModel):
    label: str

@router.get("/leads")
def get_leads(
    page: int = 1,
    search: Optional[str] = "",
    title: Optional[str] = "",
    persona: Optional[str] = "",
    company: Optional[str] = "",
    validation_status: Optional[str] = "",
    city: Optional[str] = "",
    country: Optional[str] = "",
    source: Optional[str] = "",
    per_page: int = 25,
    exclude_drafted: bool = False,
    exclude_source: Optional[str] = None,
    user_id: Optional[str] = Header(None, alias="X-User-Id")
):
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    
    # Dynamically extract designation if needed (to handle cases where schema update was blocked)
    query = """
        SELECT *, 
               COALESCE(designation, raw_payload->>'Designation', raw_payload->>'Role/Designation', raw_payload->>'designation', persona) as designation, 
               labels, remarks 
        FROM leads_raw 
        WHERE 1=1
    """
    params = []
    
    is_admin = (str(user_id).lower() == 'admin' or str(user_id) == '1')

    if is_admin:
        pass  # Admin sees all leads — no user_id filter applied
    elif user_id:
        query += " AND user_id = %s"
        params.append(user_id)
    else:
        query += " AND user_id IS NULL"


    if source:
        query += " AND source = %s"
        params.append(source)
        
    if exclude_source:
        query += " AND source != %s"
        params.append(exclude_source)

    is_bulk_context = (source in ('bulk', 'csv_import')) or (exclude_source == 'direct')
    if is_bulk_context:
        # 1. Must have a basic identity (Name and Company)
        query += " AND (first_name IS NOT NULL OR last_name IS NOT NULL) AND (COALESCE(first_name,'') != '' OR COALESCE(last_name,'') != '')"
        query += " AND company_name IS NOT NULL AND COALESCE(company_name,'') != ''"

        # 2. Block dummy / test records in name and email content
        bad_names = r'test|dummy|sample|example|unknown|admin|user|lead test|mock|noreply'
        query += f" AND COALESCE(first_name,'') !~* '{bad_names}'"
        query += f" AND COALESCE(last_name,'') !~* '{bad_names}'"

        # 3. Invalid Email Domains
        bad_domains = r'@(test|dummy|example|mailinator|fake|temp|noemail)\.(com|net|io|org)$'
        query += f" AND COALESCE(email,'') !~* '{bad_domains}'"

    if source == 'direct':
        # Apply strict filtering for Lead Pipeline ONLY
        
        # Dummy Names
        bad_names = r'test|dummy|sample|example|unknown|admin|user|lead test|mock|noreply'
        query += f" AND COALESCE(first_name,'') !~* '{bad_names}'"
        query += f" AND COALESCE(last_name,'') !~* '{bad_names}'"

        # Invalid Email Domains
        bad_domains = r'@(test|dummy|example|mailinator|fake|temp|noemail)\.(com|net|io|org)$'
        query += f" AND COALESCE(email,'') !~* '{bad_domains}'"

        # Active Role Filter
        bad_titles = r'\b(ex|former|previous|past|advisor|retired|consultant|board member)\b'
        query += f" AND COALESCE(designation, raw_payload->>'Designation', raw_payload->>'Role/Designation', raw_payload->>'designation', persona, '') !~* '{bad_titles}'"
        
    # Global Blacklist Exclusion
    query += " AND (is_unsubscribed IS NULL OR is_unsubscribed = FALSE)"
    query += " AND email NOT IN (SELECT email FROM unsubscribe_list)"

    # ──────────────────────────────────────────────────────────────────────────

    if exclude_drafted:
        query += " AND (email_status IS NULL OR email_status = '')"
    
    if search:
        query += " AND (first_name ILIKE %s OR last_name ILIKE %s OR email ILIKE %s OR company_name ILIKE %s OR raw_payload->>'current_title' ILIKE %s OR persona ILIKE %s OR phone ILIKE %s)"
        s = f"%{search}%"
        params.extend([s, s, s, s, s, s, s])

    if title:
        titles = [t.strip() for t in title.split(',') if t.strip()]
        if titles:
            title_conditions = " OR ".join(["raw_payload->>'current_title' ILIKE %s"] * len(titles))
            query += f" AND ({title_conditions})"
            for t in titles:
                params.append(f"%{t}%")
        
    if persona:
        query += " AND persona = %s"
        params.append(persona)
        
    if company:
        query += " AND company_name ILIKE %s"
        params.append(f"%{company}%")
        
    if validation_status:
        query += " AND validation_status = %s"
        params.append(validation_status)

        
    # count total - handle multi-line select correctly
    count_query = f"SELECT COUNT(*) FROM ({query}) as total_count"
    cur.execute(count_query, tuple(params))
    total = cur.fetchone()[0]
    
    query += " ORDER BY created_at DESC LIMIT %s OFFSET %s"
    params.extend([per_page, (page - 1) * per_page])
    cur.execute(query, tuple(params))
    leads = cur.fetchall()
    
    cur.execute(query, tuple(params))
    rows = cur.fetchall()
    
    cur.close()
    conn.close()

    leads = []
    for r in rows:
        payload = r.get("raw_payload")
        if isinstance(payload, str):
            try:
                payload = json.loads(payload)
            except:
                payload = {}
        elif not payload:
            payload = {}

        city = r.get("city") or payload.get("city") or ""
        country = r.get("country") or payload.get("country") or ""

        # Robust phone extraction
        phone = r.get("phone")
        if not phone and payload and "phones" in payload:
            phones = payload.get("phones")
            if phones and isinstance(phones, list) and len(phones) > 0:
                phone = phones[0].get("number")
 
        leads.append({
            "id": r["id"],
            "name": f"{r['first_name'] or ''} {r['last_name'] or ''}".strip(),
            "first_name": r["first_name"],
            "last_name": r["last_name"],
            "email": r["email"],
            "phone": phone or r.get("phone") or "",
            "persona": r["persona"],
            "fit_score": r.get("fit_score", 0),
            "family_office_name": r.get("family_office_name", ""),
            "company_name": r["company_name"],
            "industry": r.get("industry", ""),
            "city": city,
            "country": country,
            "linkedin": r["linkedin_url"],
            "source": r.get("source", ""),
            "validation_status": r["validation_status"],
            "email_status": r.get("email_status"),
            "is_unsubscribed": r.get("is_unsubscribed", False),
            "remarks": r.get("remarks", ""),
            "created_at": r["created_at"].isoformat() + "Z" if r["created_at"] else None
        })

    return {
        "leads": leads,
        "total": total
    }


@router.get("/leads/{lead_id}")
def get_lead_detail(lead_id: int, user_id: Optional[str] = Header(None, alias="X-User-Id")):
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    
    if user_id:
        cur.execute("SELECT * FROM leads_raw WHERE id = %s AND user_id = %s", (lead_id, user_id))
    else:
        cur.execute("SELECT * FROM leads_raw WHERE id = %s AND user_id IS NULL", (lead_id,))
        
    row = cur.fetchone()
    cur.close()
    conn.close()

    if not row:
        return {"error": "Lead not found"}
    
    # Convert to mutable dict
    lead = dict(row)
    
    # Enrich with payload if needed
    payload = lead.get("raw_payload")
    if isinstance(payload, str):
        try:
            payload = json.loads(payload)
        except:
            payload = {}
    elif not payload:
        payload = {}
        
    city = lead.get("city") or payload.get("city") or ""
    country = lead.get("country") or payload.get("country") or ""
    
    lead["city"] = city
    lead["country"] = country
    
    # Robust phone extraction fallback for details
    phone = lead.get("phone")
    if not phone and payload and "phones" in payload:
        phones = payload.get("phones")
        if phones and isinstance(phones, list) and len(phones) > 0:
            phone = phones[0].get("number")
    lead["phone"] = phone or payload.get("phone") or ""
    
    # ensure job title is included (designation)
    if payload:
        lead["designation"] = payload.get("current_title", "")
        
    # Serialize datetime
    if lead.get("created_at"):
        lead["created_at"] = lead["created_at"].isoformat() + "Z"
        
    # Normalize email_draft content to handle literal escapes
    if lead.get("email_draft"):
        lead["email_draft"] = lead["email_draft"].replace("\\n", "\n").replace("\\r\\n", "\n")
    
    return lead

@router.patch("/leads/{lead_id}")
def update_lead_endpoint(lead_id: int, req: LeadUpdate, user_id: Optional[str] = Header(None, alias="X-User-Id")):

    update_data = req.dict(exclude_unset=True)
    if not update_data:
        return {"message": "No changes provided"}
    
    success = update_lead(lead_id, update_data)
    if success:
        add_activity_log(lead_id, "UPDATE_LEAD", f"Updated fields: {', '.join(update_data.keys())}", "admin")
        return {"message": "Lead updated successfully"}
    return {"error": "Failed to update lead"}

@router.get("/leads/{lead_id}/activity")
def get_lead_activity(lead_id: int):
    logs = get_activity_log(lead_id)
    return logs

@router.post("/leads")
def create_manual_lead(req: LeadCreate, user_id: Optional[str] = Header(None, alias="X-User-Id")):
    from app.models.lead import insert_lead
    
    payload = {
        "designation": req.designation,
        "city": req.city,
        "country": req.country,
        "phone": req.phone,
        "manual_entry": True
    }
    
    try:
        insert_lead(
            req.first_name,
            req.last_name,
            req.email,
            "", # domain
            req.linkedin_url,
            req.company_name,
            req.source or "direct",
            payload,
            fit_score=0,
            persona=req.persona or "OTHER",
            phone=req.phone,
            user_id=user_id
        )
        return {"message": "Lead created successfully"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/leads/bulk-labels")
def bulk_labels(req: BulkLabelRequest):
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        cur.execute("""
            UPDATE leads_raw 
            SET labels = (
                SELECT ARRAY_AGG(DISTINCT l) 
                FROM UNNEST(COALESCE(labels, '{}') || %s) l
            )
            WHERE id = ANY(%s)
        """, (req.labels, req.lead_ids))
        
        conn.commit()
        add_activity_log(None, "LABEL_ASSIGNED", f"Assigned labels {req.labels} to {len(req.lead_ids)} leads", "admin")
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        cur.close()
        conn.close()
    
    return {"message": "Labels assigned successfully"}

@router.post("/leads/{lead_id}/remove-label")
def remove_lead_label(lead_id: int, req: LabelRemoveRequest):
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        cur.execute("""
            UPDATE leads_raw 
            SET labels = ARRAY_REMOVE(labels, %s)
            WHERE id = %s
        """, (req.label, lead_id))
        
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        cur.close()
        conn.close()
    
class BulkUpdateSourceReq(BaseModel):
    lead_ids: List[int]
    source: str

@router.post("/leads/bulk-approve")
def bulk_approve(req: List[int]):
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("UPDATE leads_raw SET source = 'direct' WHERE id = ANY(%s)", (req,))
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        cur.close()
        conn.close()
    return {"message": "Leads approved and moved to pipeline"}

@router.post("/leads/{lead_id}/unsubscribe")
def unsubscribe_lead(lead_id: int):
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    try:
        cur.execute("SELECT email, source FROM leads_raw WHERE id = %s", (lead_id,))
        lead = cur.fetchone()
        if not lead:
            raise HTTPException(status_code=404, detail="Lead not found")
        
        cur.execute("UPDATE leads_raw SET is_unsubscribed = TRUE WHERE id = %s", (lead_id,))
        
        if lead['email']:
            cur.execute("""
                INSERT INTO unsubscribe_list (email, reason, source)
                VALUES (%s, 'Manual opt-out from lead details', %s)
                ON CONFLICT (email) DO NOTHING
            """, (lead['email'], lead['source']))
        
        conn.commit()
        add_activity_log(lead_id, "UNSUBSCRIBED", "Lead opted out and email blacklisted manually", "admin")
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        cur.close()
        conn.close()
        
    return {"message": "Lead unsubscribed and blacklisted successfully"}

@router.post("/leads/bulk-delete")
def bulk_delete(req: List[int]):
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("DELETE FROM leads_raw WHERE id = ANY(%s)", (req,))
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        cur.close()
        conn.close()
    return {"message": "Leads rejected and deleted"}
@router.post("/leads/bulk-import")
def bulk_import(
    leads: List[dict],
    user_id: Optional[str] = Header(None, alias="X-User-Id")
):
    """
    Import a list of leads with flexible header mapping.
    Email and Name are the only core requirements.
    """
    conn = get_db_connection()
    cur = conn.cursor()
    inserted = 0
    errors = 0
    skipped = 0

    try:
        db_user_id = None
        if user_id:
            try:
                db_user_id = int(user_id)
            except:
                pass

        for lead in leads:
            # Normalize keys to catch variations like "E- Mail", "First Name", "Investor Name"
            norm_lead = {str(k).lower().replace(" ", "").replace("-", ""): str(v).strip() for k, v in lead.items() if v}

            # Flexible Mapping for Name
            name = (
                norm_lead.get("name") or norm_lead.get("fullname") or 
                norm_lead.get("leadname") or norm_lead.get("investorname") or
                f"{norm_lead.get('firstname', '')} {norm_lead.get('lastname', '')}".strip()
            )
            
            # Flexible Mapping for Email
            email = (
                norm_lead.get("email") or norm_lead.get("emailaddress") or 
                norm_lead.get("workemail")
            )

            if not email or not name:
                errors += 1
                continue

            # Flexible Mapping for other fields
            company = (
                norm_lead.get("companyname") or norm_lead.get("company") or 
                norm_lead.get("account") or norm_lead.get("organization") or
                norm_lead.get("client")
            )
            linkedin = (
                norm_lead.get("linkedinurl") or norm_lead.get("linkedin") or 
                norm_lead.get("profileurl") or norm_lead.get("url")
            )
            designation = (
                norm_lead.get("designation") or norm_lead.get("role") or 
                norm_lead.get("title") or norm_lead.get("jobtitle") or norm_lead.get("position")
            )
            city = norm_lead.get("city") or norm_lead.get("location") or norm_lead.get("town") or norm_lead.get("place")
            country = norm_lead.get("country") or norm_lead.get("nation")
            persona = norm_lead.get("persona") or norm_lead.get("category") or "OTHER"
            phone = norm_lead.get("phone") or norm_lead.get("phonenumber") or norm_lead.get("mobile")

            # Data Formatting
            name_parts = name.split(" ", 1)
            f_name = name_parts[0] if name_parts else ""
            l_name = name_parts[1] if len(name_parts) > 1 else ""
            
            # Create a savepoint for each lead to prevent global transaction abortion
            cur.execute("SAVEPOINT lead_savepoint")
            try:
                # Optimized query: only using columns we know exist for sure
                cur.execute("""
                    INSERT INTO leads_raw (
                        first_name, last_name, email, company_name, linkedin_url, 
                        city, country, persona, phone, source, user_id, raw_payload, remarks
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (email) DO UPDATE SET
                        first_name = EXCLUDED.first_name,
                        last_name = EXCLUDED.last_name,
                        company_name = EXCLUDED.company_name,
                        linkedin_url = EXCLUDED.linkedin_url,
                        city = EXCLUDED.city,
                        country = EXCLUDED.country,
                        persona = EXCLUDED.persona,
                        phone = EXCLUDED.phone,
                        source = EXCLUDED.source,
                        user_id = COALESCE(EXCLUDED.user_id, leads_raw.user_id),
                        raw_payload = EXCLUDED.raw_payload,
                        remarks = COALESCE(EXCLUDED.remarks, leads_raw.remarks)
                """, (
                    f_name, l_name, email, company, linkedin, 
                    city, country, persona, phone, "csv_import", db_user_id, 
                    json.dumps(lead), lead.get("remarks", "")
                ))
                if cur.rowcount > 0:
                    inserted += 1
                else:
                    skipped += 1
                cur.execute("RELEASE SAVEPOINT lead_savepoint")
            except Exception as e:
                cur.execute("ROLLBACK TO SAVEPOINT lead_savepoint")
                print(f"Bulk import individual error: {e}")
                errors += 1
                continue
        
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        cur.close()
        conn.close()

    return {"message": f"Successfully processed {inserted + skipped} leads. ({inserted} new/updated, {errors} skipped due to invalid email or name)"}


class GSheetImportRequest(BaseModel):
    url: str

@router.post("/leads/import-gsheet")
def import_from_gsheet(
    req: GSheetImportRequest,
    user_id: Optional[str] = Header(None, alias="X-User-Id")
):
    import requests as http_requests
    import csv, io, re

    raw_url = req.url.strip()
    
    if "/d/" not in raw_url:
        raise HTTPException(status_code=400, detail="Invalid Google Sheet URL format.")
    
    doc_id = raw_url.split("/d/")[1].split("/")[0]
    
    # Extract gid (tab ID)
    gid_match = re.search(r"[?&#]gid=(\d+)", raw_url)
    gid = gid_match.group(1) if gid_match else "0"
    
    export_url = f"https://docs.google.com/spreadsheets/d/{doc_id}/export?format=csv&gid={gid}"
    
    try:
        resp = http_requests.get(export_url, allow_redirects=True, timeout=15)
        content_type = resp.headers.get("Content-Type", "")
        
        if resp.status_code == 200 and "csv" in content_type.lower():
            reader = csv.DictReader(io.StringIO(resp.text))
            
            # Use our generous backend bulk-import logic!
            return bulk_import([dict(row) for row in reader], user_id)
            
        else:
            raise HTTPException(status_code=400, detail="Sheet is fully private or not found. Please make sure 'Anyone with the link can view'.")
            
    except Exception as e:
        if isinstance(e, HTTPException):
            raise
        raise HTTPException(status_code=500, detail=str(e))
