from fastapi import APIRouter, Header
from pydantic import BaseModel
import traceback
from typing import Optional, List
from concurrent.futures import ThreadPoolExecutor, as_completed

from app.models.lead import get_lead_by_id
from app.models.draft import insert_draft
from app.database import get_db_connection
from app.services.llm_services import EmailGenerator
import psycopg2.extras
import logging

router = APIRouter()
logger = logging.getLogger(__name__)

def normalize_user_id(user_id: Optional[str]) -> str:
    """Normalizes the user ID from the header to a valid database ID string."""
    if not user_id or user_id.strip() == "" or str(user_id).lower() == "admin":
        return "1"
    return str(user_id)

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

class BulkActionRequest(BaseModel):
    lead_ids: List[int]
    action: str  # APPROVED, ARCHIVED, SENT, REJECTED
    reason: Optional[str] = None

@router.post("/emails/bulk-action")
def bulk_email_action(req: BulkActionRequest, user_id: Optional[str] = Header(None, alias="X-User-Id")):
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        
        if not req.lead_ids:
            return {"message": "No leads provided"}
            
        format_strings = ','.join(['%s'] * len(req.lead_ids))
        where_params = tuple(req.lead_ids)
        
        # User restriction
        user_clause = ""
        if user_id and user_id != "admin":
            user_clause = " AND user_id = %s"
            where_params += (user_id,)
        elif user_id == "admin":
            pass
        else:
            user_clause = " AND user_id IS NULL"

        # Update status
        cur.execute(f"UPDATE leads_raw SET email_status = %s, updated_at = NOW() WHERE id IN ({format_strings}) {user_clause}", (req.action, *where_params))
        
        # Log activity
        from app.models.lead import add_activity_log
        for lid in req.lead_ids:
            add_activity_log(lid, f"BULK_{req.action}", f"Bulk {req.action.lower()} action applied. {f'Reason: {req.reason}' if req.reason else ''}", "admin")

        conn.commit()
        cur.close()
        conn.close()
        
        return {"message": f"Successfully updated {len(req.lead_ids)} leads to {req.action}"}
    except Exception as e:
        traceback.print_exc()
        return {"error": str(e)}

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

def get_user_name(user_id):
    if not user_id:
        return "the team"
    try:
        from app.database import get_db_connection
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        cur.execute("SELECT full_name, username FROM users WHERE id = %s", (user_id,))
        user = cur.fetchone()
        cur.close()
        conn.close()
        if user:
            return user['full_name'] or user['username']
    except:
        pass
    return "the team"

