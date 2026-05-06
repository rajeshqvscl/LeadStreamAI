# app/utils/classification.py

def infer_lead_classification(company_name, designation, remarks, current_sector=None):
    """
    Unified logic to determine lead_type and sector based on keywords.
    """
    text = f"{company_name or ''} {designation or ''} {remarks or ''}".lower()
    
    # 1. Determine Type
    lead_type = "CLIENT"
    if any(x in text for x in ["venture", "capital", "equity", "partners", "investor", "investment", "vc ", "asset management", "family office"]):
        lead_type = "INVESTOR"
    
    # 2. Determine Sector (Industry)
    # If the user provided a sector, or if we have a valid industry already, keep it.
    # Otherwise, try to infer from keywords.
    sector = current_sector
    
    # List of keywords for inference
    keywords = {
        "Defence": ["defence", "military", "aerospace", "drdo", "naval", "weapon", "tactical", "security", "surveillance", "defense", "missile", "armored"],
        "SaaS": ["saas", "software as a service", "subscription software", "cloud platform", "b2b software", "crm", "erp"],
        "FinTech": ["fintech", "payment", "banking", "finance", "wealthtech", "insurtech", "crypto", "blockchain", "wallet", "lending"],
        "AI": ["artificial intelligence", " ai ", "machine learning", " ml ", "neural network", "deep learning", "generative ai", "openai", "bot", "algorithm", "automation", "intelligence", "qvscl"],
        "Consulting": ["consulting", "advisory", "strategy", "management consulting", "consultant", "adviser"],
        "Manufacturing": ["manufacturing", "factory", "industrial", "robotics", "automation", "hardware", "machinery"],
        "Healthcare": ["healthcare", "medical", "hospital", "pharma", "biotech", "life science", "genomics", "wellness"],
        "EdTech": ["edtech", "education", "learning", "e-learning", "academy", "university", "college", "skill"],
        "AgriTech": ["agritech", "agriculture", "farming", "crop", "agri", "foodtech", "livestock", "harvest"],
        "E-commerce": ["ecommerce", "e-commerce", "retail", "marketplace", "d2c", "shopping", "store"],
        "CleanTech": ["cleantech", "renewable", "solar", "energy", "green tech", "environment", "sustainability", "carbon", "electric"],
        "Logistics": ["logistics", "supply chain", "shipping", "freight", "delivery", "warehouse", "transport"],
        "PropTech": ["proptech", "real estate", "property", "construction", "housing", "building"]
    }

    # Only re-infer if the sector is generic or missing
    if not sector or sector.upper() in ["OTHER", "CLIENT", "INVESTOR", "NULL", "NONE"]:
        for industry, tokens in keywords.items():
            if any(t in text for t in tokens):
                sector = industry
                break
        
        # FINAL GUARD: Ensure sector is NOT Investor or Client
        if sector and sector.upper() in ["INVESTOR", "CLIENT"]:
            sector = "Other"
        
        if not sector:
            sector = "Other"

    return lead_type, sector
