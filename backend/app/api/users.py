from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import List, Optional
import hashlib
from app.database import get_db_connection
import psycopg2
from datetime import datetime

router = APIRouter()

class UserBase(BaseModel):
    username: str
    email: str
    full_name: Optional[str] = None
    role: str = "USER"
    is_active: bool = True

class UserCreate(UserBase):
    password: str

class UserUpdate(BaseModel):
    email: Optional[str] = None
    full_name: Optional[str] = None
    role: Optional[str] = None
    is_active: Optional[bool] = None
    password: Optional[str] = None

@router.get("/users/")
def list_users(role: Optional[str] = None):
    conn = get_db_connection()
    cur = conn.cursor()
    
    query = "SELECT id, username, email, full_name, role, is_active, created_at FROM users"
    params = []
    if role:
        query += " WHERE role = %s"
        params.append(role)
    
    query += " ORDER BY created_at DESC"
    cur.execute(query, params)
    users = cur.fetchall()
    
    cur.close()
    conn.close()
    return {"users": users, "total": len(users)}

@router.post("/users/")
def create_user(user: UserCreate):
    conn = get_db_connection()
    cur = conn.cursor()
    
    # Hash password
    password_hash = hashlib.sha256(user.password.encode()).hexdigest()
    
    try:
        cur.execute("""
            INSERT INTO users (username, email, full_name, password_hash, role, is_active)
            VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING id, username, email, full_name, role, is_active, created_at
        """, (user.username, user.email, user.full_name, password_hash, user.role, user.is_active))
        
        new_user = cur.fetchone()
        conn.commit()
    except psycopg2.IntegrityError:
        conn.rollback()
        raise HTTPException(status_code=400, detail="Username or email already exists")
    finally:
        cur.close()
        conn.close()
        
    return new_user

@router.put("/users/{user_id}")
def update_user(user_id: int, user: UserUpdate):
    conn = get_db_connection()
    cur = conn.cursor()
    
    update_data = user.dict(exclude_unset=True)
    if not update_data:
        raise HTTPException(status_code=400, detail="No data provided for update")
    
    if "password" in update_data:
        update_data["password_hash"] = hashlib.sha256(update_data.pop("password").encode()).hexdigest()
        
    set_clause = ", ".join([f"{k} = %s" for k in update_data.keys()])
    params = list(update_data.values())
    params.append(user_id)
    
    cur.execute(f"UPDATE users SET {set_clause} WHERE id = %s RETURNING id, username, email, full_name, role, is_active, created_at", params)
    updated_user = cur.fetchone()
    
    if not updated_user:
        conn.rollback()
        cur.close()
        conn.close()
        raise HTTPException(status_code=404, detail="User not found")
        
    conn.commit()
    cur.close()
    conn.close()
    return updated_user

@router.delete("/users/{user_id}")
def delete_user(user_id: int):
    conn = get_db_connection()
    cur = conn.cursor()
    
    # Actually deactivate instead of delete for safety
    cur.execute("UPDATE users SET is_active = FALSE WHERE id = %s", (user_id,))
    
    if cur.rowcount == 0:
        cur.close()
        conn.close()
        raise HTTPException(status_code=404, detail="User not found")
        
    conn.commit()
    cur.close()
    conn.close()
    return {"message": "User suspended successfully"}

@router.post("/users/{user_id}/resume")
def resume_user(user_id: int):
    conn = get_db_connection()
    cur = conn.cursor()
    
    cur.execute("UPDATE users SET is_active = TRUE WHERE id = %s", (user_id,))
    
    if cur.rowcount == 0:
        cur.close()
        conn.close()
        raise HTTPException(status_code=404, detail="User not found")
        
    conn.commit()
    cur.close()
    conn.close()
    return {"message": "User resumed successfully"}

@router.delete("/users/{user_id}/hard")
def hard_delete_user(user_id: int):
    conn = get_db_connection()
    cur = conn.cursor()
    
    cur.execute("DELETE FROM users WHERE id = %s", (user_id,))
    
    if cur.rowcount == 0:
        cur.close()
        conn.close()
        raise HTTPException(status_code=404, detail="User not found")
        
    conn.commit()
    cur.close()
    conn.close()
    return {"message": "User record permanently deleted"}