# --- Generate Draft ---
# Supports both /generate-draft (user prompt) and /generate-email (frontend Axios)
@router.post("/generate-draft")
@router.post("/generate-email")
def generate_draft(req: DraftRequest, user_id: Optional[str] = Header(None, alias="X-User-Id")):
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        
        if user_id and user_id != "admin":
            cur.execute("SELECT * FROM leads_raw WHERE id = %s AND user_id = %s", (req.lead_id, user_id))
        elif user_id == "admin":
            cur.execute("SELECT * FROM leads_raw WHERE id = %s", (req.lead_id,))
        else:
            cur.execute("SELECT * FROM leads_raw WHERE id = %s AND user_id IS NULL", (req.lead_id,))
            
        lead = cur.fetchone()

        if not lead:
            return {"error": "Lead not found"}
        lead = normalize_lead(lead)
        
        sender_name = get_user_name(user_id)
        generator = EmailGenerator()
        email_data = generator.generate_email(lead, sender_name=sender_name)
        
        subject = email_data.get("subject", "Following up")
        body = email_data.get("body", "Hello, we would love to connect.")
        
        # The AI now generates the full email including greeting and sign-off.
        # We just need to prepend the Subject for consistent database storage.
        email_content = f"Subject: {subject}\n\n{body}"
        
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
@router.get("/pending-drafts")
@router.get("/emails")
def get_pending_drafts(page: int = 1, status: Optional[str] = None, region: Optional[str] = None, geo: Optional[str] = None, per_page: int = 20, user_id: Optional[str] = Header(None, alias="X-User-Id")):
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    
    # Base condition
    where_clause = "WHERE email_draft IS NOT NULL"
    params = []
    
    if user_id and user_id != "admin":
        where_clause += " AND user_id = %s"
        params.append(user_id)
    elif user_id == "admin":
        pass
    else:
        where_clause += " AND user_id IS NULL"

    if status:
        where_clause += " AND email_status = %s"
        params.append(status)

    if region:
        if region == 'US':
            where_clause += " AND country IN ('USA', 'US', 'United States', 'Canada')"
        elif region == 'EU':
            where_clause += " AND country IN ('UK', 'Germany', 'France', 'Spain', 'Italy', 'Netherlands', 'Sweden')"
        elif region == 'APAC':
            where_clause += " AND country IN ('India', 'Singapore', 'Australia', 'Japan', 'China')"

    if geo:
        tier1_countries = ('USA', 'US', 'Canada', 'UK', 'Germany', 'France', 'Australia', 'Japan')
        if geo == 'Tier1':
            where_clause += f" AND country IN {tier1_countries}"
        elif geo == 'Emerging':
            where_clause += f" AND country NOT IN {tier1_countries}"

    query = f"""
        SELECT id, first_name, last_name, email, email_draft, email_status, company_name, persona, fit_score, updated_at, email_approved_by 
        FROM leads_raw 
        {where_clause}
        ORDER BY COALESCE(updated_at, created_at) DESC LIMIT %s OFFSET %s
    """
    params.extend([per_page, (page - 1) * per_page])
    
    cur.execute(query, tuple(params))
    rows = cur.fetchall()
    
    # count total
    count_query = f"SELECT COUNT(*) FROM leads_raw {where_clause}"
    cur.execute(count_query, tuple(params[:-2])) # exclude limit/offset
    total = cur.fetchone()[0]
    pages = (total + per_page - 1) // per_page
    
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
            "attachments": [
                {"name": "QVSCL Company Profile.pdf", "size": "1.7 MB", "type": "application/pdf"},
                {"name": "Lalit_Huria_Profile.pdf", "size": "250 KB", "type": "application/pdf"}
            ],
            "status": r["email_status"] or "PENDING_APPROVAL",
            "performance": {"opens": 0, "clicks": 0}, # Placeholders
            "verifier": r.get("email_approved_by") or ("admin" if r["email_status"] in ["APPROVED", "SENT"] else None),
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
        
        if user_id and user_id != "admin":
            cur.execute("SELECT * FROM leads_raw WHERE id = %s AND user_id = %s", (draft_id, user_id))
        elif user_id == "admin":
            cur.execute("SELECT * FROM leads_raw WHERE id = %s", (draft_id,))
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
    from app.services.email_service import send_email
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    
    # 1. Fetch User Data for Sender Identity
    sender_email = None
    sender_name = "the team"
    if user_id:
        cur.execute("SELECT email, full_name, username FROM users WHERE id = %s", (normalize_user_id(user_id),))
        u = cur.fetchone()
        if u:
            sender_email = u['email']
            sender_name = u['full_name'] or u['username']

    # 2. Fetch/Prepare Draft
    cur.execute("SELECT first_name, last_name, email, email_draft FROM leads_raw WHERE id = %s", (draft_id,))
    lead = cur.fetchone()
    if not lead:
        return {"error": "Lead not found"}

    draft_content = lead.get('email_draft')
    email = lead['email']
    
    if not draft_content:
        from app.services.llm_services import EmailGenerator
        generator = EmailGenerator()
        email_data = generator.generate_email(dict(lead), sender_name=sender_name)
        subject = email_data.get("subject", "Following up")
        body = email_data.get("body", "Hello, we would love to connect.")
        draft_content = f"Subject: {subject}\n\n{body}"
    
    # 3. Parse and Dispatch
    subject = "Following up"
    body = draft_content
    if "Subject: " in draft_content:
        parts = draft_content.split("\n\n", 1)
        subject = parts[0].replace("Subject: ", "").strip()
        body = parts[1].strip() if len(parts) > 1 else ""

    # Real Dispatch
    logging.info(f"Triggering real email dispatch for lead {draft_id} from {sender_email}")
    success = send_email(
        to_email=email,
        subject=subject,
        html_content=body.replace("\n", "<br>"),
        from_email=sender_email,
        from_name=sender_name
    )

    if success:
        cur.execute(
            "UPDATE leads_raw SET email_draft = %s, email_status = 'SENT', email_approved_by = %s, updated_at = NOW() WHERE id = %s",
            (draft_content, sender_name, draft_id)
        )
        conn.commit()
        from app.models.lead import add_activity_log
        add_activity_log(draft_id, "EMAIL_SENT", f"Email dispatched via Resend from {sender_email}", sender_name)
        cur.close()
        conn.close()
        return {"status": "sent", "message": f"Success: Email dispatched to {email}"}
    else:
        conn.rollback()
        cur.close()
        conn.close()
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail="Outreach dispatch failed. Please verify your Resend configuration and sender email in Profile.")

