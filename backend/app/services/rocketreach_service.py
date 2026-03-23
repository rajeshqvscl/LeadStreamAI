import requests
import os
from dotenv import load_dotenv
from pathlib import Path

env_path = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(dotenv_path=env_path, override=True)
ROCKETREACH_API_KEY = os.getenv("ROCKETREACH_API_KEY")

BASE_URL = "https://api.rocketreach.co/api/v2"

HEADERS = {
    "Api-Key": ROCKETREACH_API_KEY,
    "Content-Type": "application/json"
}

# C-suite titles we always want to target — these are passed to RocketReach
C_SUITE_TITLES = [
    "CEO", "Chief Executive Officer",
    "Founder", "Co-Founder", "Co Founder",
    "MD", "Managing Director",
    "VP", "Vice President",
    "CTO", "Chief Technology Officer",
    "CFO", "Chief Financial Officer",
    "COO", "Chief Operating Officer",
    "President",
    "Partner",
    "General Partner",
    "Managing Partner",
]


def search_leads(employer=None, title=None, location=None, page_size=10):
    """
    Search RocketReach for leads.
    - If a specific title is given, use it (unless it's 'other', then ignore it).
    - Otherwise, default to searching across ALL C-suite titles.
    - Uses paging to try and fulfill the requested page_size of verified leads.
    """

    url = f"{BASE_URL}/search"
    query = {}

    if employer:
        query["current_employer"] = [employer]

    # Handle 'other' or empty titles for broader search coverage
    if title and title.lower() != 'other':
        # User specified a real title — use it exactly
        query["current_title"] = [title]
    else:
        # No title or 'other' specified — search all C-suite titles
        query["current_title"] = C_SUITE_TITLES

    if location:
        query["location"] = [location]

    leads = []
    max_pages = 5
    current_page = 1
    
    while len(leads) < page_size and current_page <= max_pages:
        payload = {
            "start": current_page,
            # Fetch a healthy batch to filter through
            "page_size": max(page_size * 2, 20),
            "query": query
        }

        r = requests.post(url, json=payload, headers=HEADERS, timeout=45)

        if not r.ok:
            # If we already have some leads, return them instead of failing completely
            if leads:
                break
            raise Exception(f"RocketReach Search Error (Page {current_page}): {r.text}")

        profiles = r.json().get("profiles", [])
        if not profiles:
            break

        for p in profiles:
            profile_id = p.get("id")
            if not profile_id:
                continue

            details = lookup_profile(profile_id)
            if not details:
                continue

            # --- Email: only accept verified/reliable ones ---
            email = None
            trusted_statuses = {"current", "verified", "valid", "accept_all", ""}
            for email_obj in (details.get("emails") or []):
                status = (email_obj.get("status") or "").lower()
                addr = email_obj.get("email") or ""
                if addr and status in trusted_statuses:
                    email = addr
                    break

            # Skip leads with no usable email
            if not email:
                continue

            # --- Name ---
            full_name = details.get("name") or ""
            parts = full_name.strip().split(" ")
            first_name = parts[0] if parts else ""
            last_name = " ".join(parts[1:]) if len(parts) > 1 else ""

            # --- Domain ---
            domain = email.split("@")[1] if "@" in email else None

            # --- Phone ---
            phone = None
            for p_obj in (details.get("phones") or []):
                if p_obj.get("number"):
                    phone = p_obj["number"]
                    break

            leads.append({
                "first_name": first_name,
                "last_name": last_name,
                "email": email,
                "phone": phone,
                "domain": domain,
                "linkedin": details.get("linkedin_url"),
                "company": details.get("current_employer"),
                "source": "rocketreach",
                "payload": details
            })

            # Stop once fulfill the requested count
            if len(leads) >= page_size:
                return leads

        current_page += 1

    return leads


def lookup_profile(profile_id):

    url = f"{BASE_URL}/person/lookup"

    headers = {
        "Api-Key": ROCKETREACH_API_KEY
    }

    params = {
        "id": profile_id
    }

    r = requests.get(url, headers=headers, params=params, timeout=30)

    if not r.ok:
        print("Lookup error:", r.text)
        return None

    return r.json()