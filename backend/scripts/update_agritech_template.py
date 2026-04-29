import psycopg2
import os
from dotenv import load_dotenv
load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

name = "yashika_draft_agritech"
description = "Climate Agritech Platform fundraising draft (USD 500K-1M)"
content = """Dear {{First Name}},

I hope you're doing well.

I'm {{Sender First Name}} from QVSCL (Gurugram), a strategic advisory firm working with high-growth early-stage ventures. We are currently raising a round for a climate-focused agritech platform that is building a full-stack renewable energy marketplace for rural India.

Business Overview
Sector: Agritech / Climate / Social Impact
Stage: Revenue-generating, growth-stage
Positioning: India’s first curated marketplace for renewable & green energy products for farmers and rural households
Platform Offering:
Multi-brand marketplace with 60+ brands and 200+ SKUs across solar, biogas, and green energy solutions
End-to-end solutions spanning product discovery, advisory, deployment, and after-sales service
AI-enabled touchpoints including chatbots and localized support
Business Model:
Phygital distribution model combining AI-enabled digital platform + village-level offline stores
Asset-light approach with franchise-led last-mile distribution
Multiple revenue streams across B2C sales, B2B projects, partnerships, franchise fees, and AMC services

Problems
Rural India faces structural inefficiencies in energy access and agri productivity:
High dependence on firewood, diesel, and unreliable electricity
Limited access to modern technologies and advisory support
Fragmented distribution through traditional dealer networks limits penetration

Solutions
A one-stop, full-stack renewable energy platform addressing access, affordability, and adoption:
Phygital Marketplace: Seamless online + offline distribution network
AI-led Advisory: Personalized product recommendations and assisted buying
Last-mile Reach: Deep rural penetration via trained partners and franchise stores
Integrated Offering: Solar, biogas, thermal, and green energy products under one platform
Value-Added Services: Financing support, insurance, and long-term after-sales service

Traction & Impact
Revenue: INR 5.1 Cr achieved till Feb’26 with ~105% YoY growth
Advance Orders: INR 2 Cr pipeline
On-ground Impact (FY20-25):
1,24,153+ lives impacted; 1,10,000+ women impacted
2,070+ tons of CO₂ emissions abated
66,000+ green jobs created; 900+ acres irrigated via solar
Large-scale deployment of renewable energy products across rural India

Differentiation
First-mover advantage in building a renewable energy marketplace with advisory layer
Strong last-mile rural distribution network vs. e-commerce-led competitors
Integrated stack combining commerce, financing, service, and impact delivery

Fundraise
Raising: USD 500K - 1M
Use of Funds: Expansion, product development (AgriVoltaics), team scale-up, and market expansion

If this aligns with your portfolio focus and does not conflict with it, I’d be happy to share the full presentation or connect over a virtual meeting at your convenience. I have attached the QVSCL Profile. You may also share your investment thesis with us so we can send relevant deal flow in the future.
For more details about our services: Website | Linkedin

Looking forward to your response.

SIG_START
--
Thanks & Regards,
{{Sender Name}},
{{Sender Title}},
SIG_LINK_LABEL:LinkedIn:{{Sender LinkedIn}}
{{Sender Phone}}
Important: This message and its attachments are intended only for the addressee and may contain legally privileged and/or confidential information. If you are not the intended recipient, you are hereby notified that you must not use, disseminate, or copy this material in any form, or take any action based upon it. If you have received this message by error, please immediately delete it and its attachments and notify the sender at QV Strategic Consulting LLP by electronic mail message reply. Thank you.
SIG_END"""

def update_template():
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()
    
    print(f"Updating template {name} with dynamic placeholders...")
    cur.execute("UPDATE prompts SET content = %s, description = %s WHERE name = %s;", (content, description, name))
        
    conn.commit()
    cur.close()
    conn.close()
    print("Done.")

if __name__ == "__main__":
    update_template()
