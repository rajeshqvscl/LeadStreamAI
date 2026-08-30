"""
Authentication endpoints for API v1.
"""
from fastapi import APIRouter, HTTPException, Depends, Header, Request
from pydantic import BaseModel
from typing import Optional
import os
import bcrypt
from app.database import get_db_connection
from app.services.google_service import get_google_flow, register_gmail_watch, invalidate_gmail_service_cache
import psycopg2.extras
import logging
import datetime
import secrets

logger = logging.getLogger(__name__)

router = APIRouter()

# Load .env
from dotenv import load_dotenv
from pathlib import Path
env_path = Path(__file__).resolve().parent.parent.parent / ".env"
load_dotenv(dotenv_path=env_path, override=True)


class LoginRequest(BaseModel):
    username: str
    password: str


# Login rate limiting
import threading
import time
from collections import defaultdict

_login_attempts = defaultdict(list)
_login_blocked = defaultdict(float)
_login_attempts_lock = threading.Lock()
LOGIN_MAX_ATTEMPTS = 5
LOGIN_WINDOW_SECONDS = 300
LOGIN_LOCKOUT_SECONDS = 900


def _client_ip(request: Request) -> str:
    fwd = request.headers.get("x-forwarded-for", "")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _check_login_rate_limit(username: str, request: Request) -> str:
    key = f"{username.strip().lower()}|{_client_ip(request)}"
    now = time.time()
    with _login_attempts_lock:
        if _login_blocked[key] > now:
            raise HTTPException(status_code=429, detail="Too many login attempts. Please wait 15 minutes and try again.")
        _login_attempts[key] = [t for t in _login_attempts[key] if now - t < LOGIN_WINDOW_SECONDS]
        if len(_login_attempts[key]) >= LOGIN_MAX_ATTEMPTS:
            _login_blocked[key] = now + LOGIN_LOCKOUT_SECONDS
            raise HTTPException(status_code=429, detail="Too many login attempts. Please wait 15 minutes and try again.")
    return key


def _record_login_attempt(key: str):
    with _login_attempts_lock:
        _login_attempts[key].append(time.time())


@router.post("/login")
def login(req: LoginRequest, request: Request = None):
    rate_key = _check_login_rate_limit(req.username, request)
    
    username = req.username.strip()
    password = req.password
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    cur.execute(
        "SELECT id, username, email, full_name, password_hash, role, team, is_active, is_approved, signature, signature_mode FROM users WHERE LOWER(username) = LOWER(%s)",
        (username,),
    )
    
    user = cur.fetchone()
    cur.close()
    conn.close()
    
    if not user:
        _record_login_attempt(rate_key)
        raise HTTPException(status_code=401, detail="Invalid username or password")
    
    if not user['is_active']:
        _record_login_attempt(rate_key)
        raise HTTPException(status_code=403, detail="Account is deactivated")
    
    stored_hash = user['password_hash']
    if stored_hash.startswith('$2'):
        if not bcrypt.checkpw(password.encode(), stored_hash.encode()):
            _record_login_attempt(rate_key)
            raise HTTPException(status_code=401, detail="Invalid username or password")
    else:
        import hashlib
        password_hash = hashlib.sha256(password.encode()).hexdigest()
        if password_hash != stored_hash:
            _record_login_attempt(rate_key)
            raise HTTPException(status_code=401, detail="Invalid username or password")
        # Upgrade to bcrypt
        new_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
        try:
            up_conn = get_db_connection()
            up_cur = up_conn.cursor()
            up_cur.execute("UPDATE users SET password_hash = %s WHERE id = %s", (new_hash, user['id']))
            up_conn.commit()
            up_cur.close()
            up_conn.close()
        except Exception:
            pass
    
    # Create session token
    access_token = secrets.token_urlsafe(32)
    expires_at = datetime.datetime.utcnow() + datetime.timedelta(days=30)
    try:
        s_conn = get_db_connection()
        s_cur = s_conn.cursor()
        s_cur.execute("DELETE FROM sessions WHERE expires_at <= NOW()")
        s_cur.execute("INSERT INTO sessions (token, user_id, expires_at) VALUES (%s, %s, %s)", (access_token, user['id'], expires_at))
        s_conn.commit()
        s_cur.close()
        s_conn.close()
    except Exception as sess_err:
        logger.error(f"Failed to create session: {sess_err}")
        raise HTTPException(status_code=500, detail="Could not create session. Please try again.")
    
    # Clear failed attempts
    with _login_attempts_lock:
        _login_attempts.pop(rate_key, None)
        _login_blocked.pop(rate_key, None)
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": {
            "id": user['id'],
            "username": user['username'],
            "email": user['email'],
            "full_name": user['full_name'],
            "role": user['role'],
            "team": user.get('team') or 'CLIENT',
            "is_approved": user['is_approved'],
            "signature": user.get('signature'),
            "signature_mode": user.get('signature_mode') or 'custom'
        }
    }