@router.post("/reject-email/{draft_id}")
def reject_draft(draft_id: int, req: Optional[RejectRequest] = None, user_id: Optional[str] = Header(None, alias="X-User-Id")):
    conn = get_db_connection()
    cur = conn.cursor()
    
    if user_id and user_id != "admin":
        where_clause = "WHERE id = %s AND user_id = %s"
        params = (draft_id, user_id)
    elif user_id == "admin":
        where_clause = "WHERE id = %s"
        params = (draft_id,)
    else:
        where_clause = "WHERE id = %s AND user_id IS NULL"
        params = (draft_id,)
    
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
        if user_id and user_id != "admin":
            where_clause = f"WHERE id IN ({format_strings}) AND user_id = %s"
            params = tuple(req.lead_ids) + (user_id,)
        elif user_id == "admin":
            where_clause = f"WHERE id IN ({format_strings})"
            params = tuple(req.lead_ids)
        else:
            where_clause = f"WHERE id IN ({format_strings}) AND user_id IS NULL"
            params = tuple(req.lead_ids)
        
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
    from app.services.email_service import send_email
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    
    # 1. Fetch User Data for Sender Identity
    sender_email = None
    sender_name = "the team"
    if user_id:
        cur.execute("SELECT email, full_name, username FROM users WHERE id = %s", (user_id,))
        u = cur.fetchone()
        if u:
            sender_email = u['email']
            sender_name = u['full_name'] or u['username']

    # 2. Get all approved leads for THIS user
    where_clause = "WHERE email_status = 'APPROVED'"
    params = []
    if user_id and user_id != "admin":
        where_clause += " AND user_id = %s"
        params.append(user_id)
    elif user_id == "admin":
        pass
    else:
        where_clause += " AND user_id IS NULL"
    
    cur.execute(f"SELECT id, email, email_draft FROM leads_raw {where_clause}", params)
    leads_to_send = cur.fetchall()
    
    sent_count = 0
    for lead in leads_to_send:
        try:
            draft_content = lead['email_draft'] or ""
            # Parse Subject and Body
            subject = "Following up"
            body = draft_content
            if "Subject: " in draft_content:
                parts = draft_content.split("\n\n", 1)
                subject = parts[0].replace("Subject: ", "").strip()
                body = parts[1].strip() if len(parts) > 1 else ""

            # Real Dispatch
            success = send_email(
                to_email=lead['email'],
                subject=subject,
                html_content=body.replace("\n", "<br>"),
                from_email=sender_email,
                from_name=sender_name
            )

            if success:
                cur.execute("UPDATE leads_raw SET email_status = 'SENT', updated_at = NOW() WHERE id = %s", (lead['id'],))
                from app.models.lead import add_activity_log
                add_activity_log(lead['id'], "EMAIL_SENT", f"Email dispatched via Resend from {sender_email}", "system")
                sent_count += 1
        except Exception as e:
            logger.error(f"Batch dispatch error for lead {lead['id']}: {str(e)}")

    conn.commit()
    cur.close()
    conn.close()
    
    return {"message": f"Successfully sent {sent_count} approved emails via Resend."}

