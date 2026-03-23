from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional

router = APIRouter()

class LoginRequest(BaseModel):
    username: str
    password: str

@router.post("/auth/login")
def login(req: LoginRequest):
    return {
        "access_token": "dummy_token",
        "token_type": "bearer"
    }
