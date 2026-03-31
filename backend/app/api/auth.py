from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional
import os
from dotenv import load_dotenv
from pathlib import Path

# Fix: Ensure .env is loaded in the API layer too
env_path = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(dotenv_path=env_path, override=True)


router = APIRouter()

class LoginRequest(BaseModel):
    username: str
    password: str

@router.post("/auth/login")
def login(req: LoginRequest):
    admin_user = os.getenv("ADMIN_USERNAME")
    admin_pass = os.getenv("ADMIN_PASSWORD")
    
    if not admin_user or not admin_pass:
        # If not configured, deny login
        from fastapi import HTTPException
        raise HTTPException(status_code=500, detail="Server authentication not configured")

    if req.username == admin_user and req.password == admin_pass:
        return {
            "access_token": "dummy_token",
            "token_type": "bearer"
        }
    
    from fastapi import HTTPException
    raise HTTPException(status_code=401, detail="Invalid username or password")