@router.post("/generate-bulk-domain-drafts")
def generate_bulk_domain_drafts(req: BulkDraftRequest, user_id: Optional[str] = Header(None, alias="X-User-Id")):
    try:
        from app.models.lead import get_lead_by_id
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        
        if not req.lead_ids:
            return {"message": "No leads provided"}
            
        format_strings = ','.join(['%s'] * len(req.lead_ids))
        if user_id and user_id != "admin":
            where_clause = f"WHERE id IN ({format_strings}) AND user_id = %s"
            params = tuple(req.lead_ids) + (user_id,)
        elif user_id == "admin":
            where_clause = f"WHERE id IN ({format_strings})"
            params = tuple(req.lead_ids)
        else:
            where_clause = f"WHERE id IN ({format_strings}) AND user_id IS NULL"
            params = tuple(req.lead_ids)

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
        
        def process_group(group_key, group_leads):
            first_lead = group_leads[0]
            try:
                sender_name = get_user_name(user_id)
                email_data = generator.generate_email(normalize_lead(first_lead), sender_name=sender_name)
                subject = email_data.get("subject", "Following up")
                body = email_data.get("body", "Hello, we would love to connect.")
            except Exception as e:
                print(f"Error generating email for {group_key}: {e}")
                subject = "Following up"
                body = "Hello, we would love to connect to discuss potential synergies."
                
            lines = body.split('\n')
            if lines and any(g in lines[0].lower() for g in ['hi ', 'hello ', 'dear ']):
                lines = lines[1:]
            clean_body = '\n'.join(lines).lstrip()
            return f"Subject: {subject}\n\nHi {{first_name}},\n\n{clean_body}", group_leads
            
        results = []
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(process_group, k, v) for k, v in groups.items()]
            for future in as_completed(futures):
                res = future.result()
                if res: results.append(res)
                
        for email_content, group_leads in results:
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
    from app.services.email_service import send_email
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        
        if not req.lead_ids:
            return {"message": "No leads provided"}
            
        # 1. Fetch User Data
        sender_email = None
        sender_name = "the team"
        if user_id:
            cur.execute("SELECT email, full_name, username FROM users WHERE id = %s", (user_id,))
            u = cur.fetchone()
            if u:
                sender_email = u['email']
                sender_name = u['full_name'] or u['username']

        format_strings = ','.join(['%s'] * len(req.lead_ids))
        if user_id and user_id != "admin":
            where_clause = f"WHERE id IN ({format_strings}) AND user_id = %s"
            params = tuple(req.lead_ids) + (user_id,)
        elif user_id == "admin":
            where_clause = f"WHERE id IN ({format_strings})"
            params = tuple(req.lead_ids)
        else:
            where_clause = f"WHERE id IN ({format_strings}) AND user_id IS NULL"
            params = tuple(req.lead_ids)

        cur.execute(f"SELECT id, first_name, email, email_draft, domain, company_name FROM leads_raw {where_clause}", params)
        leads = cur.fetchall()
        
        sent_count = 0
        from app.models.lead import add_activity_log
        from app.services.llm_services import EmailGenerator
        generator = EmailGenerator()

        for lead in leads:
            try:
                # If draft already exists, use it. Otherwise generate.
                email_content = lead.get("email_draft")
                if not email_content:
                    email_data = generator.generate_email(normalize_lead(dict(lead)), sender_name=sender_name)
                    subject = email_data.get("subject", "Following up")
                    body = email_data.get("body", "Hello, we would love to connect.")
                    email_content = f"Subject: {subject}\n\n{body}"
                
                # Parse Subject and Body
                subject = "Following up"
                body = email_content
                if "Subject: " in email_content:
                    parts = email_content.split("\n\n", 1)
                    subject = parts[0].replace("Subject: ", "").strip()
                    body = parts[1].strip() if len(parts) > 1 else ""

                # Real Dispatch
                success = send_email(
                    to_email=lead['email'],
                    subject=subject,
                    html_content=body.replace("\n", "<br>"),
                    from_email=sender_email,
                    from_name=sender_name
                )

                if success:
                    cur.execute("""
                        UPDATE leads_raw 
                        SET email_draft = %s, email_status = 'SENT', updated_at = NOW() 
                        WHERE id = %s
                    """, (email_content, lead['id']))
                    add_activity_log(lead['id'], "EMAIL_SENT", f"Bulk domain email dispatched via Resend from {sender_email}", "system")
                    sent_count += 1
            except Exception as e:
                print(f"Error sending bulk lead {lead['id']}: {e}")

        conn.commit()
        cur.close()
        conn.close()
        
        return {
            "message": f"Successfully sent {sent_count} emails via Resend.",
            "leads_processed": len(leads),
            "leads_sent": sent_count
        }
    except Exception as e:
        traceback.print_exc()
        return {"error": str(e)}