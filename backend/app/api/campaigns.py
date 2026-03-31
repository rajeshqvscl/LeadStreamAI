from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel
from typing import List, Optional
from app.models.campaign import (
    create_campaign, get_campaigns, get_campaign_by_id, 
    update_campaign, delete_campaign
)

router = APIRouter()

class CampaignCreate(BaseModel):
    name: str
    description: Optional[str] = None
    tone: Optional[str] = 'professional'
    target_industry: Optional[str] = None
    target_persona: Optional[str] = None
    subject: Optional[str] = None
    html_body: Optional[str] = None
    context_prompt: Optional[str] = None
    strategy_prompt: Optional[str] = None
    is_active: Optional[bool] = True

class CampaignUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    tone: Optional[str] = None
    target_industry: Optional[str] = None
    target_persona: Optional[str] = None
    subject: Optional[str] = None
    html_body: Optional[str] = None
    context_prompt: Optional[str] = None
    strategy_prompt: Optional[str] = None
    is_active: Optional[bool] = None

@router.post("/campaigns")
def api_create_campaign(campaign: CampaignCreate):
    try:
        return create_campaign(campaign.dict())
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/campaigns")
def api_get_campaigns(
    limit: int = 20, 
    offset: int = 0, 
    active_only: bool = False
):
    return get_campaigns(limit, offset, active_only)

@router.get("/campaigns/{id}")
def api_get_campaign(id: int):
    campaign = get_campaign_by_id(id)
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    return campaign

@router.put("/campaigns/{id}")
def api_update_campaign(id: int, campaign: CampaignUpdate):
    updated = update_campaign(id, campaign.dict(exclude_unset=True))
    if not updated:
        raise HTTPException(status_code=404, detail="Campaign not found")
    return updated

@router.delete("/campaigns/{id}")
def api_delete_campaign(id: int):
    if delete_campaign(id):
        return {"message": "Campaign deleted successfully"}
    raise HTTPException(status_code=404, detail="Campaign not found")

class CampaignAddLeads(BaseModel):
    lead_ids: List[int]

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

# Tracking endpoints
@router.get("/track/open/{token}")
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

@router.get("/track/click/{token}")
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
