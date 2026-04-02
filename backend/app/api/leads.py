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
               COALESCE(raw_payload->>'Designation', raw_payload->>'Role/Designation', raw_payload->>'designation', persona) as designation, 
               labels 
        FROM leads_raw 
        WHERE 1=1
    """
    params = []
    
    if user_id:
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
    
    query += " ORDER BY id DESC LIMIT %s OFFSET %s"
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
            "validation_status": r["validation_status"],
            "email_status": r.get("email_status"),
            "is_unsubscribed": r.get("is_unsubscribed", False),
            "created_at": r["created_at"].isoformat() if r["created_at"] else None
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
        lead["created_at"] = lead["created_at"].isoformat()
        
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
            # Flexible Mapping for Name
            name = (
                lead.get("Name") or lead.get("name") or 
                lead.get("Full Name") or lead.get("full_name") or 
                lead.get("Lead Name") or 
                f"{lead.get('first_name', '')} {lead.get('last_name', '')}".strip()
            )
            
            # Flexible Mapping for Email
            email = (
                lead.get("email") or lead.get("Email") or 
                lead.get("E-mail") or lead.get("Email Address") or 
                lead.get("Work Email")
            )

            if not email or not name:
                errors += 1
                continue

            # Flexible Mapping for other fields
            company = (
                lead.get("company_name") or lead.get("Company Name") or 
                lead.get("Company") or lead.get("Account") or lead.get("Organization")
            )
            linkedin = (
                lead.get("linkedin_url") or lead.get("LinkedIn URL") or 
                lead.get("LinkedIn") or lead.get("Profile URL") or lead.get("URL")
            )
            designation = (
                lead.get("Designation") or lead.get("Job Title") or 
                lead.get("Title") or lead.get("Role") or lead.get("Position") or 
                lead.get("Role/Designation")
            )
            city = lead.get("city") or lead.get("City") or lead.get("Location") or lead.get("Town")
            country = lead.get("country") or lead.get("Country") or lead.get("Nation")
            persona = lead.get("persona") or lead.get("Persona") or lead.get("Category") or "OTHER"
            phone = lead.get("phone") or lead.get("Phone") or lead.get("phone number") or lead.get("Mobile")

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
                        city, country, persona, phone, source, user_id, raw_payload
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (email) DO UPDATE SET
                        first_name = EXCLUDED.first_name,
                        last_name = EXCLUDED.last_name,
                        company_name = EXCLUDED.company_name,
                        linkedin_url = EXCLUDED.linkedin_url,
                        city = EXCLUDED.city,
                        country = EXCLUDED.country,
                        persona = EXCLUDED.persona,
                        phone = EXCLUDED.phone,
                        user_id = COALESCE(leads_raw.user_id, EXCLUDED.user_id),
                        raw_payload = EXCLUDED.raw_payload
                """, (
                    f_name, l_name, email, company, linkedin, 
                    city, country, persona, phone, "import", db_user_id, 
                    json.dumps(lead)
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
