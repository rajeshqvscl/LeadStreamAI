
from app.models.campaign import (
    create_campaign,
    delete_campaign,
    get_campaign_by_id,
    get_campaigns,
    update_campaign,
)
from fastapi import APIRouter, Header, HTTPException, Request
from pydantic import BaseModel

router = APIRouter()

class CampaignCreate(BaseModel):
    name: str
    description: str | None = None
    tone: str | None = 'professional'
    target_industry: str | None = None
    target_persona: str | None = None
    subject: str | None = None
    html_body: str | None = None
    context_prompt: str | None = None
    strategy_prompt: str | None = None
    is_active: bool | None = True
    target_companies: str | None = None

class CampaignUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    tone: str | None = None
    target_industry: str | None = None
    target_persona: str | None = None
    subject: str | None = None
    html_body: str | None = None
    context_prompt: str | None = None
    strategy_prompt: str | None = None
    is_active: bool | None = None
    target_companies: str | None = None

@router.post("/campaigns")
def api_create_campaign(campaign: CampaignCreate, user_id: str | None = Header(None, alias="X-User-Id")):
    import psycopg2.extras
    from app.database import get_db_connection

    try:
        data = campaign.dict()
        data['user_id'] = user_id

        # Fetch user_name for metadata
        if user_id:
            conn = get_db_connection()
            cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
            uid = user_id if user_id.isdigit() else "1"
            cur.execute("SELECT full_name, username FROM users WHERE id = %s", (uid,))
            u = cur.fetchone()
            if u:
                data['user_name'] = u['full_name'] or u['username']
            cur.close()
            conn.close()

        return create_campaign(data)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/campaigns")
def api_get_campaigns(
    limit: int = 20,
    offset: int = 0,
    active_only: bool = False,
    user_id: str | None = Header(None, alias="X-User-Id")
):
    return get_campaigns(limit, offset, active_only, user_id)

@router.get("/campaigns/{id}")
def api_get_campaign(id: int, user_id: str | None = Header(None, alias="X-User-Id")):
    campaign = get_campaign_by_id(id, user_id)
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    return campaign

@router.put("/campaigns/{id}")
def api_update_campaign(id: int, campaign: CampaignUpdate, user_id: str | None = Header(None, alias="X-User-Id")):
    updated = update_campaign(id, campaign.dict(exclude_unset=True), user_id)
    if not updated:
        raise HTTPException(status_code=404, detail="Campaign not found")
    return updated

@router.delete("/campaigns/{id}")
def api_delete_campaign(id: int, user_id: str | None = Header(None, alias="X-User-Id")):
    if delete_campaign(id, user_id):
        return {"message": "Campaign deleted successfully"}
    raise HTTPException(status_code=404, detail="Campaign not found")



class CampaignAddLeads(BaseModel):
    lead_ids: list[int]

@router.post("/campaigns/{id}/add-leads")
def api_add_leads_to_campaign(id: int, req: CampaignAddLeads):
    campaign = get_campaign_by_id(id)
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")

    added_count = 0
    for lead_id in req.lead_ids:
        try:
            CampaignTrackingService.add_recipient(id, lead_id)
            added_count += 1
        except Exception:
            continue # Skip duplicates or errors

    return {"message": f"Successfully added {added_count} leads to campaign"}

from app.services.campaign_tracking import CampaignTrackingService


# Tracking endpoints (prefixed with /campaigns to avoid conflict with leads tracking in tracking.py)
@router.get("/campaigns/track/open/{token}")
async def track_open(token: str, request: Request):
    recipient = CampaignTrackingService.get_recipient_by_token(token)
    if recipient:
        CampaignTrackingService.log_event(
            recipient['campaign_id'],
            recipient['id'],
            'OPEN',
            ip_address=request.client.host,
            user_agent=request.headers.get('user-agent')
        )
    # Return a 1x1 transparent pixel (simulated as JSON for now)
    return {"message": "Open tracked"}

@router.get("/campaigns/track/click/{token}")
async def track_click(token: str, request: Request, url: str):
    recipient = CampaignTrackingService.get_recipient_by_token(token)
    if recipient:
        CampaignTrackingService.log_event(
            recipient['campaign_id'],
            recipient['id'],
            'CLICK',
            ip_address=request.client.host,
            user_agent=request.headers.get('user-agent')
        )
    return {"message": "Click tracked", "redirect_to": url}
