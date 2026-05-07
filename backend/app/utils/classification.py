# app/utils/classification.py

def infer_lead_classification(company_name, designation, remarks, current_sector=None):
    """
    Unified logic to determine lead_type and sector based on keywords.
    """
    text = f"{company_name or ''} {designation or ''} {remarks or ''}".lower()
    
    # 1. Determine Type - More specific investor types
    lead_type = "CLIENT"
    investor_keywords = [
        "venture", "capital", "equity", "partners", "investor", "investment", "vc ", 
        "asset management", "family office", "private equity", "hedge fund", "mutual fund",
        "angel investor", "seed fund", "growth fund", "impact investor", "strategic investor"
    ]
    if any(x in text for x in investor_keywords):
        lead_type = "INVESTOR"
    
    # 2. Investor-specific sectors (more detailed)
    investor_sectors = {
        "VC - Early Stage": ["seed", "pre-seed", "angel", "first check", "early stage", "series a", "pre-series"],
        "VC - Growth": ["series b", "series c", "growth", "late stage", "scale-up"],
        "Private Equity": ["pe ", "private equity", "buyout", "lbo", "growth equity"],
        "Family Office": ["family office", "ultra high net worth", "uhnw", "single family"],
        "Corporate VC": ["corporate venture", "cvc", "strategic investment"],
        "Accelerator": ["accelerator", "startup accelerator", "y combinator", "techstars"],
        "Angel Network": ["angel network", "angel group", " syndicate"],
        "Wealth Manager": ["wealth manager", "wealth advisory", "private banking", "family wealth"],
        "Fund of Funds": ["fund of funds", "fo f", "multi strategy"]
    }
    
    client_sectors = {
        "SaaS": ["saas", "software as a service", "subscription software", "cloud platform", "b2b software", "crm", "erp", "project management"],
        "FinTech": ["fintech", "payment", "banking", "finance", "wealthtech", "insurtech", "crypto", "blockchain", "wallet", "lending", "neobank"],
        "AI & ML": ["artificial intelligence", " ai ", "machine learning", " ml ", "neural network", "generative ai", " llm ", "model"],
        "Healthcare": ["healthcare", "medical", "hospital", "pharma", "biotech", "life science", "genomics", "wellness", "telehealth"],
        "E-commerce": ["ecommerce", "e-commerce", "retail", "marketplace", "d2c", "shopping", "store", "omnichannel"],
        "EdTech": ["edtech", "education", "learning", "e-learning", "academy", "university", "college", "skill", "lms"],
        "Logistics": ["logistics", "supply chain", "shipping", "freight", "delivery", "warehouse", "transport", "last mile"],
        "CleanTech": ["cleantech", "renewable", "solar", "energy", "green tech", "environment", "sustainability", "ev ", "electric vehicle"],
        "Cybersecurity": ["cybersecurity", "security", "privacy", "data protection", "infosec", "threat", "ゼロ信任"],
        "PropTech": ["proptech", "real estate", "property", "construction", "housing", "building", "reit"],
        "Manufacturing": ["manufacturing", "factory", "industrial", "robotics", "hardware", "machinery", "3d printing"],
        "AgriTech": ["agritech", "agriculture", "farming", "crop", "agri", "foodtech", "livestock"],
        "Consulting": ["consulting", "advisory", "strategy", "management consulting", "consultant", "adviser"],
        "Media & Entertainment": ["media", "entertainment", "content", "streaming", "gaming", "creator economy"],
        "Food & Beverage": ["food", "beverage", "restaurant", "foodtech", "dark kitchen", "qsr"],
        "HR Tech": ["hr tech", "human resources", "recruitment", "ats", "hiring", "payroll", "staffing"],
        "Data Analytics": ["data analytics", "bi ", "business intelligence", "dashboard", "data science", "analytics"],
        "Cloud Infra": ["cloud", "infrastructure", "devops", "aws", "azure", "gcp", "hosting"],
        "Legal Tech": ["legal tech", "law", "contract", "compliance", "regtech"]
    }
    
    # 3. Determine Sector
    sector = current_sector
    
    if lead_type == "INVESTOR":
        for ind, tokens in investor_sectors.items():
            if any(t in text for t in tokens):
                sector = ind
                break
        if not sector:
            sector = "Investor - General"
    else:
        for ind, tokens in client_sectors.items():
            if any(t in text for t in tokens):
                sector = ind
                break
    
    # FINAL GUARD: Ensure sector is NOT Investor or Client (confusing values)
    if sector and sector.upper() in ["INVESTOR", "CLIENT"]:
        sector = "Other"
    if not sector:
        sector = "Other"
    
    return lead_type, sector
