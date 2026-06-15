import os
import shutil
from fastapi import APIRouter, HTTPException, Header, UploadFile, File
from typing import Optional
from pydantic import BaseModel
from app.models.prompt import get_all_prompts, create_prompt, update_prompt, delete_prompt
from app.database import get_db_connection
import psycopg2.extras

ASSETS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "assets")
os.makedirs(ASSETS_DIR, exist_ok=True)

router = APIRouter()

class PromptBase(BaseModel):
    name: str
    prompt_type: str
    content: str
    description: Optional[str] = None
    is_active: Optional[bool] = True

class PromptCreate(BaseModel):
    name: str
    content: str
    description: Optional[str] = None
    followup_1: Optional[str] = None
    followup_2: Optional[str] = None
    followup_3: Optional[str] = None
    subject: Optional[str] = None
    cc: Optional[str] = None

class PromptUpdate(BaseModel):
    name: Optional[str] = None
    prompt_type: Optional[str] = None
    content: Optional[str] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None
    followup_1: Optional[str] = None
    followup_2: Optional[str] = None
    followup_3: Optional[str] = None
    subject: Optional[str] = None
    cc: Optional[str] = None

@router.get("/prompts")
def list_prompts():
    return get_all_prompts()

@router.post("/prompts")
def add_prompt(prompt: PromptBase):
    prompt_id = create_prompt(
        prompt.name, 
        prompt.prompt_type, 
        prompt.content, 
        prompt.description, 
        prompt.is_active
    )
    return {"id": prompt_id, "message": "Prompt created successfully"}

@router.post("/custom-draft-templates")
def create_custom_template(tpl: PromptCreate, user_id: Optional[str] = Header(None, alias="X-User-Id")):
    """Create a custom draft template with follow-ups, owned by the current user."""
    owner_username = None
    if user_id:
        try:
            conn = get_db_connection()
            cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
            cur.execute("SELECT username, full_name FROM users WHERE id = %s", (int(user_id),))
            user_row = cur.fetchone()
            cur.close()
            conn.close()
            if user_row:
                uname = str(user_row['username'] or '').lower()
                fname = str(user_row['full_name'] or '').lower()
                owner_username = uname.split('.')[0] or fname.split()[0] if fname else uname
        except Exception:
            pass
    prompt_id = create_prompt(
        name=tpl.name,
        prompt_type='CUSTOM_DRAFT',
        content=tpl.content,
        description=tpl.description,
        is_active=True,
        owner_username=owner_username,
        followup_1=tpl.followup_1,
        followup_2=tpl.followup_2,
        followup_3=tpl.followup_3,
        subject=tpl.subject,
        cc=tpl.cc
    )
    return {"id": prompt_id, "message": "Custom template created successfully"}

@router.put("/prompts/{prompt_id}")
def edit_prompt(prompt_id: int, prompt_data: PromptUpdate):
    success = update_prompt(prompt_id, prompt_data.dict(exclude_unset=True))
    if not success:
        raise HTTPException(status_code=404, detail="Prompt not found")
    return {"message": "Prompt updated successfully"}

@router.post("/prompts/{prompt_id}/attachment")
def upload_prompt_attachment(prompt_id: int, file: UploadFile = File(...)):
    if not file.filename.lower().endswith('.pdf'):
        raise HTTPException(status_code=400, detail="Only PDF files allowed")
    ext = os.path.splitext(file.filename)[1]
    dest_name = f"prompt_{prompt_id}_attachment{ext}"
    dest_path = os.path.join(ASSETS_DIR, dest_name)
    with open(dest_path, "wb") as f:
        shutil.copyfileobj(file.file, f)
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("UPDATE prompts SET attachment_file = %s WHERE id = %s", (dest_name, prompt_id))
    conn.commit()
    cur.close()
    conn.close()
    return {"filename": dest_name, "message": "Attachment uploaded"}

@router.delete("/prompts/{prompt_id}")
def remove_prompt(prompt_id: int, user_id: Optional[str] = Header(None, alias="X-User-Id")):
    """Delete a prompt — only if the user owns it."""
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    # Fetch the prompt to verify ownership
    cur.execute("SELECT owner_username FROM prompts WHERE id = %s", (prompt_id,))
    prompt = cur.fetchone()
    if not prompt:
        cur.close()
        conn.close()
        raise HTTPException(status_code=404, detail="Prompt not found")
    owner = prompt['owner_username']
    if owner and user_id:
        try:
            cur.execute("SELECT username, full_name FROM users WHERE id = %s", (int(user_id),))
            user_row = cur.fetchone()
            if user_row:
                uname = str(user_row['username'] or '').lower()
                fname = str(user_row['full_name'] or '').lower()
                current_user = uname.split('.')[0] or fname.split()[0] if fname else uname
                if current_user != owner:
                    cur.close()
                    conn.close()
                    raise HTTPException(status_code=403, detail="You can only delete your own templates")
        except HTTPException:
            raise
        except Exception:
            pass
    elif owner and not user_id:
        cur.close()
        conn.close()
        raise HTTPException(status_code=403, detail="Authentication required to delete this template")
    cur.close()
    conn.close()
    success = delete_prompt(prompt_id)
    if not success:
        raise HTTPException(status_code=404, detail="Prompt not found")
    return {"message": "Template deleted successfully"}
