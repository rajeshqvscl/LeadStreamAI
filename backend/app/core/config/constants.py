import re
from typing import Dict, List, Tuple


INVESTOR_KEYWORDS: List[str] = [
    "venture", "capital", "equity", "partners", "investor", "investment", "vc ",
    "asset management", "family office", "private equity", "hedge fund", "mutual fund",
    "angel investor", "seed fund", "growth fund", "impact investor", "strategic investor",
    "vc,", "vc.", "vc)", "vc]",
]

CLIENT_KEYWORDS: List[str] = [
    "saas", "fintech", "software", "client", "customer", "product", "services",
    "b2b", "enterprise", "platform", "solution", "technology", "tech",
]


INVESTOR_SECTORS: Dict[str, List[str]] = {
    "VC - Early Stage": ["seed", "pre-seed", "angel", "first check", "early stage", "series a", "pre-series"],
    "VC - Growth": ["series b", "series c", "growth", "late stage", "scale-up"],
    "Private Equity": ["pe ", "private equity", "buyout", "lbo", "growth equity"],
    "Family Office": ["family office", "ultra high net worth", "uhnw", "single family"],
    "Corporate VC": ["corporate venture", "cvc", "strategic investment"],
    "Accelerator": ["accelerator", "startup accelerator", "y combinator", "techstars"],
    "Angel Network": ["angel network", "angel group", " syndicate"],
    "Wealth Manager": ["wealth manager", "wealth advisory", "private banking", "family wealth"],
    "Fund of Funds": ["fund of funds", "fof", "multi strategy"],
    "Sovereign Wealth": ["sovereign wealth", "swf", "government investment"],
    "Impact Investor": ["impact investor", "impact fund", "esg fund", "sustainable investment"],
}

CLIENT_SECTORS: Dict[str, List[str]] = {
    "SaaS": ["saas", "software as a service", "subscription software", "cloud platform", "b2b software", "crm", "erp", "project management"],
    "FinTech": ["fintech", "payment", "banking", "finance", "wealthtech", "insurtech", "crypto", "blockchain", "wallet", "lending", "neobank"],
    "AI & ML": ["artificial intelligence", " ai ", "machine learning", " ml ", "neural network", "generative ai", " llm ", "model"],
    "Healthcare": ["healthcare", "medical", "hospital", "pharma", "biotech", "life science", "genomics", "wellness", "telehealth"],
    "E-commerce": ["ecommerce", "e-commerce", "retail", "marketplace", "d2c", "shopping", "store", "omnichannel"],
    "EdTech": ["edtech", "education", "learning", "e-learning", "academy", "university", "college", "skill", "lms"],
    "Logistics": ["logistics", "supply chain", "shipping", "freight", "delivery", "warehouse", "transport", "last mile"],
    "CleanTech": ["cleantech", "renewable", "solar", "energy", "green tech", "environment", "sustainability", "ev ", "electric vehicle"],
    "Cybersecurity": ["cybersecurity", "security", "privacy", "data protection", "infosec", "threat"],
    "PropTech": ["proptech", "real estate", "property", "construction", "housing", "building", "reit"],
    "Manufacturing": ["manufacturing", "factory", "industrial", "robotics", "hardware", "machinery", "3d printing"],
    "AgriTech": ["agritech", "agriculture", "farming", "crop", "foodtech", "livestock"],
    "Consulting": ["consulting", "advisory", "strategy", "management consulting", "consultant", "adviser"],
    "Media & Entertainment": ["media", "entertainment", "content", "streaming", "gaming", "creator economy"],
    "Food & Beverage": ["food", "beverage", "restaurant", "foodtech", "dark kitchen", "qsr"],
    "HR Tech": ["hr tech", "human resources", "recruitment", "ats", "hiring", "payroll", "staffing"],
    "Data Analytics": ["data analytics", "bi ", "business intelligence", "dashboard", "data science", "analytics"],
    "Cloud Infra": ["cloud", "infrastructure", "devops", "aws", "azure", "gcp", "hosting"],
    "Legal Tech": ["legal tech", "law", "contract", "compliance", "regtech"],
    "MarTech": ["martech", "marketing", "advertising", "adtech", "customer data platform", "cdp"],
    "DevTools": ["devtools", "developer tools", "api", "sdk", "ci/cd", "github", "gitlab"],
}

OWNER_OVERRIDES: Dict[str, Tuple[str, str]] = {
    "yashika": ("INVESTOR", "Investor - General"),
    "kajal": ("INVESTOR", "Investor - General"),
    "ayush": ("INVESTOR", "Investor - General"),
    "palak": ("CLIENT", "Other"),
    "vismaya": ("CLIENT", "Other"),
}

