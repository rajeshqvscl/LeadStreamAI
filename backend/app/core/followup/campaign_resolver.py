"""
Follow-up Campaign Resolver
SINGLE SOURCE: which campaign/template for this lead.
Removes duplication from followup_service.py, drafts.py, generate_followup_preview().
"""

from typing import List, Tuple, Callable, Optional
from dataclasses import dataclass
from app.core.config import constants


@dataclass
class LeadData:
    """Minimal lead data needed for campaign resolution"""
    id: int
    draft_template_used: str = ""
    original_subject: str = ""
    email_draft: str = ""
    persona: str = ""
    sector: str = ""
    sender_name: str = ""
    sender_email: str = ""
    lead_type: str = "INVESTOR"
    is_agritech: bool = False


class CampaignResolver:
    """
    Resolves which campaign template to use for a lead.
    Rules are evaluated in order - first match wins.
    """
    
    # Rules: (campaign_key, predicate_function)
    # Order matters - more specific rules first
    CAMPAIGN_RULES: List[Tuple[str, Callable[[LeadData], bool]]] = [
        # Explicit template name matches (highest priority)
        ("INVESTOR_PALAK_ADVISORY", 
         lambda l: l.draft_template_used in ("palak_mam_corporate_advisory", "palak_mam_mna_fundraising", "palak_mam_Draft_1")
                  or "corporate advisory" in (l.original_subject or "").lower()
                  or ("corporate advisory" in (l.email_draft or "").lower() and "m&a" not in (l.email_draft or "").lower())),
        
        ("INVESTOR_KAJAL_HEALTH_ECOSYSTEM", 
         lambda l: l.draft_template_used == "kajal_mam_health_ecosystem"),
        
        ("INVESTOR_KAJAL_JV", 
         lambda l: l.draft_template_used in ("kajal_mam_jv", "kajal_mam_qvscl_intro")
                  or "jv & investment" in (l.original_subject or "").lower()
                  or "strategic partnership opportunity" in (l.original_subject or "").lower()),
        
        ("INVESTOR_KAJAL_GENERIC", 
         lambda l: l.draft_template_used in ("kajal_mam_hyphen", "kajal_mam_agritech")),
        
        # Content-based detection (subject/draft/persona/sector)
        ("INVESTOR_AI_HIRING", 
         lambda l: any("hiring" in f.lower() or "recruitment" in f.lower() 
                      for f in [l.original_subject, l.email_draft, l.persona, l.sector] if f)),
        
        ("INVESTOR_HEALTHTECH", 
         lambda l: any("health" in f.lower() or "diagnostic" in f.lower() 
                      for f in [l.original_subject, l.email_draft, l.persona, l.sector] if f)),
        
        ("INVESTOR_DEFENCE", 
         lambda l: any(kw in f.lower() for kw in ["defence", "deeptech", "idex"] 
                      for f in [l.original_subject, l.email_draft, l.persona, l.sector] if f)),
        
        # Agritech with sender-specific variant
        ("INVESTOR_YASHIKA_AGRITECH", 
         lambda l: l.is_agritech and "yashika" in f"{l.sender_name} {l.sender_email} {l.draft_template_used}".lower()),
        
        ("INVESTOR_AGRITECH", 
         lambda l: l.is_agritech or "agritech" in (l.original_subject or "").lower() or "climate" in (l.original_subject or "").lower()),
        
        # Fallback by lead_type
        ("CLIENT", lambda l: l.lead_type == "CLIENT"),
        ("INVESTOR_GENERIC", lambda l: True),  # Always matches last
    ]
    
    @classmethod
    def resolve(cls, lead: LeadData) -> str:
        """
        Resolve campaign key for a lead.
        Returns campaign key that maps to DEFAULT_TEMPLATES.
        """
        # Compute agritech flag if not set
        if not lead.is_agritech:
            lead.is_agritech = (
                "agritech" in (lead.original_subject or "").lower()
                or "agritech" in (lead.email_draft or "").lower()
                or "agritech" in (lead.persona or "").lower()
                or "agritech" in (lead.sector or "").lower()
                or "climate" in (lead.original_subject or "").lower()
                or "climate" in (lead.email_draft or "").lower()
            )
        
        for campaign_key, rule in cls.CAMPAIGN_RULES:
            try:
                if rule(lead):
                    return campaign_key
            except Exception:
                continue
        
        return "INVESTOR_GENERIC"
    
    @classmethod
    def get_template(cls, campaign_key: str, stage: int) -> str:
        """Get template for campaign and stage, with fallback"""
        templates = constants.DEFAULT_TEMPLATES.get(campaign_key)
        if not templates:
            templates = constants.DEFAULT_TEMPLATES["INVESTOR_GENERIC"]
        
        template = templates.get(stage)
        if not template:
            template = templates.get(1, "Hi {name},\n\nFollowing up on my previous email.\n\nBest regards,")
        
        return template


def get_campaign_for_lead(lead: dict) -> str:
    """Convenience function for dict-based leads (legacy compatibility)"""
    lead_data = LeadData(
        id=lead.get("id", 0),
        draft_template_used=lead.get("draft_template_used", "") or "",
        original_subject=lead.get("last_outreach_subject", "") or lead.get("first_outreach_subject", "") or "",
        email_draft=lead.get("email_draft", "") or "",
        persona=lead.get("persona", "") or "",
        sector=lead.get("sector", "") or "",
        sender_name=lead.get("sender_name", "") or lead.get("full_name", "") or "",
        sender_email=lead.get("sender_email", "") or "",
        lead_type=lead.get("lead_type", "INVESTOR") or "INVESTOR",
    )
    return CampaignResolver.resolve(lead_data)