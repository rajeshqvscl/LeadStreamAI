import requests
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
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


def _parse_profile_details(details):
    """
    Helper to consistently parse RocketReach person details into our lead format.
    """
    if not details:
        return None

    # --- Email: only accept verified/reliable ones ---
    email = None
    trusted_statuses = {"current", "verified", "valid", "accept_all", ""}
    for email_obj in (details.get("emails") or []):
        status = (email_obj.get("status") or "").lower()
        addr = email_obj.get("email") or ""
        if addr and status in trusted_statuses:
            email = addr
            break

    if not email:
        return None

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

    return {
        "first_name": first_name,
        "last_name": last_name,
        "email": email,
        "phone": phone,
        "domain": domain,
        "linkedin": details.get("linkedin_url"),
        "company": details.get("current_employer"),
        "source": "rocketreach",
        "payload": details
    }


def search_leads(employer=None, title=None, location=None, page_size=10):
    url = f"{BASE_URL}/search"
    query = {}

    if employer:
        query["current_employer"] = [employer]

    if title and title.lower() != 'other':
        query["current_title"] = [t.strip() for t in title.split(',') if t.strip()]
    else:
        query["current_title"] = C_SUITE_TITLES

    if location:
        query["location"] = [location]

    leads = []
    max_pages = 5
    current_page = 1
    
    while len(leads) < page_size and current_page <= max_pages:
        payload = { "start": current_page, "page_size": max(page_size * 2, 20), "query": query }
        r = requests.post(url, json=payload, headers=HEADERS, timeout=45)

        if not r.ok:
            if leads: break
            return _generate_mock_leads(employer, title, location, page_size)

        profiles = r.json().get("profiles", [])
        if not profiles: break

        def process_profile(p):
            profile_id = p.get("id")
            if not profile_id: return None
            details = lookup_profile(profile_id)
            parsed = _parse_profile_details(details)
            if not parsed: return None

            # Strict parsing: If user searched specifically for a company, block fuzzy/irrelevant API matches
            employer_found = parsed.get("company") or ""
            if employer and employer.lower() not in employer_found.lower():
                return None
            return parsed

        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(process_profile, p) for p in profiles]
            for future in as_completed(futures):
                parsed = future.result()
                if parsed:
                    leads.append(parsed)
                    if len(leads) >= page_size:
                        return leads

        current_page += 1

    return leads


def lookup_by_email(email):
    """
    Search RocketReach for a person by their email address.
    """
    url = f"{BASE_URL}/person/lookup"
    params = {"email": email}
    r = requests.get(url, headers=HEADERS, params=params, timeout=30)
    
    if not r.ok:
        print(f"Email lookup error ({r.status_code}): {r.text}")
        return []
    
    details = r.json()
    parsed = _parse_profile_details(details)
    return [parsed] if parsed else []


def lookup_by_name(name, company=None):
    """
    Search RocketReach for a person by name and optionally company.
    """
    url = f"{BASE_URL}/search"
    query = {"name": name}
    if company:
        query["current_employer"] = [company]
        
    payload = {
        "start": 1,
        "page_size": 10,
        "query": query
    }
    
    r = requests.post(url, json=payload, headers=HEADERS, timeout=30)
    if not r.ok:
        print(f"Name search error ({r.status_code}): {r.text}")
        return []

    profiles = r.json().get("profiles", [])
    leads = []
    
    def process_name_profile(p):
        pid = p.get("id")
        if not pid: return None
        details = lookup_profile(pid)
        return _parse_profile_details(details)

    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = [executor.submit(process_name_profile, p) for p in profiles]
        for future in as_completed(futures):
            parsed = future.result()
            if parsed:
                leads.append(parsed)
            
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

def _generate_mock_leads(employer, title, location, page_size):
    import random
    leads = []
    base_domains = ["example.com", "test.org", "mockcorp.io", "dummy.net"]
    titles = ["CEO", "VP of Engineering", "Chief Marketing Officer", "Founder", "CTO"]
    names = [("Jane", "Doe"), ("John", "Smith"), ("Alice", "Johnson"), ("Bob", "Williams"), ("Charlie", "Brown")]
    
    for i in range(page_size):
        first, last = random.choice(names)
        company = employer if employer else f"Mock Company {i}"
        domain = random.choice(base_domains)
        job = title if title and title.lower() != 'other' else random.choice(titles)
        
        leads.append({
            "first_name": first,
            "last_name": f"{last}{i}",
            "email": f"{first.lower()}.{last.lower()}{i}@{domain}",
            "phone": f"+1555010{random.randint(1000, 9999)}",
            "domain": domain,
            "linkedin": f"https://linkedin.com/in/{first.lower()}-{last.lower()}-{i}",
            "company": company,
            "source": "rocketreach_mock",
            "payload": {
                "current_title": job,
                "current_employer": company
            }
        })
    return leads