DEFAULT_TEMPLATES: Dict[str, Dict[int, str]] = {
    "CLIENT": {
        1: "Hi {name},\n\nI hope you're having a good week.\n\nI'm just following up on my previous email regarding the collaboration we discussed. Would love to hear your thoughts on this when you have a moment.",
        2: "Hi {name},\n\nFollowing up on my last note. I'm confident that our platform can add significant value to your current workflow, especially given your focus in the sector.\n\nAre you available for a brief 5-10 minute sync later this week to explore this?",
        3: "Hi {name},\n\nI've reached out a few times regarding our platform but haven't heard back, so I'll assume this isn't a priority for you at the moment.\n\nI'll stop my follow-ups for now, but feel free to reach out if your situation changes or if you have any questions in the future.",
    },
    "INVESTOR_GENERIC": {
        1: "Dear {name},\n\nI hope you're doing well. Following up on the investment opportunity teaser I shared earlier.\n\nPlease let me know if you have reviewed it or require any additional information for evaluation.",
        2: "Hi {name},\n\nFollowing up on my previous note. We are seeing strong interest and strategic progress across our core milestones.\n\nWould you be open to a brief 5-10 minute sync this week to share a quick update and discuss further?",
        3: "Hi {name},\n\nI understand you are busy, so I'm reaching out one last time. If this isn't a fit for you right now, I'll move this to the back burner.\n\nThank you again for your time and consideration.",
    },
    "INVESTOR_AGRITECH": {
        1: "Hi {name},\n\nI hope you're doing well.\n\nJust following up on the Climate Agritech Platform opportunity shared earlier. Please let me know if you've had a chance to review it or if I can provide any additional information.\n\nLooking forward to hearing from you.",
        2: "Hi {name},\n\nJust checking in regarding the Climate Agritech Platform opportunity I shared earlier. I'd appreciate any initial thoughts or feedback on the opportunity when you have a moment.\n\nThank you for your time.",
        3: "Hi {name},\n\nThis will be my final follow-up regarding the Climate Agritech Platform opportunity. If it's not a fit at the moment, I completely understand. If there is any interest, I'd be happy to share further details or schedule a brief discussion.\n\nThank you again for your consideration.",
    },
    "INVESTOR_YASHIKA_AGRITECH": {
        1: "Hi {name},\n\nI hope you're doing well.\n\nI'm just following up on the Climate Agritech platform opportunity we shared earlier. The company reported ₹5.1 crore revenue in FY26 and has previously raised ₹2.37 crore through government grants and angel investors. Please let me know if you have had a chance to review this or if I can provide any additional information.\n\nLooking forward to hearing from you.",
        2: "Hi {name},\n\nJust checking in regarding the Climate Agritech Platform opportunity I shared earlier. I'd appreciate any initial thoughts or feedback on the opportunity when you have a moment.\n\nThank you for your time.",
        3: "Hi {name},\n\nThis will be my final follow-up regarding the Climate Agritech Platform opportunity. If it's not a fit at the moment, I completely understand. If there is any interest, I'd be happy to share further details or schedule a brief discussion.\n\nThank you again for your consideration.",
    },
    "INVESTOR_AI_HIRING": {
        1: "Dear {name},\n\nI hope you're doing well. Following up on the AI Hiring Infrastructure platform teaser shared earlier. Please let me know if you have reviewed it or require any additional information for evaluation.",
        2: "Hi {name},\n\nFollowing up on my previous note. We are seeing exceptional enterprise traction for our AI Hiring Infrastructure.\n\nGiven your focus in this domain, would you be open to a brief 5-10 minute call to discuss this further?",
        3: "Hi {name},\n\nI understand you are busy, so I'm reaching out one last time. If this isn't a fit for you right now, I'll move this to the back burner.\n\nThank you again for your time and consideration.",
    },
    "INVESTOR_HEALTHTECH": {
        1: "Dear {name},\n\nI hope you're doing well. Following up on the HealthTech opportunity I shared regarding our AI-enabled diagnostics platform.\n\nPlease let me know if you have any questions or require further information.",
        2: "Hi {name},\n\nFollowing up on my previous note. We are seeing strong traction and expanding our lab network significantly.\n\nGiven your focus in the healthcare space, I'd value the opportunity to get your feedback on our current trajectory. Are you available for a brief sync?",
        3: "Hi {name},\n\nI'm reaching out one last time to see if you'd like to discuss the opportunity. I understand you're busy, so I'll move this to the back burner if I don't hear from you.\n\nThanks again for your time and consideration.",
    },
    "INVESTOR_DEFENCE": {
        1: "Dear {name},\n\nI hope you're doing well. Following up on the Defence Deeptech & AI Systems opportunity (iDEX Prime Winner) I shared earlier.\n\nPlease let me know if you have reviewed it or require any additional information for evaluation.",
        2: "Hi {name},\n\nFollowing up on my previous note. We are seeing exceptional traction and interest from key strategic partners in the deeptech and national security ecosystem.\n\nGiven your focus in this domain, would you be open to a brief 5-10 minute call to discuss this further?",
        3: "Hi {name},\n\nI understand you are busy, so I'm reaching out one last time. If this isn't a fit for you right now, I'll move this to the back burner.\n\nThank you again for your time and consideration.",
    },
    "INVESTOR_PALAK_ADVISORY": {
        1: "Dear {name},\n\nI hope you are well.\n\nJust following up on my previous email. We would value the opportunity to connect and understand your growth roadmap and any potential capital/funding priorities that may be ahead.\n\nWould you be open to a short video call? Happy to coordinate as per your availability.\n\nLooking forward to hearing from you.",
        2: "Dear {name},\n\nJust following up on my earlier note.\n\nGiven your growth journey, we thought it may be worthwhile to connect and exchange perspectives around future expansion and funding opportunities.\n\nPlease let us know a suitable time for a brief discussion if this would be of interest.\n\nLooking forward to connecting.",
        3: "Dear {name},\n\nI understand you are busy, so I'm reaching out one last time. If this isn't a fit for you right now, I'll move this to the back burner.\n\nThank you again for your time and consideration.",
    },
    "INVESTOR_KAJAL_HEALTH_ECOSYSTEM": {
        1: """Dear {name},

I hope you're doing well.

I wanted to follow up on our earlier note regarding the **Seed Round opportunity in a preventive health ecosystem platform** building India's diagnostics infrastructure layer.

Since our last outreach, the company has continued to demonstrate strong momentum:

- **7,000+ diagnostic orders completed**
- **300+ labs onboarded** across Delhi NCR
- **₹89L+ revenue generated to date**
- **₹2.58 Cr annualized revenue run rate**

The platform is positioned at the intersection of **diagnostics, AI-driven insights, and continuous preventive health monitoring**, addressing a large and underserved market opportunity.

The company is currently raising a **$1M Seed Round** to scale technology, expand the diagnostics network, and strengthen institutional partnerships.

Happy to share the detailed pitch deck and additional information.

Looking forward to your thoughts.""",
        2: """Dear {name},

I wanted to share updates on the **Seed Round opportunity in a preventive health ecosystem platform** building India's diagnostics infrastructure layer.

Since our last outreach, the company has continued to demonstrate strong momentum:

- **7,000+ diagnostic orders completed**
- **300+ labs onboarded** across Delhi NCR
- **₹89L+ revenue generated to date**
- **₹2.58 Cr annualized revenue run rate**

The platform is positioned at the intersection of **diagnostics, AI-driven insights, and continuous preventive health monitoring**, addressing a large and underserved market opportunity.

The company is currently raising a **$1M Seed Round** to scale technology, expand the diagnostics network, and strengthen institutional partnerships.

Happy to share the detailed pitch deck and additional information.

Looking forward to your thoughts.""",
        3: """Dear {name},

I hope this finds you well.

I'm reaching out one final time regarding the **Seed Round for our AI-enabled preventive health ecosystem platform** — with 300+ labs, 7,000+ orders, and ₹2.58 Cr ARR, the company has shown strong early traction.

If the timing isn't right or this doesn't align with your current focus, I completely understand — I'll step back from my follow-ups.

However, if circumstances change or you'd like to revisit this opportunity, please don't hesitate to reach out. We'd be happy to share the full deck or connect at your convenience.

Thank you sincerely for your time and consideration.""",
    },
    "INVESTOR_KAJAL_GENERIC": {
        1: "Dear {name},\n\nI am following up on my previous email regarding the investment opportunity. Please let me know if you are open to a brief introductory call or if I should send the pitch deck for your review.\n\nAdditionally, Would you like to share your investment thesis so that I can share relevant deals in the future?\n\nLooking forward to connecting.",
        2: "Hi {name},\n\nJust checking in regarding the opportunity I shared earlier. I'd appreciate any initial thoughts or feedback on the opportunity when you have a moment.\n\nThank you for your time.",
        3: "Hi {name},\n\nThis will be my final follow-up regarding the opportunity I shared earlier. If it's not a fit at the moment, I completely understand. If there is any interest, I'd be happy to share further details or schedule a brief discussion.\n\nThank you again for your consideration.",
    },
    "INVESTOR_KAJAL_JV": {
        1: "Just following up on my earlier note.\n\nWe would be keen to explore how QVSCL can support your portfolio companies through capital raising, strategic advisory, M&A, and growth initiatives.\n\nIf relevant, we'd also be happy to share curated deal flow aligned with your investment thesis and stage focus.\n\nWould you be available for a brief 15-minute call sometime next week?\n\nLooking forward to your thoughts.\n\nBest regards,",
        2: "Hi {name},\n\nJust checking in regarding the opportunity I shared earlier. I'd appreciate any initial thoughts or feedback on the opportunity when you have a moment.\n\nThank you for your time.",
        3: "Hi {name},\n\nThis will be my final follow-up regarding the opportunity I shared earlier. If it's not a fit at the moment, I completely understand. If there is any interest, I'd be happy to share further details or schedule a brief discussion.\n\nThank you again for your consideration.",
    },
}

