from fastapi import APIRouter, HTTPException, Depends, Header
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from typing import Optional
import os
import requests
import hashlib
import psycopg2
import psycopg2.extras
from dotenv import load_dotenv
from pathlib import Path
from app.database import get_db_connection

# Fix: Ensure .env is loaded in the API layer too
env_path = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(dotenv_path=env_path, override=True)

router = APIRouter()

class LoginRequest(BaseModel):
    username: str
    password: str

@router.post("/auth/login")
def login(req: LoginRequest):
    import hashlib
    from app.database import get_db_connection
    from fastapi import HTTPException
    
    username = req.username.strip()
    password = req.password
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    # Query user by username (case-insensitive)
    cur.execute("SELECT id, username, email, full_name, password_hash, role, is_active, is_approved FROM users WHERE LOWER(username) = LOWER(%s)", (username,))

    user = cur.fetchone()
    
    cur.close()
    conn.close()
    
    if not user:
        raise HTTPException(status_code=401, detail="Invalid username or password")
        
    if not user['is_active']:
        raise HTTPException(status_code=403, detail="Account is deactivated")
        
    # Verify password hash
    password_hash = hashlib.sha256(req.password.encode()).hexdigest()
    if password_hash != user['password_hash']:
        raise HTTPException(status_code=401, detail="Invalid username or password")
        
    # Reset is_approved to FALSE on every login for non-admins
    # This enforces the "approval required every time you login" rule.
    if user['role'] != 'ADMIN':
        try:
            conn = get_db_connection()
            cur = conn.cursor()
            cur.execute("UPDATE users SET is_approved = FALSE WHERE id = %s", (user['id'],))
            conn.commit()
            cur.close()
            conn.close()
        except Exception as e:
            print(f"Login reset failed: {e}")

    return {
        "access_token": "dummy_token", # In a real app, generate a JWT here
        "token_type": "bearer",
        "user": {
            "id": user['id'],
            "username": user['username'],
            "email": user['email'],
            "full_name": user['full_name'],
            "role": user['role'],
            "is_approved": user['is_approved']
        }
    }

@router.get("/auth/me")
def get_current_user(user_id: Optional[str] = Header(None, alias="X-User-Id")):
    """Returns the current user profile and approval status."""
    if not user_id:
        raise HTTPException(status_code=401, detail="Authentication required")
    
    # Handle 'admin' string or digits
    real_uid = user_id if user_id and user_id.isdigit() else "1"
    
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    try:
        cur.execute("SELECT id, username, email, full_name, role, is_active, is_approved, credits_used, COALESCE(credits_limit, 200) as credits_limit FROM users WHERE id = %s", (real_uid,))
        user = cur.fetchone()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
            
        return dict(user)
    finally:
        cur.close()
        conn.close()

# --- LOGOUT & STATE RESET ---

@router.post("/auth/logout")
def logout(user_id: Optional[str] = Header(None, alias="X-User-Id")):
    """Handles logout by resetting the user's approval status, enforcing re-approval upon next login."""
    if not user_id:
        return {"success": True}
        
    from app.database import get_db_connection
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        # Reset is_approved to FALSE so they must request access again
        cur.execute("UPDATE users SET is_approved = FALSE WHERE id = %s AND role != 'ADMIN'", (user_id,))
        conn.commit()
    except Exception as e:
        conn.rollback()
        print(f"Logout status reset failed: {e}")
    finally:
        cur.close()
        conn.close()
        
    return {"success": True, "message": "Logged out and approval status reset"}

# --- ACCESS REQUEST & APPROVAL ---

class AccessRequest(BaseModel):
    user_id: int

