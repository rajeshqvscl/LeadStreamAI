import psycopg2
import os
from dotenv import load_dotenv
load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

PALAK_CONTENT = """Subject: Strategic M&A and India Entry Advisory | QVSCL × {{Company Name}}

Dear {{First Name}},

I hope you're having a productive week.

I'm {{Sender Name}} from QVSCL. We’ve been closely following your firm's expansion in the region, and I wanted to reach out regarding our specialized **M&A and India Entry advisory services**.

If you are currently:
* **Looking to Acquire a company in India** to expand capabilities or enter new markets
* **Exploring a Strategic Merger or Joint Venture** in India
* **Evaluating Growth through inorganic routes**

—We can support you end-to-end, including:
* Identifying and evaluating relevant targets/opportunities
* Valuation and deal structuring
* Managing diligence and negotiations
* Ensuring smooth transaction closure and integration

**We bring a hands-on, confidential approach backed by strong market access across sectors.** 

If this is relevant, I'm happy to schedule a quick discussion and share live opportunities currently in the market. I am sharing our Company Profile attached to this email for your reference.

Looking forward to connecting.

SIG_START
--
**Thanks & Regards,**
*{{Sender Name}},*
**{{Sender Title}},**
[LinkedIn]({{Sender LinkedIn}})
**{{Sender Phone}}**
SIG_END
"""

def update_templates():
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()
    # Ensure the name matches what's in the DB. Earlier I saw 'palak_mam_Draft_1'
    cur.execute(
        "UPDATE prompts SET content = %s WHERE name = 'palak_mam_Draft_1'",
        (PALAK_CONTENT,)
    )
    conn.commit()
    print("Palak's Template updated with matching subject and better formatting.")
    cur.close()
    conn.close()

if __name__ == "__main__":
    update_templates()