DECLINE_PATTERNS: List[Tuple[str, str]] = [
    (r"\bwe\s+will\s+pass\s+on\s+this\s+opportunity\b", "We will pass on this opportunity"),
    (r"\bpass\s+on\s+this\s+opportunity\b", "Pass on this opportunity"),
    (r"\bwe\s+only\s+invest\s+in\b", "We only invest in"),
    (r"\bwe\s+only\s+do\b", "We only do"),
    (r"\bwe\s+will\s+pass\b(?!\s+(?:this|it|that|along)\s+(?:along|on|to|over)\b)", "We will pass"),
    (r"\bwe(?:'|'')\s*ll\s+pass\b(?!\s+(?:this|it|that|along)\s+(?:along|on|to|over)\b)", "We'll pass"),
    (r"\bnot\s+a\s+current\s+fit\b", "Not a current fit"),
    (r"\bnot\s+fit\s+for\s+us\b", "Not fit for us"),
    (r"\bno\s*,?\s*thank\s*(?:you|s)?\b", "No thank you"),
    (r"\bplease\s+share\s+a\s+detailed\s+deck\b", "Please share a detailed deck"),
    (r"\bpass\s+from\s+us\b", "Pass from us"),
    (r"\bpass\s+for\s+now\b", "Pass for now"),
    (r"\bnot\s+within\s+our\s+mandate\b", "Not within our mandate"),
    (r"\btoo\s+early\s+for\s+us\b", "Too early for us"),
    (r"\bnot\s+interested\b", "Not interested"),
    (r"\bwe\s+do\s+not\s+invest\b", "We do not invest"),
    (r"\bdecline\s+the\s+opportunity\b", "Decline the opportunity"),
    (r"\bnot\s+a\s+good\s+fit\b", "Not a good fit"),
]

