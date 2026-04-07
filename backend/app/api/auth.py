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
        
    # Data is preserved across sessions — leads persist after logout/login

        
    return {
        "access_token": "dummy_token", # In a real app, generate a JWT here
        "token_type": "bearer",
        "user": {
            "id": user['id'],
            "username": user['username'],
            "email": user['email'],
            "full_name": user['full_name'],
            "role": user['role']
        }
    }

