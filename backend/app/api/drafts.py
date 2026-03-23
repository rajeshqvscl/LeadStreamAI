from fastapi import APIRouter
from pydantic import BaseModel
import traceback
from typing import Optional

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
def generate_draft(req: DraftRequest):
    try:
        lead = get_lead_by_id(req.lead_id)
        if not lead:
            return {"error": "Lead not found"}
        lead = normalize_lead(lead)
        
        generator = EmailGenerator()
        email_data = generator.generate_email(lead)
        
        subject = email_data.get("subject", "Following up")
        body = email_data.get("body", "Hello, we would love to connect.")
        
        # update leads_raw.email_draft and email_status='PENDING_APPROVAL'
        conn = get_db_connection()
        cur = conn.cursor()
        email_content = f"Subject: {subject}\n\n{body}"
        cur.execute("""
            UPDATE leads_raw 
            SET email_draft = %s, email_status = 'PENDING_APPROVAL' 
            WHERE id = %s
        """, (email_content, req.lead_id))
        conn.commit()
        cur.close()
        conn.close()

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
def get_pending_drafts(page: int = 1, status: Optional[str] = None, per_page: int = 20):
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    
    query = """
        SELECT id, first_name, last_name, email, email_draft, email_status, company_name, persona, fit_score 
        FROM leads_raw 
        WHERE email_draft IS NOT NULL
    """
    params = []
    
    if status:
        query += " AND email_status = %s"
        params.append(status)
        
    query += " ORDER BY id DESC LIMIT %s OFFSET %s"
    params.extend([per_page, (page - 1) * per_page])
    
    cur.execute(query, tuple(params))
    rows = cur.fetchall()
    
    # count total
    count_query = "SELECT COUNT(*) FROM leads_raw WHERE email_draft IS NOT NULL"
    count_params = []
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
        subject = ""
        body = draft_content
        if "Subject: " in draft_content:
            parts = draft_content.split("\n\n", 1)
            subject = parts[0].replace("Subject: ", "")
            if len(parts) > 1:
                body = parts[1]
                
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
            "verifier": "admin" if r["email_status"] in ["APPROVED", "SENT"] else None
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
def refine_email_endpoint(draft_id: int, req: RefineRequest):
    try:
        # Get lead info to provide context to LLM
        lead = get_lead_by_id(draft_id)
        if not lead:
            return {"error": "Lead not found"}
            
        generator = EmailGenerator()
        refined_data = generator.refine_email(req.subject, req.body, req.instruction)
        
        # Update DB
        new_content = f"Subject: {refined_data['subject']}\n\n{refined_data['body']}"
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("UPDATE leads_raw SET email_draft = %s WHERE id = %s", (new_content, draft_id))
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
def approve_draft(draft_id: int, req: Optional[ApproveRequest] = None):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        "UPDATE leads_raw SET email_status = 'APPROVED' WHERE id = %s",
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
def reject_draft(draft_id: int, req: Optional[RejectRequest] = None):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        "UPDATE leads_raw SET email_status = 'REJECTED' WHERE id = %s",
        (draft_id,)
    )
    conn.commit()
    cur.close()
    conn.close()
    
    from app.models.lead import add_activity_log
    add_activity_log(draft_id, "EMAIL_REJECTED", f"Reason: {req.rejected_reason if req else ''}", "admin")
    
    return {"status": "rejected", "message": "Draft rejected"}

@router.post("/send-approved-batch")
def send_approved_batch():
    conn = get_db_connection()
    cur = conn.cursor()
    
    # Get all approved lead IDs
    cur.execute("SELECT id FROM leads_raw WHERE email_status = 'APPROVED'")
    ids = [r[0] for r in cur.fetchall()]
    
    cur.execute(
        "UPDATE leads_raw SET email_status = 'SENT' WHERE email_status = 'APPROVED'"
    )
    updated = cur.rowcount
    conn.commit()
    cur.close()
    conn.close()
    
    from app.models.lead import add_activity_log
    for lid in ids:
        add_activity_log(lid, "EMAIL_SENT", "Email dispatched in batch", "system")
        
    return {"message": f"Successfully sent {updated} approved emails."}