CAMPAIGN_RULES: List[Tuple[str, str]] = [
    ("INVESTOR_PALAK_ADVISORY", "corporate advisory"),
    ("INVESTOR_KAJAL_HEALTH_ECOSYSTEM", "kajal_mam_health_ecosystem"),
    ("INVESTOR_KAJAL_JV", "kajal_mam_jv"),
    ("INVESTOR_KAJAL_JV", "kajal_mam_qvscl_intro"),
    ("INVESTOR_AI_HIRING", "hiring"),
    ("INVESTOR_HEALTHTECH", "health"),
    ("INVESTOR_HEALTHTECH", "diagnostic"),
    ("INVESTOR_DEFENCE", "defence"),
    ("INVESTOR_DEFENCE", "deeptech"),
    ("INVESTOR_DEFENCE", "idex"),
    ("INVESTOR_AGRITECH", "agritech"),
    ("INVESTOR_AGRITECH", "climate"),
    ("INVESTOR_KAJAL_GENERIC", "kajal_mam_hyphen"),
    ("INVESTOR_KAJAL_GENERIC", "kajal_mam_agritech"),
]

LOGO_FORCED_STYLES: Dict[str, str] = {
    "upload_1786095549294_2711.webp": "width:100px;height:100px;object-fit:contain;display:block;",
}

USER_EMAIL_FONTS: Dict[int, str] = {
    2: "Arial, sans-serif",
    3: "sans-serif",
    4: "sans-serif",
    5: "sans-serif",
}

USER_EMAIL_FONT_SIZES: Dict[int, str] = {
    2: "18px",
    3: "14px",
    4: "15px",
    5: "13px",
}

DEFAULT_EMAIL_FONT: str = "sans-serif"
DEFAULT_EMAIL_FONT_SIZE: str = "15px"
SANS_SERIF_FONT: str = "sans-serif"