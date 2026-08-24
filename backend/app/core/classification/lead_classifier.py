"""
Lead Classifier
Deterministic keyword-based classification for lead type and sector.
Single source of truth - used by insert_lead, drafts, admin_dashboard, etc.
"""

from typing import Tuple, Optional
from app.core.config import constants


class LeadClassifier:
    """
    Classifies leads based on company name, designation, remarks, sector, and owner.
    Hardcoded keyword rules - deterministic, testable, no ML.
    """
    
    def __init__(self):
        self.investor_keywords = constants.INVESTOR_KEYWORDS
        self.client_keywords = constants.CLIENT_KEYWORDS
        self.investor_sectors = constants.INVESTOR_SECTORS
        self.client_sectors = constants.CLIENT_SECTORS
        self.owner_overrides = constants.OWNER_OVERRIDES
    
    def classify(
        self,
        company_name: str = "",
        designation: str = "",
        remarks: str = "",
        current_sector: Optional[str] = None,
        owner_name: Optional[str] = None,
    ) -> Tuple[str, str]:
        """
        Returns (lead_type, sector)
        lead_type: "INVESTOR" or "CLIENT"
        sector: specific sector string or "Investor - General" / "Other"
        """
        # 1. Owner-based override (highest priority)
        if owner_name:
            owner_lower = owner_name.lower()
            for key, (lt, sec) in self.owner_overrides.items():
                if key in owner_lower:
                    return lt, sec
        
        # 2. Keyword matching on combined text
        text = f"{company_name or ''} {designation or ''} {remarks or ''}".lower()
        
        # Determine lead type
        lead_type = "CLIENT"
        if any(kw in text for kw in self.investor_keywords):
            lead_type = "INVESTOR"
        
        # Determine sector
        sectors = self.investor_sectors if lead_type == "INVESTOR" else self.client_sectors
        
        for sector_name, tokens in sectors.items():
            if any(token in text for token in tokens):
                return lead_type, sector_name
        
        # No specific sector matched
        if lead_type == "INVESTOR":
            return "INVESTOR", "Investor - General"
        return "CLIENT", "Other"


# Singleton
_classifier: Optional[LeadClassifier] = None


def get_lead_classifier() -> LeadClassifier:
    global _classifier
    if _classifier is None:
        _classifier = LeadClassifier()
    return _classifier


def infer_lead_classification(
    company_name: str,
    designation: str,
    remarks: str,
    current_sector: Optional[str] = None,
    owner_name: Optional[str] = None,
) -> Tuple[str, str]:
    """
    Backward-compatible function for existing calls.
    Delegates to LeadClassifier.
    """
    return get_lead_classifier().classify(
        company_name=company_name,
        designation=designation,
        remarks=remarks,
        current_sector=current_sector,
        owner_name=owner_name,
    )