@router.post("/auth/request-access")
def request_access(req: AccessRequest):
    """Triggers an email notification to the Admin for approval."""
    from app.services.email_service import send_email
    from app.database import get_db_connection
    import psycopg2.extras

    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    
    # Get user details
    cur.execute("SELECT id, username, email, full_name FROM users WHERE id = %s", (req.user_id,))
    user = cur.fetchone()
    
    # Get admin email from database
    cur.execute("SELECT email, full_name, username FROM users WHERE role = 'ADMIN' LIMIT 1")
    admin = cur.fetchone()
    
    cur.close()
    conn.close()
    
    # Resolve Backend URL: Priority .env > Production Guess > Local Fallback
    import os
    from dotenv import load_dotenv
    load_dotenv(dotenv_path=env_path, override=True) # Refresh env
    
    # 1. Try environment variables
    base_url = os.getenv("BACKEND_URL")
    
    # 2. Try Render specific variables
    if not base_url or base_url.lower() == "null" or "localhost" in base_url.lower():
        # Only use localhost if we are NOT on Render
        if os.getenv("RENDER_EXTERNAL_URL"):
            base_url = os.getenv("RENDER_EXTERNAL_URL")
    
    # 3. Final Fallback to a valid string, never Null
    if not base_url or base_url.lower() == "null" or base_url.strip() == "":
        # We also check the commented out production URL in case it's helpful
        base_url = "https://lead-backend-ipls.onrender.com" # Probable render URL from .env comments
    
    # Clean the URL
    base_url = base_url.rstrip("/")
    if not base_url.startswith("http"):
        base_url = f"https://{base_url}"
        
    approve_url = f"{base_url}/api/admin/approve-user/{user['id']}"
    print(f"DEBUG: Generated Approval URL: {approve_url}")
    
    subject = f"🚨 Discovery Access Request: {user['full_name'] or user['username']}"
    html_content = f"""
    <div style="font-family: sans-serif; max-width: 600px; margin: auto; padding: 20px; border: 1px solid #e2e8f0; border-radius: 12px; background-color: #f8fafc;">
        <h2 style="color: #6366f1;">Discovery Access Request</h2>
        <p>User <strong>{user['full_name'] or user['username']}</strong> ({user['email']}) is requesting access to the <strong>Lead Discovery & Bulk Search</strong> engine.</p>
        
        <div style="margin: 30px 0; text-align: center;">
            <a href="{approve_url}" style="background-color: #6366f1; color: white; padding: 14px 28px; text-decoration: none; border-radius: 8px; font-weight: bold; display: inline-block; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.1);">
                Approve Discovery Access
            </a>
        </div>
        
        <p style="color: #64748b; font-size: 14px;">Approving will grant them a strict limit of 200 leads and enable all search features.</p>
    </div>
    """
    
    # Send email from system to admin
    success = send_email(
        to_email=admin['email'],
        subject=subject,
        html_content=html_content,
        from_email=os.getenv("SMTP_USER", admin['email']),
        from_name="LeadStream Security",
        is_system_email=True
    )
    
    if not success:
        raise HTTPException(status_code=500, detail="Failed to send notification email")
        
    return {"message": "Access request sent to administrator"}

@router.get("/admin/approve-user/{user_id}")
def approve_user_landing(user_id: int):
    """One-click approval landing page for Admins."""
    from app.database import get_db_connection
    from fastapi.responses import HTMLResponse
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        cur.execute("""
            UPDATE users 
            SET is_approved = TRUE, 
                is_active = TRUE,
                credits_limit = 200,
                credits_used = 0
            WHERE id = %s
        """, (user_id,))
        conn.commit()
    except Exception as e:
        conn.rollback()
        return HTMLResponse(content=f"Error: {str(e)}", status_code=400)
    finally:
        cur.close()
        conn.close()

    frontend_url = os.getenv("FRONTEND_URL", "https://lead-frontend-5new.onrender.com")
    
    return HTMLResponse(content=f"""
        <div style="font-family: sans-serif; text-align: center; padding: 50px; background-color: #f8fafc; min-height: 100vh;">
            <div style="max-width: 500px; margin: auto; background: white; padding: 40px; border-radius: 20px; shadow: 0 10px 15px -3px rgba(0,0,0,0.1);">
                <div style="font-size: 60px; margin-bottom: 20px;">✅</div>
                <h1 style="color: #10b981; margin-bottom: 15px;">User Approved!</h1>
                <p style="color: #475569; font-size: 16px; line-height: 1.6;">Account access has been granted. The user is now active and can perform extractions.</p>
                
                <div style="margin-top: 40px;">
                    <a href="{frontend_url}" style="background-color: #6366f1; color: white; padding: 12px 30px; text-decoration: none; border-radius: 10px; font-weight: bold; display: inline-block;">
                        Open Dashboard →
                    </a>
                </div>
                <p style="color: #94a3b8; margin-top: 30px; font-size: 12px;">You can now close this tab.</p>
            </div>
        </div>
    """)
