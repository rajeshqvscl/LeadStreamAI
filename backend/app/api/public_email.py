from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional
import logging
from app.database import get_db_connection
import psycopg2.extras
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/public", tags=["public_email"])

class UnsubscribeRequest(BaseModel):
    token: str

class ResubscribeRequest(BaseModel):
    token: str


def _get_lead_and_prefs_by_token(token: str):
    """Look up a lead by unsubscribe_token, return lead dict + email_preferences dict or None."""
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    try:
        cur.execute("""
            SELECT id, email, first_name, last_name, company_name, source,
                   email_opt_in, is_unsubscribed
            FROM leads_raw
            WHERE unsubscribe_token = %s
        """, (token,))
        lead = cur.fetchone()
        if not lead:
            raise HTTPException(status_code=404, detail="Invalid unsubscribe link")
        lead = dict(lead)

        # Check email_preferences table
        cur.execute("""
            SELECT * FROM email_preferences
            WHERE unsubscribe_token = %s
        """, (token,))
        prefs = cur.fetchone()
        prefs = dict(prefs) if prefs else None

        return lead, prefs
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        cur.close()
        conn.close()


def _sync_email_preferences(lead: dict, token: str, prefs: Optional[dict] = None):
    """Upsert email_preferences row for a lead, creating or updating as needed."""
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    try:
        if prefs:
            cur.execute("""
                UPDATE email_preferences
                SET marketing_enabled = %s,
                    transactional_enabled = %s,
                    status = %s,
                    updated_at = NOW(),
                    unsubscribed_at = %s
                WHERE id = %s
            """, (
                lead.get('email_opt_in', True),
                True,
                'unsubscribed' if lead.get('is_unsubscribed') else 'subscribed',
                datetime.now(timezone.utc) if lead.get('is_unsubscribed') else prefs.get('unsubscribed_at'),
                prefs['id']
            ))
        else:
            cur.execute("""
                INSERT INTO email_preferences
                    (lead_id, email, unsubscribe_token, marketing_enabled, transactional_enabled, status, unsubscribe_reason)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (unsubscribe_token) DO UPDATE
                SET marketing_enabled = EXCLUDED.marketing_enabled,
                    status = EXCLUDED.status,
                    updated_at = NOW(),
                    unsubscribed_at = CASE WHEN EXCLUDED.status = 'unsubscribed' THEN NOW() ELSE email_preferences.unsubscribed_at END
            """, (
                lead['id'],
                lead['email'],
                token,
                lead.get('email_opt_in', True),
                True,
                'unsubscribed' if lead.get('is_unsubscribed') else 'subscribed',
                'Opted out via email unsubscribe link' if lead.get('is_unsubscribed') else None
            ))
        conn.commit()
    except Exception as e:
        conn.rollback()
        logger.error(f"Failed to sync email_preferences for lead {lead['id']}: {e}")
    finally:
        cur.close()
        conn.close()


def _log_email_event(lead_id: int, event_type: str, metadata: Optional[dict] = None):
    """Insert a row into email_events."""
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("""
            INSERT INTO email_events (lead_id, status, metadata)
            VALUES (%s, %s, %s)
        """, (lead_id, event_type, psycopg2.extras.Json(metadata) if metadata else None))
        conn.commit()
    except Exception as e:
        conn.rollback()
        logger.warning(f"Failed to log email event for lead {lead_id}: {e}")
    finally:
        cur.close()
        conn.close()


@router.get("/unsubscribe/validate")
def validate_unsubscribe_token_public(token: str = Query(...)):
    """Validate an unsubscribe token and return lead preferences (no auth required)."""
    try:
        lead, prefs = _get_lead_and_prefs_by_token(token)
    except HTTPException:
        raise

    already_unsubscribed = lead.get('email_opt_in') is False or lead.get('is_unsubscribed') is True

    return {
        "valid": True,
        "email": lead.get('email'),
        "first_name": lead.get('first_name'),
        "last_name": lead.get('last_name'),
        "company": lead.get('company_name'),
        "source": lead.get('source'),
        "is_unsubscribed": already_unsubscribed,
        "marketing_enabled": prefs.get('marketing_enabled', not already_unsubscribed) if prefs else not already_unsubscribed,
        "status": prefs.get('status', 'unsubscribed' if already_unsubscribed else 'subscribed') if prefs else ('unsubscribed' if already_unsubscribed else 'subscribed')
    }


@router.post("/unsubscribe")
def unsubscribe_public(body: UnsubscribeRequest):
    """Process an unsubscribe by token (no auth required)."""
    from app.api.leads import process_unsubscribe

    try:
        lead, prefs = _get_lead_and_prefs_by_token(body.token)
    except HTTPException:
        raise

    if lead.get('email_opt_in') is False or lead.get('is_unsubscribed') is True:
        return {"success": True, "message": "Already unsubscribed", "email": lead['email']}

    process_unsubscribe(lead['id'])
    lead['email_opt_in'] = False
    lead['is_unsubscribed'] = True
    _sync_email_preferences(lead, body.token, prefs)
    _log_email_event(lead['id'], 'UNSUBSCRIBED', {"source": "public_page", "method": "unsubscribe"})

    return {"success": True, "message": "Successfully unsubscribed", "email": lead['email']}


@router.post("/resubscribe")
def resubscribe_public(body: ResubscribeRequest):
    """Re-enable marketing emails for a previously unsubscribed lead (no auth required)."""
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    try:
        cur.execute("""
            SELECT id, email, source FROM leads_raw WHERE unsubscribe_token = %s
        """, (body.token,))
        lead = cur.fetchone()
        if not lead:
            raise HTTPException(status_code=404, detail="Invalid unsubscribe link")

        lead = dict(lead)

        # Re-enable in leads_raw
        cur.execute("""
            UPDATE leads_raw
            SET email_opt_in = TRUE,
                is_unsubscribed = FALSE,
                followup_status = 'IDLE',
                email_status = 'PENDING',
                updated_at = NOW()
            WHERE id = %s
        """, (lead['id'],))

        # Remove from global blacklist
        cur.execute("DELETE FROM unsubscribe_list WHERE email = %s", (lead['email'],))

        # Update email_preferences
        cur.execute("""
            INSERT INTO email_preferences
                (lead_id, email, unsubscribe_token, marketing_enabled, transactional_enabled, status)
            VALUES (%s, %s, %s, TRUE, TRUE, 'subscribed')
            ON CONFLICT (unsubscribe_token) DO UPDATE
            SET marketing_enabled = TRUE,
                status = 'subscribed',
                unsubscribed_at = NULL,
                updated_at = NOW()
        """, (lead['id'], lead['email'], body.token))

        conn.commit()

        _log_email_event(lead['id'], 'RESUBSCRIBED', {"source": "public_page", "method": "resubscribe"})

        return {"success": True, "message": "Successfully resubscribed", "email": lead['email']}
    except HTTPException:
        raise
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        cur.close()
        conn.close()


@router.get("/preferences")
def get_preferences(token: str = Query(...)):
    """Get email preferences by unsubscribe token (no auth required)."""
    try:
        lead, prefs = _get_lead_and_prefs_by_token(token)
    except HTTPException:
        raise

    return {
        "email": lead['email'],
        "marketing_enabled": prefs.get('marketing_enabled', not (lead.get('email_opt_in') is False)) if prefs else not (lead.get('email_opt_in') is False),
        "transactional_enabled": prefs.get('transactional_enabled', True) if prefs else True,
        "status": prefs.get('status', 'subscribed') if prefs else 'subscribed',
        "unsubscribed_at": prefs.get('unsubscribed_at') if prefs else None
    }
