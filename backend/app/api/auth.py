from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from typing import Optional
import os
import requests
import hashlib
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

@router.get("/auth/google/login")
async def google_login():
    import urllib.parse
    from dotenv import load_dotenv
    from pathlib import Path
    
    # FORCE RELOAD at runtime to pick up the very latest saves from the user
    env_path = Path(__file__).resolve().parent.parent / ".env"
    load_dotenv(dotenv_path=env_path, override=True)
    
    google_client_id = os.getenv("GOOGLE_CLIENT_ID")
    redirect_uri = os.getenv("GOOGLE_REDIRECT_URI")
    
    # DEBUG LOGGING FOR ADMIN
    print(f"\n[GOOGLE AUTH DEBUG]")
    print(f"Loaded ID: {google_client_id[:5]}...{google_client_id[-5:] if google_client_id else ''}")
    print(f"Redirect URI: {redirect_uri}")
    print(f"--------------------\n")
    
    # Safety Check: Block if still using placeholders
    if not google_client_id or "your_client_id" in google_client_id:
        masked_id = (google_client_id[:5] + "..." + google_client_id[-5:]) if google_client_id and len(google_client_id) > 10 else str(google_client_id)
        return RedirectResponse(f"{os.getenv('FRONTEND_URL', 'http://localhost:5173')}/login?error=Google OAuth keys not configured (Found: {masked_id})")

    scope = "openid email profile"
    # Properly encode the redirect_uri to prevent 401/400 errors from Google
    encoded_uri = urllib.parse.quote(redirect_uri, safe='')
    url = f"https://accounts.google.com/o/oauth2/v2/auth?response_type=code&client_id={google_client_id}&redirect_uri={encoded_uri}&scope={scope}"
    return RedirectResponse(url)

@router.get("/auth/google/callback")
async def google_callback(code: str):
    token_url = "https://oauth2.googleapis.com/token"
    data = {
        "code": code,
        "client_id": os.getenv("GOOGLE_CLIENT_ID"),
        "client_secret": os.getenv("GOOGLE_CLIENT_SECRET"),
        "redirect_uri": os.getenv("GOOGLE_REDIRECT_URI"),
        "grant_type": "authorization_code"
    }
    
    frontend_url = os.getenv("FRONTEND_URL", "http://localhost:5173")
    
    try:
        token_response = requests.post(token_url, data=data).json()
        access_token = token_response.get("access_token")
        
        if not access_token:
            error_msg = token_response.get("error_description") or token_response.get("error", "Failed to retrieve access token")
            return RedirectResponse(f"{frontend_url}/login?error=Token Exchange Failed: {error_msg}")
            
        user_info_res = requests.get(
            "https://www.googleapis.com/oauth2/v3/userinfo",
            headers={"Authorization": f"Bearer {access_token}"}
        )
        user_info = user_info_res.json()
        
        email = user_info.get("email")
        if not email:
             return RedirectResponse(f"{frontend_url}/login?error=Failed to retrieve email from Google profile")
        full_name = user_info.get("name")
        google_id = user_info.get("sub")
        
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT id, username, full_name, role, is_active, is_approved FROM users WHERE email = %s", (email,))
        user = cur.fetchone()
        
        if not user:
            # Auto-create user but leave is_approved as FALSE
            username = email.split('@')[0]
            cur.execute("""
                INSERT INTO users (username, email, full_name, google_id, role, is_active, is_approved)
                VALUES (%s, %s, %s, %s, 'USER', TRUE, FALSE)
                RETURNING id, username, full_name, role, is_active, is_approved
            """, (username, email, full_name, google_id))
            user = cur.fetchone()
            conn.commit()
            
        cur.close()
        conn.close()
        
        if not user['is_active']:
            return RedirectResponse(f"{frontend_url}/login?error=Account deactivated")
            
        # Simplified: pass user info and token in URL for demo/dev purposes
        # In production, use a secure HTTP-only cookie or a temporary code
        import json
        import urllib.parse
        user_data = urllib.parse.quote(json.dumps({
            "id": user["id"],
            "username": user["username"],
            "full_name": user["full_name"],
            "role": user["role"]
        }))
        
        return RedirectResponse(f"{frontend_url}/dashboard?token=google_session&user={user_data}")
        
    except Exception as e:
        return RedirectResponse(f"{frontend_url}/login?error=Authentication failed: {str(e)}")

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
        
    # --- Fresh Start Implementation (Requested) ---
    # Delete all data associated with this user every time they login
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM leads_raw WHERE user_id = %s", (user['id'],))
    cur.execute("DELETE FROM activity_log WHERE user_id = %s", (user['id'],))
    cur.execute("DELETE FROM campaigns WHERE user_id = %s", (user['id'],))
    conn.commit()
    cur.close()
    conn.close()
    # -----------------------------------------------

        
    return {
        "access_token": "dummy_token", # In a real app, generate a JWT here
        "token_type": "bearer",
        "user": {
            "id": user['id'],
            "username": user['username'],
            "full_name": user['full_name'],
            "role": user['role']
        }
    }

