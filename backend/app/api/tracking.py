import logging
import base64
from urllib.parse import quote, unquote
import re
from fastapi import APIRouter, Request, Response
from fastapi.responses import RedirectResponse
from app.database import get_db_connection

logger = logging.getLogger(__name__)
router = APIRouter(tags=["tracking"])

TRANSPARENT_GIF = base64.b64decode(
    "R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7"
)

def inject_click_tracking(html_content: str, tracking_token: str, backend_url: str) -> str:
    """Replace all <a href=\"...\"> links in HTML with tracking redirect URLs.
    Only modifies the href attribute — visible text/content stays unchanged."""
    if not html_content or not tracking_token:
        return html_content

    def _replace_link(match):
        prefix = match.group(1)
        url = match.group(2)
        # Skip mailto:, tel:, #anchor, and already-tracked links
        if any(url.startswith(x) for x in ['mailto:', 'tel:', '#', 'javascript:']) or '/api/track/click/' in url:
            return match.group(0)
        tracked = f'{prefix}"{backend_url}/api/track/click/{tracking_token}?url={quote(url, safe="")}"'
        return tracked

    # Match <a href="url"> or <a href='url'>
    pattern = re.compile(r'(<a\s+[^>]*?href\s*=\s*["\'])([^"\']+)(["\'])', re.IGNORECASE)
    return pattern.sub(_replace_link, html_content)


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


@router.get("/track/click/{token}")
async def track_click(token: str, request: Request):
    url = request.query_params.get("url", "")
    try:
        conn = get_db_connection()
        cur = conn.cursor()

        cur.execute("SELECT id FROM leads_raw WHERE tracking_token = %s", (token,))
        lead = cur.fetchone()
        if lead:
            lead_id = lead['id']
            cur.execute("UPDATE leads_raw SET email_status = 'CLICKED', updated_at = NOW() WHERE id = %s AND email_status IN ('SENT', 'OPENED', 'CONTACTED')", (lead_id,))
            conn.commit()

            from app.models.lead import add_activity_log
            add_activity_log(lead_id, "CLICKED", f"Link clicked: {url[:200]}", "system")

        cur.close()
        conn.close()
    except Exception as e:
        logger.error(f"Track click failed for token {token}: {e}")

    if url:
        return RedirectResponse(url=unquote(url))
    return Response(content="OK", status_code=200)
