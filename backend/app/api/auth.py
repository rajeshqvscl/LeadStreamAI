from pathlib import Path
from fastapi import APIRouter, HTTPException, Depends, Header, Request
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from typing import Optional
import os
import requests
import hashlib
import psycopg2
import psycopg2.extras
from dotenv import load_dotenv
import datetime
from app.database import get_db_connection
from app.services.google_service import get_google_flow, register_gmail_watch

# Fix: Ensure .env is loaded in the API layer too
env_path = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(dotenv_path=env_path, override=True)

# --- OAuth Environment Fixes (Local Testing) ---
os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'

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
        
    # Verification removed: Users stay approved once an admin activates them.

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

@router.post("/auth/google/disconnect")
def disconnect_google(user_id: Optional[str] = Header(None, alias="X-User-Id")):
    """Forcefully removes all Google tokens for a user (Nuclear Reset)."""
    uid = user_id if user_id and user_id.isdigit() else "1"
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("""
            UPDATE users 
            SET google_access_token = NULL, 
                google_refresh_token = NULL, 
                google_token_expiry = NULL,
                google_linked_at = NULL,
                google_email = NULL
            WHERE id = %s
        """, (uid,))
        conn.commit()
        return {"status": "success", "message": "Intelligence Layer disconnected."}
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        cur.close()
        conn.close()

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
        cur.execute("SELECT id, username, email, full_name, role, is_active, is_approved, google_linked_at, google_email, credits_used, COALESCE(credits_limit, 200) as credits_limit FROM users WHERE id = %s", (real_uid,))
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
    """Handles logout."""
    if not user_id:
        return {"success": True}
        
    return {"success": True, "message": "Logged out"}

# --- ACCESS REQUEST & APPROVAL ---

@router.post("/auth/google/unlink")
def unlink_google(user_id: Optional[str] = Header(None, alias="X-User-Id")):
    """Removes the Google connection for the current user."""
    from app.database import get_db_connection
    if not user_id:
        raise HTTPException(status_code=400, detail="Missing user context")
    
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("""
            UPDATE users 
            SET google_refresh_token = NULL, 
                google_linked_at = NULL 
            WHERE id = %s OR username = %s
        """, (user_id if user_id.isdigit() else 0, user_id))
        conn.commit()
        return {"success": True, "message": "Google account unlinked successfully"}
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        cur.close()
        conn.close()

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
    res = send_email(
        to_email=admin['email'],
        subject=subject,
        html_content=html_content,
        from_email=os.getenv("SMTP_USER", admin['email']),
        from_name="LeadStream Security",
        is_system_email=True
    )
    success = res[0] if isinstance(res, tuple) else res
    
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
                is_active = TRUE
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

# --- GOOGLE OAUTH FLOW ---

@router.get("/auth/google/link")
def google_link(request: Request, user_id: str = Header(..., alias="X-User-Id")):
    """Initiates the Google OAuth 2.0 flow for a specific user."""
    # Use configured redirect URI or fallback to current request host
    redirect_uri = os.getenv("GOOGLE_REDIRECT_URI")
    if not redirect_uri:
        redirect_uri = f"{request.base_url.scheme}://{request.base_url.netloc}/api/auth/google/callback"
    
    import base64
    import json
    
    flow = get_google_flow(redirect_uri=redirect_uri)
    
    # Generate the authorization URL. 
    # This generates flow.code_verifier internally.
    # Force a fresh grant to clear any accidental "Metadata-only" selections
    authorization_url, _ = flow.authorization_url(
        access_type='offline',
        prompt='consent select_account',
        include_granted_scopes='false'
    )
    
    # Bundle user_id and code_verifier into a tiny state string
    state_payload = json.dumps({"u": user_id, "v": flow.code_verifier})
    state_str = base64.urlsafe_b64encode(state_payload.encode()).decode()
    
    # Regenerate URL with our bundled state
    authorization_url, _ = flow.authorization_url(
        access_type='offline',
        prompt='consent select_account',
        include_granted_scopes='false',
        state=state_str
    )
    
    return {"url": authorization_url}

@router.get("/auth/google/callback")
def google_callback(request: Request, code: str, state: str):
    """Handles the Google OAuth 2.0 callback, exchanges code for tokens, and performs watch() registration."""
    import base64
    import json
    
    # Extract user_id and code_verifier from the state bundle
    try:
        state_data = json.loads(base64.urlsafe_b64decode(state).decode())
        user_id = state_data.get('u')
        code_verifier = state_data.get('v')
    except Exception as e:
        print(f"Error decoding OAuth state: {e}")
        raise HTTPException(status_code=400, detail="Invalid OAuth state")

    # Use configured redirect URI or fallback to current request host
    redirect_uri = os.getenv("GOOGLE_REDIRECT_URI")
    if not redirect_uri:
        redirect_uri = f"{request.base_url.scheme}://{request.base_url.netloc}/api/auth/google/callback"
    
    flow = get_google_flow(redirect_uri=redirect_uri)
    # CRITICAL: Restore the code_verifier so fetch_token succeeds
    flow.code_verifier = code_verifier
    
    # Exchange the authorization code for tokens
    flow.fetch_token(code=code)
    creds = flow.credentials

    conn = get_db_connection()
    cur = conn.cursor()
    try:
        # Extract Google Email and ID reliably from userinfo endpoint
        google_email = None
        google_id = None
        try:
            from googleapiclient.discovery import build
            user_info_service = build('oauth2', 'v2', credentials=creds)
            user_info = user_info_service.userinfo().get().execute()
            google_email = user_info.get('email')
            google_id = user_info.get('id')
        except Exception as e:
            logger.error(f"Failed to fetch Google user info: {e}")
            pass

        # Store tokens and identity in database
        # Only update refresh_token if Google provided a new one (to avoid nullifying old working one)
        if creds.refresh_token:
            cur.execute("""
                UPDATE users 
                SET google_access_token = %s, 
                    google_refresh_token = %s, 
                    google_token_expiry = %s,
                    google_linked_at = NOW(),
                    google_email = %s,
                    google_id = %s
                WHERE id = %s
            """, (creds.token, creds.refresh_token, creds.expiry, google_email, google_id, user_id))
        else:
            cur.execute("""
                UPDATE users 
                SET google_access_token = %s, 
                    google_token_expiry = %s,
                    google_linked_at = NOW(),
                    google_email = %s,
                    google_id = %s
                WHERE id = %s
            """, (creds.token, creds.expiry, google_email, google_id, user_id))
        conn.commit()
        
        # Scope Validation: Check if we actually got the required permission
        received_scopes = creds.scopes or []
        print(f"DEBUG: Scopes received from Google for user {user_id}: {received_scopes}")
        
        has_full_scope = any('gmail.readonly' in s or 'mail.google.com' in s for s in received_scopes)
        if not has_full_scope:
            print(f"WARNING: User {user_id} linked account without read scope. Scopes received: {received_scopes}")
            # Redirect to a specialized error page
            frontend_url = os.getenv("FRONTEND_URL", "http://localhost:5173")
            return RedirectResponse(url=f"{frontend_url}/dashboard?error=permissions_denied")
        
        # Immediately register Gmail watch() for this user
        register_gmail_watch(int(user_id))
        
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to link Google account: {str(e)}")
    finally:
        cur.close()
        conn.close()

    frontend_url = os.getenv("FRONTEND_URL", "http://localhost:5173")
    return RedirectResponse(url=f"{frontend_url}/dashboard?google=linked")
