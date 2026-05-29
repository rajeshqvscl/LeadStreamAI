import logging
import base64
from fastapi import APIRouter, Request, Response
from app.database import get_db_connection

logger = logging.getLogger(__name__)
router = APIRouter(tags=["tracking"])

TRANSPARENT_GIF = base64.b64decode(
    "R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7"
)

@router.get("/track/open/{token}")
async def track_open(token: str, request: Request):
    try:
        conn = get_db_connection()
        cur = conn.cursor()

        cur.execute("SELECT id, email_status FROM leads_raw WHERE tracking_token = %s", (token,))
        lead = cur.fetchone()
        if lead:
            lead_id = lead['id']
            current_status = lead['email_status']
            if current_status in ('SENT', 'CONTACTED'):
                cur.execute("UPDATE leads_raw SET email_status = 'OPENED', updated_at = NOW() WHERE id = %s", (lead_id,))
                conn.commit()

                from app.models.lead import add_activity_log
                add_activity_log(lead_id, "OPENED", "Email opened (tracking pixel)", "system")

        cur.close()
        conn.close()
    except Exception as e:
        logger.error(f"Track open failed for token {token}: {e}")

    return Response(content=TRANSPARENT_GIF, media_type="image/gif")
