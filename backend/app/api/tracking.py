import logging
import base64
from urllib.parse import quote, unquote
import re
from fastapi import APIRouter, Request, Response
from fastapi.responses import RedirectResponse
from app.database import get_db_connection

logger = logging.getLogger(__name__)
router = APIRouter(tags=["tracking"])

import hashlib

def _make_unique_gif(seed: str) -> bytes:
    """1x1 transparent GIF with unique bytes per token.
    Gmail proxy caches by content hash — unique content forces a fresh fetch for each email."""
    h = hashlib.md5(seed.encode()).digest()
    r, g, b = h[0], h[1], h[2]
    return bytes([
        0x47, 0x49, 0x46, 0x38, 0x39, 0x61,  # GIF89a
        0x01, 0x00, 0x01, 0x00,                # 1x1 px
        0x80, 0x00, 0x00,                      # packed, bg index, aspect
        r, g, b,                               # color 0 — transparent (unique per token)
        0xff, 0xff, 0xff,                      # color 1 — white (unused)
        0x21, 0xf9, 0x04, 0x01, 0x00, 0x00, 0x00, 0x00,  # GCE: transparency on, index 0
        0x2c, 0x00, 0x00, 0x00, 0x00, 0x01, 0x00, 0x01, 0x00, 0x00, 0x02, 0x01, 0x44, 0x00,
        0x3b                                     # trailer
    ])

def inject_click_tracking(html_content: str, tracking_token: str, backend_url: str) -> str:
    """Replace all <a href=\"...\"> links in HTML with tracking redirect URLs.
    Only modifies the href attribute — visible text/content stays unchanged."""
    if not html_content or not tracking_token:
        return html_content

    def _replace_link(match):
        prefix = match.group(1)
        url = match.group(2)
        # Skip mailto:, tel:, #anchor, unsubscribe links, and already-tracked links
        if any(url.startswith(x) for x in ['mailto:', 'tel:', '#', 'javascript:']) or '/api/track/click/' in url or '/unsubscribe' in url:
            return match.group(0)
        tracked = f'{prefix}{backend_url}/api/track/click/{tracking_token}?url={quote(url, safe="")}{match.group(3)}'
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

    return Response(content=_make_unique_gif(token), media_type="image/gif", headers={"Cache-Control": "no-cache, no-store, must-revalidate", "Pragma": "no-cache", "Expires": "0", "Vary": "Accept-Encoding"})


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