@router.post("/google/disconnect")
def disconnect_google(user_id: Optional[str] = Header(None, alias="X-User-Id")):
    uid = user_id if user_id and user_id.isdigit() else "1"
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name = 'users' AND column_name LIKE 'google_%'"
        )
        available = {row['column_name'] for row in cur.fetchall()}
        target_cols = [
            "google_access_token", "google_refresh_token", "google_token_expiry",
            "google_linked_at", "google_email",
        ]
        settable = [c for c in target_cols if c in available]
        if not settable:
            raise HTTPException(status_code=500, detail="No google_* columns found in users table")
        
        set_clause = ", ".join(f"{c} = NULL" for c in settable)
        cur.execute(f"UPDATE users SET {set_clause} WHERE id = %s", (uid,))
        conn.commit()
        
        try:
            invalidate_gmail_service_cache(int(uid))
        except Exception as cache_err:
            logger.warning(f"Failed to invalidate Google service cache on disconnect: {cache_err}")
        
        return {"status": "success", "message": "Intelligence Layer disconnected."}
    except HTTPException:
        conn.rollback()
        raise
    except Exception as e:
        conn.rollback()
        logger.error(f"Google disconnect failed for user {uid}: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        cur.close()
        conn.close()


@router.get("/me")
def get_current_user(user_id: Optional[str] = Header(None, alias="X-User-Id")):
    if not user_id:
        raise HTTPException(status_code=401, detail="Authentication required")
    
    real_uid = user_id if user_id and user_id.isdigit() else "1"
    
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    try:
        cur.execute(
            "SELECT id, username, email, full_name, role, team, is_active, is_approved, "
            "google_linked_at, google_email, credits_used, COALESCE(credits_limit, 200) as credits_limit, "
            "signature, signature_mode, email_font, email_font_size, signature_font, signature_font_size, "
            "image_width, image_height FROM users WHERE id = %s",
            (real_uid,)
        )
        user = cur.fetchone()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        result = dict(user)
        if not result.get('team'):
            result['team'] = 'CLIENT'
        return result
    finally:
        cur.close()
        conn.close()


@router.post("/refresh")
def refresh_token(
    user_id: Optional[str] = Header(None, alias="X-User-Id"),
    authorization: Optional[str] = Header(None, alias="Authorization")
):
    if not user_id:
        raise HTTPException(status_code=401, detail="Authentication required")
    
    real_uid = user_id if user_id and user_id.isdigit() else "1"
    
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    try:
        cur.execute("SELECT id, username, email, full_name, role, team, is_active, is_approved FROM users WHERE id = %s", (real_uid,))
        user = cur.fetchone()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        if not user.get('is_active'):
            raise HTTPException(status_code=403, detail="User is inactive")
        
        cur.execute("DELETE FROM sessions WHERE user_id = %s", (real_uid,))
        
        import secrets
        access_token = secrets.token_urlsafe(32)
        expires_at = datetime.datetime.utcnow() + datetime.timedelta(days=30)
        cur.execute("INSERT INTO sessions (token, user_id, expires_at) VALUES (%s, %s, %s)", (access_token, real_uid, expires_at))
        conn.commit()
        
        return {
            "access_token": access_token,
            "token_type": "bearer",
            "expires_in": 30 * 24 * 60 * 60,
            "user": {
                "id": user['id'],
                "username": user['username'],
                "email": user['email'],
                "full_name": user['full_name'],
                "role": user['role'],
                "team": user.get('team') or 'CLIENT',
                "is_active": user['is_active'],
                "is_approved": user['is_approved']
            }
        }
    finally:
        cur.close()
        conn.close()


class TeamUpdateRequest(BaseModel):
    team: str


@router.put("/team")
def update_team(req: TeamUpdateRequest, user_id: Optional[str] = Header(None, alias="X-User-Id")):
    if not user_id:
        raise HTTPException(status_code=401, detail="Authentication required")
    
    team = req.team.upper()
    if team not in ('CLIENT', 'INVESTOR'):
        raise HTTPException(status_code=400, detail="Team must be CLIENT or INVESTOR")
    
    real_uid = user_id if user_id and user_id.isdigit() else "1"
    
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    try:
        cur.execute(
            "UPDATE users SET team = %s, updated_at = NOW() WHERE id = %s RETURNING id, username, email, full_name, role, team, is_active, is_approved, signature, signature_mode",
            (team, real_uid)
        )
        user = cur.fetchone()
        conn.commit()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        return dict(user)
    finally:
        cur.close()
        conn.close()


class SignatureUpdateRequest(BaseModel):
    signature: str


@router.put("/signature")
def update_signature(req: SignatureUpdateRequest, user_id: Optional[str] = Header(None, alias="X-User-Id")):
    if not user_id:
        raise HTTPException(status_code=401, detail="Authentication required")
    real_uid = user_id if user_id and user_id.isdigit() else "1"
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        from app.utils.signature_clean import clean_signature_markdown
        cur.execute("UPDATE users SET signature = %s WHERE id = %s", (clean_signature_markdown(req.signature), real_uid))
        conn.commit()
        return {"message": "Signature updated successfully"}
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        cur.close()
        conn.close()


class SignatureModeUpdateRequest(BaseModel):
    signature_mode: str


@router.put("/signature-mode")
def update_signature_mode(req: SignatureModeUpdateRequest, user_id: Optional[str] = Header(None, alias="X-User-Id")):
    if not user_id:
        raise HTTPException(status_code=401, detail="Authentication required")
    mode = req.signature_mode
    if mode not in ('custom', 'auto'):
        raise HTTPException(status_code=400, detail="signature_mode must be 'custom' or 'auto'")
    real_uid = user_id if user_id and user_id.isdigit() else "1"
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("UPDATE users SET signature_mode = %s WHERE id = %s", (mode, real_uid))
        conn.commit()
        return {"message": "Signature mode updated", "signature_mode": mode}
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        cur.close()
        conn.close()


class PreferencesUpdateRequest(BaseModel):
    email_font: Optional[str] = None
    email_font_size: Optional[str] = None
    signature_font: Optional[str] = None
    signature_font_size: Optional[str] = None
    signature_mode: Optional[str] = None
    team: Optional[str] = None
    image_width: Optional[str] = None
    image_height: Optional[str] = None


@router.put("/preferences")
def update_preferences(req: PreferencesUpdateRequest, user_id: Optional[str] = Header(None, alias="X-User-Id")):
    if not user_id:
        raise HTTPException(status_code=401, detail="Authentication required")
    
    real_uid = user_id if user_id and user_id.isdigit() else "1"
    
    # Validate team
    if req.team is not None:
        team = req.team.upper()
        if team not in ('CLIENT', 'INVESTOR'):
            raise HTTPException(status_code=400, detail="Team must be CLIENT or INVESTOR")
    
    # Validate signature_mode
    if req.signature_mode is not None:
        if req.signature_mode not in ('custom', 'auto'):
            raise HTTPException(status_code=400, detail="signature_mode must be 'custom' or 'auto'")
    
    # Validate font sizes
    if req.email_font_size is not None and not req.email_font_size.endswith('px'):
        raise HTTPException(status_code=400, detail="email_font_size must end with 'px' (e.g., '13px')")
    
    if req.signature_font_size is not None and not req.signature_font_size.endswith('px'):
        raise HTTPException(status_code=400, detail="signature_font_size must end with 'px' (e.g., '13px')")
    
    # Validate image dimensions
    for field, value in [('image_width', req.image_width), ('image_height', req.image_height)]:
        if value is not None:
            if not any(value.endswith(unit) for unit in ('px', '%', 'em', 'rem', 'vw', 'vh')) and value != 'auto':
                raise HTTPException(status_code=400, detail=f"{field} must end with 'px', '%', 'em', 'rem', 'vw', 'vh' or be 'auto'")
    
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    try:
        updates = []
        params = []
        
        field_map = {
            'email_font': 'email_font',
            'email_font_size': 'email_font_size',
            'signature_font': 'signature_font',
            'signature_font_size': 'signature_font_size',
            'signature_mode': 'signature_mode',
            'team': 'team',
            'image_width': 'image_width',
            'image_height': 'image_height',
        }
        
        for req_field, db_field in field_map.items():
            value = getattr(req, req_field)
            if value is not None:
                updates.append(f"{db_field} = %s")
                params.append(value.upper() if req_field == 'team' else value)
        
        if not updates:
            raise HTTPException(status_code=400, detail="No valid fields to update")
        
        updates.append("updated_at = NOW()")
        params.append(real_uid)
        
        query = f"UPDATE users SET {', '.join(updates)} WHERE id = %s RETURNING id, username, email, full_name, role, team, is_active, is_approved, email_font, email_font_size, signature_font, signature_font_size, signature, signature_mode, image_width, image_height"
        cur.execute(query, params)
        user = cur.fetchone()
        conn.commit()
        
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        return dict(user)
    finally:
        cur.close()
        conn.close()


@router.post("/logout")
def logout(request: Request, user_id: Optional[str] = Header(None, alias="X-User-Id")):
    auth_header = request.headers.get("authorization", "")
    token = None
    if auth_header.lower().startswith("bearer "):
        token = auth_header[7:].strip()
    
    if token:
        try:
            conn = get_db_connection()
            cur = conn.cursor()
            cur.execute("DELETE FROM sessions WHERE token = %s", (token,))
            conn.commit()
            cur.close()
            conn.close()
        except Exception as e:
            logger.error(f"Logout session revoke failed: {e}")
    
    return {"success": True, "message": "Logged out"}


class AccessRequest(BaseModel):
    user_id: int


@router.post("/request-access")
def request_access(req: AccessRequest, request: Request):
    from app.services.email_service import send_email
    from app.utils.auth_helpers import get_daily_email_limit
    
    verified_user_id = getattr(request.state, "user_id", None)
    if not verified_user_id:
        raise HTTPException(status_code=401, detail="Authentication required")
    
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    
    cur.execute("SELECT id, username, email, full_name FROM users WHERE id = %s", (verified_user_id,))
    user = cur.fetchone()
    
    cur.execute("SELECT email, full_name, username FROM users WHERE role = 'ADMIN' LIMIT 1")
    admin = cur.fetchone()
    
    cur.close()
    conn.close()
    
    # Resolve backend URL
    base_url = os.getenv("BACKEND_URL")
    if not base_url or base_url.lower() == "null" or "localhost" in base_url.lower():
        if os.getenv("RENDER_EXTERNAL_URL"):
            base_url = os.getenv("RENDER_EXTERNAL_URL")
    
    if not base_url or base_url.lower() == "null" or base_url.strip() == "":
        base_url = "http://127.0.0.1:8000"
    
    base_url = base_url.rstrip("/")
    if not base_url.startswith("http"):
        base_url = f"https://{base_url}"
        
    approve_url = f"{base_url}/api/admin/approve-user/{user['id']}"
    logger.info(f"Generated Approval URL: {approve_url}")
    
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
    
    res = send_email(
        to_email=admin['email'],
        subject=subject,
        html_content=html_content,
        from_email=admin['email'],
        from_name="LeadStream Security",
        is_system_email=True,
        user_id=1
    )
    success = res[0] if isinstance(res, tuple) else res
    
    if not success:
        raise HTTPException(status_code=500, detail="Failed to send notification email")
        
    return {"message": "Access request sent to administrator"}


# Google OAuth endpoints would go here - omitted for brevity
# They follow the same pattern as the original auth.py