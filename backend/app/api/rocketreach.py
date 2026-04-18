import os
import logging
import requests
from fastapi import APIRouter, HTTPException, Header, Query
from pydantic import BaseModel
from typing import Optional
from dotenv import load_dotenv
from pathlib import Path
import psycopg2.extras
from app.database import get_db_connection

def normalize_user_id(user_id):
    if not user_id or user_id in ('admin', 'undefined', 'null', ''):
        return '1'
    try:
        return str(int(user_id))
    except (ValueError, TypeError):
        return '1'


load_dotenv(dotenv_path=Path(__file__).resolve().parent.parent / ".env")
logger = logging.getLogger(__name__)
router = APIRouter()

ROCKETREACH_API_KEY = os.getenv("ROCKETREACH_API_KEY", "")
RR_BASE = "https://api.rocketreach.co/api/v2"


class AddLeadRequest(BaseModel):
    rr_id: Optional[int] = None
    first_name: str
    last_name: Optional[str] = ""
    email: Optional[str] = ""
    company_name: Optional[str] = ""
    persona: Optional[str] = "UNKNOWN"
    validation_status: Optional[str] = "VALID"


@router.get("/rocketreach/search")
def search_rocketreach(
    name: Optional[str] = Query(None),
    title: Optional[str] = Query(None),
    company: Optional[str] = Query(None),
    location: Optional[str] = Query(None),
    industry: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    user_id: Optional[str] = Header(None, alias="X-User-Id"),
):
    """Free lookup search — no credits consumed. Searches for people profiles."""
    if not ROCKETREACH_API_KEY:
        raise HTTPException(status_code=400, detail="ROCKETREACH_API_KEY is not configured in .env file")

    headers = {
        "Api-Key": ROCKETREACH_API_KEY,
        "Content-Type": "application/json",
    }

    query_parts = {}
    if name:
        query_parts["name"] = name
    if title:
        query_parts["current_title"] = [title]
    if company:
        query_parts["current_employer"] = [company]
    if location:
        query_parts["location"] = [location]
    if industry:
        query_parts["industry"] = [industry]

    if not query_parts:
        raise HTTPException(status_code=400, detail="At least one search field is required")

    payload = {
        "query": query_parts,
        "start": (page - 1) * 50 + 1,
        "page_size": 50,
    }

    try:
        resp = requests.post(
            f"{RR_BASE}/person/search",
            json=payload,
            headers=headers,
            timeout=15
        )
        if resp.status_code == 401:
            raise HTTPException(status_code=400, detail="Invalid RocketReach API key. Check your .env file.")
        if not resp.ok:
            logger.error(f"RocketReach error: {resp.status_code} {resp.text}")
            raise HTTPException(status_code=resp.status_code, detail=f"RocketReach API error: {resp.text[:200]}")

        data = resp.json()
        profiles = data.get("profiles", [])
        total = data.get("pagination", {}).get("total", len(profiles))
        return {"profiles": profiles, "total": total}

    except requests.exceptions.Timeout:
        raise HTTPException(status_code=504, detail="RocketReach request timed out. Please try again.")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"RocketReach Search Error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/rocketreach/credits")
def get_credit_stats(user_id: Optional[str] = Header(None, alias="X-User-Id")):
    """Returns the number of export credits used from the database."""
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    try:
        cur.execute("SELECT COUNT(*) as used FROM activity_log WHERE action = 'RR_EXPORT'")
        row = cur.fetchone()
        used = row['used'] if row else 0
        return {"used": used, "remaining": max(0, 2400 - used)}
    except Exception as e:
        return {"used": 0, "remaining": 2400}
    finally:
        cur.close()
        conn.close()


@router.post("/rocketreach/add-lead")
def add_rocketreach_lead(
    req: AddLeadRequest,
    user_id: Optional[str] = Header(None, alias="X-User-Id"),
):
    """Adds a searched profile directly to the Lead Pipeline (no credit spent)."""
    uid = normalize_user_id(user_id)

    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

    try:
        # Check for duplicates
        if req.email:
            cur.execute("SELECT id FROM leads_raw WHERE email = %s AND user_id = %s", (req.email, uid))
            if cur.fetchone():
                raise HTTPException(status_code=409, detail=f"Lead with email {req.email} already exists in your pipeline.")

        cur.execute("""
            INSERT INTO leads_raw
                (first_name, last_name, email, company_name, persona, validation_status, source, user_id, manual_entry, created_at)
            VALUES
                (%s, %s, %s, %s, %s, %s, 'rocketreach', %s, TRUE, NOW())
            RETURNING id
        """, (
            req.first_name,
            req.last_name or '',
            req.email or '',
            req.company_name or '',
            req.persona or 'UNKNOWN',
            req.validation_status or 'VALID',
            uid,
        ))
        new_id = cur.fetchone()['id']
        conn.commit()

        # Log activity
        try:
            cur.execute(
                "INSERT INTO activity_log (lead_id, user_id, action, notes) VALUES (%s, %s, 'RR_LOOKUP', 'Lead added from RocketReach free lookup')",
                (new_id, uid)
            )
            conn.commit()
        except:
            pass

        return {"message": "Lead added to pipeline successfully!", "lead_id": new_id}
    except HTTPException:
        raise
    except Exception as e:
        conn.rollback()
        logger.error(f"Add RocketReach lead error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        cur.close()
        conn.close()
