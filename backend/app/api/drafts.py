from fastapi import APIRouter, Header
from pydantic import BaseModel
import traceback
from typing import Optional, List

from app.models.lead import get_lead_by_id
from app.models.draft import insert_draft
from app.database import get_db_connection
from app.services.llm_services import EmailGenerator
import psycopg2.extras

router = APIRouter()

class DraftRequest(BaseModel):
    lead_id: int

class ApproveRequest(BaseModel):
    approved_by: Optional[str] = "admin"

class RejectRequest(BaseModel):
    rejected_reason: Optional[str] = ""

class BulkDraftRequest(BaseModel):
    lead_ids: List[int]

class BulkSendRequest(BaseModel):
    lead_ids: List[int]

def normalize_lead(lead):
    if isinstance(lead, dict):
        return lead
    if isinstance(lead, tuple):
        return {
            "first_name": lead[1],
            "last_name": lead[2],
            "company_name": lead[3]
        }
    return {}

# --- Generate Draft ---
# Supports both /generate-draft (user prompt) and /generate-email (frontend Axios)
@router.post("/generate-draft")
@router.post("/generate-email")
def generate_draft(req: DraftRequest, user_id: Optional[str] = Header(None, alias="X-User-Id")):
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        
        if user_id:
            cur.execute("SELECT * FROM leads_raw WHERE id = %s AND user_id = %s", (req.lead_id, user_id))
        else:
            cur.execute("SELECT * FROM leads_raw WHERE id = %s AND user_id IS NULL", (req.lead_id,))
            
        lead = cur.fetchone()

        if not lead:
            return {"error": "Lead not found"}
        lead = normalize_lead(lead)
        
        generator = EmailGenerator()
        email_data = generator.generate_email(lead)
        
        subject = email_data.get("subject", "Following up")
        body = email_data.get("body", "Hello, we would love to connect.")
        
        # Ensure proper dynamic greeting in body only
        lines = body.split('\n')
        if lines and any(g in lines[0].lower() for g in ['hi ', 'hello ', 'dear ']):
            lines = lines[1:]
        clean_body = '\n'.join(lines).lstrip()
        
        # Inject personalized greeting
        first_name = lead.get('first_name', 'there')
        email_content = f"Subject: {subject}\n\nHi {first_name},\n\n{clean_body}"
        
        # update leads_raw.email_draft and email_status='PENDING_APPROVAL'
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            UPDATE leads_raw 
            SET email_draft = %s, email_status = 'PENDING_APPROVAL', updated_at = NOW() 
            WHERE id = %s
        """, (email_content, req.lead_id))
        conn.commit()
        cur.close()
        conn.close()
        
        # Log activity
        try:
            from app.models.lead import add_activity_log
            add_activity_log(req.lead_id, "DRAFT_GENERATED", "AI email draft generated and saved for review", "system")
        except:
            pass

        return {
            "message": "Draft generated",
            "draft_id": req.lead_id, # frontend uses lead ID as draft ID
            "subject": subject,
            "body": body
        }
    except Exception as e:
        traceback.print_exc()
        return {"error": str(e)}

# --- Fetch Drafts ---
# Supports both /pending-drafts (user prompt) and /emails (frontend Axios)
@router.get("/pending-drafts")
@router.get("/emails")
def get_pending_drafts(page: int = 1, status: Optional[str] = None, per_page: int = 20, user_id: Optional[str] = Header(None, alias="X-User-Id")):
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    
    # Base condition
    where_clause = "WHERE email_draft IS NOT NULL"
    params = []
    
    if user_id:
        where_clause += " AND user_id = %s"
        params.append(user_id)
    else:
        where_clause += " AND user_id IS NULL"

    query = f"""
        SELECT id, first_name, last_name, email, email_draft, email_status, company_name, persona, fit_score, updated_at 
        FROM leads_raw 
        {where_clause}
    """

    if status:
        query += " AND email_status = %s"
        params.append(status)
        
    query += " ORDER BY COALESCE(updated_at, created_at) DESC LIMIT %s OFFSET %s"
    params.extend([per_page, (page - 1) * per_page])
    
    cur.execute(query, tuple(params))
    rows = cur.fetchall()
    
    # count total
    count_query = f"SELECT COUNT(*) FROM leads_raw {where_clause}"
    count_params = [user_id] if user_id else []
    if status:
        count_query += " AND email_status = %s"
        count_params.append(status)
    cur.execute(count_query, tuple(count_params))

    total = cur.fetchone()[0]
    
    cur.close()
    conn.close()

    drafts = []
    for r in rows:
        draft_content = r["email_draft"] or ""
        # Normalize literal \n to real newlines for consistent parsing
        draft_content = draft_content.replace("\\n", "\n").replace("\\r\\n", "\n")
            
        subject = ""
        body = draft_content
        if "Subject: " in draft_content:
            # First split by double newline to separate subject line from body
            parts = draft_content.split("\n\n", 1)
            # If no double newline, maybe it's just a single newline after Subject:
            if len(parts) == 1:
                parts = draft_content.split("\n", 1)
                
            subject = parts[0].replace("Subject: ", "").strip()
            if len(parts) > 1:
                body = parts[1].strip()
        elif "Subject:" in draft_content:
            # Handle missing space after Subject:
            parts = draft_content.split("\n\n", 1)
            if len(parts) == 1:
                parts = draft_content.split("\n", 1)
            subject = parts[0].replace("Subject:", "").strip()
            if len(parts) > 1:
                body = parts[1].strip()
                
        drafts.append({
            "id": r["id"],
            "lead_id": r["id"],
            "lead_name": f"{r['first_name'] or ''} {r['last_name'] or ''}".strip(),
            "lead_email": r["email"],
            "company_name": r["company_name"],
            "persona": r["persona"],
            "fit_score": r.get("fit_score", 0),
            "subject": subject,
            "body": body,
            "status": r["email_status"] or "PENDING_APPROVAL",
            "performance": {"opens": 0, "clicks": 0}, # Placeholders
            "verifier": "admin" if r["email_status"] in ["APPROVED", "SENT"] else None,
            "updated_at": r.get("updated_at", "").isoformat() if r.get("updated_at") else ""
        })

    return {
        "drafts": drafts,
        "total": total
    }

class RefineRequest(BaseModel):
    instruction: str
    body: Optional[str] = None
    subject: Optional[str] = None

@router.post("/refine-email/{draft_id}")
def refine_email_endpoint(draft_id: int, req: RefineRequest, user_id: Optional[str] = Header(None, alias="X-User-Id")):
    try:
        # Get lead info to provide context to LLM
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        
        if user_id:
            cur.execute("SELECT * FROM leads_raw WHERE id = %s AND user_id = %s", (draft_id, user_id))
        else:
            cur.execute("SELECT * FROM leads_raw WHERE id = %s AND user_id IS NULL", (draft_id,))
            
        lead = cur.fetchone()

        if not lead:
            return {"error": "Lead not found"}
            
        generator = EmailGenerator()
        refined_data = generator.refine_email(req.subject, req.body, req.instruction)
        
        # Update DB
        new_content = f"Subject: {refined_data['subject']}\n\n{refined_data['body']}"
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("UPDATE leads_raw SET email_draft = %s, updated_at = NOW() WHERE id = %s", (new_content, draft_id))
        conn.commit()
        cur.close()
        conn.close()
        
        return {
            "subject": refined_data["subject"],
            "body": refined_data["body"]
        }
        
    except Exception as e:
        traceback.print_exc()
        return {"error": str(e)}

@router.post("/approve-draft/{draft_id}")
@router.post("/approve-email/{draft_id}")
def approve_draft(draft_id: int, req: Optional[ApproveRequest] = None, user_id: Optional[str] = Header(None, alias="X-User-Id")):
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    # Ensure a draft exists before approving
    if user_id:
        cur.execute("SELECT first_name, last_name, company_name, email_draft, domain FROM leads_raw WHERE id = %s AND user_id = %s", (draft_id, user_id))
    else:
        cur.execute("SELECT first_name, last_name, company_name, email_draft, domain FROM leads_raw WHERE id = %s AND user_id IS NULL", (draft_id,))
        
    lead = cur.fetchone()

    
    if lead and not lead.get('email_draft'):
        from app.services.llm_services import EmailGenerator
        generator = EmailGenerator()
        email_data = generator.generate_email(dict(lead))
        subject = email_data.get("subject", "Following up")
        body = email_data.get("body", "Hello, we would love to connect.")
        
        lines = body.split('\n')
        if lines and any(g in lines[0].lower() for g in ['hi ', 'hello ', 'dear ']):
            lines = lines[1:]
        clean_body = '\n'.join(lines).lstrip()
        email_content = f"Subject: {subject}\n\nHi {{first_name}},\n\n{clean_body}"
        
        cur.execute("""
            UPDATE leads_raw 
            SET email_draft = REPLACE(%s, '{{first_name}}', COALESCE(NULLIF(first_name, ''), 'there')),
                email_status = 'APPROVED', updated_at = NOW()
            WHERE id = %s
        """, (email_content, draft_id))
    else:
        cur.execute(
            "UPDATE leads_raw SET email_status = 'APPROVED', updated_at = NOW() WHERE id = %s",
            (draft_id,)
        )
        
    conn.commit()
    cur.close()
    conn.close()
    
    # Log activity
    from app.models.lead import add_activity_log
    add_activity_log(draft_id, "EMAIL_APPROVED", "Email draft approved by admin", "admin")
    
    return {"status": "approved", "message": "Draft approved successfully"}

@router.post("/reject-email/{draft_id}")
def reject_draft(draft_id: int, req: Optional[RejectRequest] = None, user_id: Optional[str] = Header(None, alias="X-User-Id")):
    conn = get_db_connection()
    cur = conn.cursor()
    
    where_clause = "WHERE id = %s AND user_id = %s" if user_id else "WHERE id = %s AND user_id IS NULL"
    params = (draft_id, user_id) if user_id else (draft_id,)
    
    cur.execute(
        f"UPDATE leads_raw SET email_status = 'REJECTED', updated_at = NOW() {where_clause}",
        params
    )

    conn.commit()
    cur.close()
    conn.close()
    
    from app.models.lead import add_activity_log
    add_activity_log(draft_id, "EMAIL_REJECTED", f"Reason: {req.rejected_reason if req else ''}", "admin")
    
    return {"status": "rejected", "message": "Draft rejected"}

@router.post("/approve-bulk-domain-drafts")
def approve_bulk_domain_drafts(req: BulkDraftRequest, user_id: Optional[str] = Header(None, alias="X-User-Id")):
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        
        if not req.lead_ids:
            return {"message": "No leads provided"}
            
        format_strings = ','.join(['%s'] * len(req.lead_ids))
        where_clause = f"WHERE id IN ({format_strings}) AND user_id = %s" if user_id else f"WHERE id IN ({format_strings}) AND user_id IS NULL"
        params = tuple(req.lead_ids) + ((user_id,) if user_id else ())
        
        cur.execute(f"SELECT * FROM leads_raw {where_clause}", params)

        leads = cur.fetchall()
        
        # Group leads
        groups = {}
        for row in leads:
            lead_dict = dict(row)
            domain = lead_dict.get('domain')
            company = lead_dict.get('company_name')
            group_key = domain if domain else (company if company else str(lead_dict['id']))
            group_key = group_key.lower().strip()
            
            if group_key not in groups:
                groups[group_key] = []
            groups[group_key].append(lead_dict)
            
        total_leads_updated = 0
        total_groups = len(groups)
        
        from app.models.lead import add_activity_log
        from app.services.llm_services import EmailGenerator
        generator = EmailGenerator()
        
        for key, group_leads in groups.items():
            first_lead = group_leads[0]
            group_ids = [l['id'] for l in group_leads]
            id_format = ','.join(['%s'] * len(group_ids))
            
            # If ANY lead in group has no draft, ensure we have one to apply
            # Or if the first lead has no draft, generate it
            email_content = first_lead.get("email_draft")
            if not email_content:
                email_data = generator.generate_email(normalize_lead(first_lead))
                subject = email_data.get("subject", "Following up")
                body = email_data.get("body", "Hello, we would love to connect.")
                
                lines = body.split('\n')
                if lines and any(g in lines[0].lower() for g in ['hi ', 'hello ', 'dear ']):
                    lines = lines[1:]
                clean_body = '\n'.join(lines).lstrip()
                email_content = f"Subject: {subject}\n\nHi {{first_name}},\n\n{clean_body}"
            
            cur.execute(f"""
                UPDATE leads_raw 
                SET email_draft = CASE 
                    WHEN email_draft IS NULL THEN REPLACE(%s, '{{first_name}}', COALESCE(NULLIF(first_name, ''), 'there'))
                    ELSE email_draft 
                END,
                email_status = 'APPROVED', updated_at = NOW() 
                WHERE id IN ({id_format})
            """, (email_content, *group_ids))
            
            # Log one activity per group/domain
            add_activity_log(None, "BULK_DOMAIN_APPROVE", f"Approved drafts for domain/group {key} ({len(group_ids)} leads)", "admin")
            
            total_leads_updated += len(group_ids)
            
        conn.commit()
        cur.close()
        conn.close()
        
        return {
            "message": f"Approved {total_groups} distinct domain draft groups ({total_leads_updated} leads).",
            "groups_processed": total_groups,
            "leads_updated": total_leads_updated
        }
    except Exception as e:
        traceback.print_exc()
        return {"error": str(e)}

@router.post("/send-approved-batch")
def send_approved_batch(user_id: Optional[str] = Header(None, alias="X-User-Id")):
    conn = get_db_connection()
    cur = conn.cursor()
    
    where_clause = "WHERE email_status = 'APPROVED' AND user_id = %s" if user_id else "WHERE email_status = 'APPROVED' AND user_id IS NULL"
    params = (user_id,) if user_id else ()
    
    # Get all approved lead IDs for THIS user
    cur.execute(f"SELECT id FROM leads_raw {where_clause}", params)
    ids = [r[0] for r in cur.fetchall()]
    
    cur.execute(
        f"UPDATE leads_raw SET email_status = 'SENT', updated_at = NOW() {where_clause}",
        params
    )

    updated = cur.rowcount
    conn.commit()
    cur.close()
    conn.close()
    
    from app.models.lead import add_activity_log
    for lid in ids:
        add_activity_log(lid, "EMAIL_SENT", "Email dispatched in batch", "system")
        
    return {"message": f"Successfully sent {updated} approved emails."}

@router.post("/generate-bulk-domain-drafts")
def generate_bulk_domain_drafts(req: BulkDraftRequest, user_id: Optional[str] = Header(None, alias="X-User-Id")):
    try:
        from app.models.lead import get_lead_by_id
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        
        if not req.lead_ids:
            return {"message": "No leads provided"}
            
        format_strings = ','.join(['%s'] * len(req.lead_ids))
        where_clause = f"WHERE id IN ({format_strings}) AND user_id = %s" if user_id else f"WHERE id IN ({format_strings}) AND user_id IS NULL"
        params = tuple(req.lead_ids) + ((user_id,) if user_id else ())

        cur.execute(f"SELECT * FROM leads_raw {where_clause}", params)

        leads = cur.fetchall()
        
        # Group leads
        groups = {}
        for row in leads:
            lead_dict = dict(row)
            domain = lead_dict.get('domain')
            company = lead_dict.get('company_name')
            group_key = domain if domain else (company if company else str(lead_dict['id']))
            group_key = group_key.lower().strip()
            
            if group_key not in groups:
                groups[group_key] = []
            groups[group_key].append(lead_dict)
            
        generator = EmailGenerator()
        total_leads_updated = 0
        total_groups = len(groups)
        
        for key, group_leads in groups.items():
            first_lead = group_leads[0]
            
            # Generate email using first lead as context
            email_data = generator.generate_email(normalize_lead(first_lead))
            subject = email_data.get("subject", "Following up")
            body = email_data.get("body", "Hello, we would love to connect.")
            
            # Ensure proper dynamic greeting
            lines = body.split('\n')
            if lines and any(g in lines[0].lower() for g in ['hi ', 'hello ', 'dear ']):
                lines = lines[1:]
            clean_body = '\n'.join(lines).lstrip()
            email_content = f"Subject: {subject}\n\nHi {{first_name}},\n\n{clean_body}"
            
            # Update all leads in this group
            group_ids = [l['id'] for l in group_leads]
            id_format = ','.join(['%s'] * len(group_ids))
            
            cur.execute(f"""
                UPDATE leads_raw 
                SET email_draft = REPLACE(%s, '{{first_name}}', COALESCE(NULLIF(first_name, ''), 'there')), 
                    email_status = 'PENDING_APPROVAL', updated_at = NOW() 
                WHERE id IN ({id_format})
            """, (email_content, *group_ids))
            
            total_leads_updated += len(group_ids)
            
        conn.commit()
        cur.close()
        conn.close()

        # Log bulk activity
        try:
            from app.models.lead import add_activity_log
            add_activity_log(None, "BULK_DRAFT_GENERATE", f"Generated domain-wise drafts for {total_leads_updated} leads across {total_groups} groups", "admin")
        except:
            pass
        
        return {
            "message": f"Generated {total_groups} distinct domain drafts and applied to {total_leads_updated} leads.",
            "groups_processed": total_groups,
            "leads_updated": total_leads_updated
        }
    except Exception as e:
        traceback.print_exc()
        return {"error": str(e)}

@router.post("/send-bulk-domain-emails")
def send_bulk_domain_emails(req: BulkSendRequest, user_id: Optional[str] = Header(None, alias="X-User-Id")):
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        
        if not req.lead_ids:
            return {"message": "No leads provided"}
            
        format_strings = ','.join(['%s'] * len(req.lead_ids))
        where_clause = f"WHERE id IN ({format_strings}) AND user_id = %s" if user_id else f"WHERE id IN ({format_strings}) AND user_id IS NULL"
        params = tuple(req.lead_ids) + ((user_id,) if user_id else ())

        cur.execute(f"SELECT * FROM leads_raw {where_clause}", params)

        leads = cur.fetchall()
        
        groups = {}
        for row in leads:
            lead_dict = dict(row)
            domain = lead_dict.get('domain')
            company = lead_dict.get('company_name')
            group_key = domain if domain else (company if company else str(lead_dict['id']))
            group_key = group_key.lower().strip()
            
            if group_key not in groups:
                groups[group_key] = []
            groups[group_key].append(lead_dict)
            
        generator = EmailGenerator()
        total_leads_updated = 0
        total_groups = len(groups)
        
        from app.models.lead import add_activity_log
        
        for key, group_leads in groups.items():
            first_lead = group_leads[0]
            
            # If draft already exists, use it. Otherwise generate.
            email_content = first_lead.get("email_draft")
            if not email_content:
                email_data = generator.generate_email(normalize_lead(first_lead))
                subject = email_data.get("subject", "Following up")
                body = email_data.get("body", "Hello, we would love to connect.")
                
                lines = body.split('\n')
                if lines and any(g in lines[0].lower() for g in ['hi ', 'hello ', 'dear ']):
                    lines = lines[1:]
                clean_body = '\n'.join(lines).lstrip()
                email_content = f"Subject: {subject}\n\nHi {{first_name}},\n\n{clean_body}"
                
            group_ids = [l['id'] for l in group_leads]
            id_format = ','.join(['%s'] * len(group_ids))
            
            cur.execute(f"""
                UPDATE leads_raw 
                SET email_draft = REPLACE(%s, '{{first_name}}', COALESCE(NULLIF(first_name, ''), 'there')), 
                    email_status = 'SENT', updated_at = NOW() 
                WHERE id IN ({id_format})
            """, (email_content, *group_ids))
            
            # Log one activity per domain group to avoid dashboard clutter
            add_activity_log(None, "BULK_DOMAIN_SEND", f"Sent emails to group {key} ({len(group_ids)} leads)", "admin")
            
            total_leads_updated += len(group_ids)
            
        conn.commit()
        cur.close()
        conn.close()
        
        return {
            "message": f"Sent {total_groups} distinct domain emails to {total_leads_updated} leads.",
            "groups_processed": total_groups,
            "leads_updated": total_leads_updated
        }
    except Exception as e:
        traceback.print_exc()
        return {"error": str(e)}