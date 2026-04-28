import requests
import os
from dotenv import load_dotenv

load_dotenv()

key = "1c888d2k03d45e1abaf81b3b592708a7febca3fe"
headers = {"Api-Key": key}

endpoints = [
    "https://api.rocketreach.co/api/v2/account/lookup",
    "https://api.rocketreach.co/api/v2/account/status",
    "https://api.rocketreach.co/api/v2/account",
    "https://api.rocketreach.co/api/v2/lookup/credits",
    "https://api.rocketreach.co/api/v2/search/company", # headers often have credits
]

for url in endpoints:
    try:
        print(f"Testing {url}...")
        resp = requests.get(url, headers=headers, timeout=10)
        print(f"Status: {resp.status_code}")
        if resp.ok:
            print(f"Body: {resp.text[:500]}")
            print(f"Headers: {resp.headers}")
        else:
            print(f"Error: {resp.text[:200]}")
    except Exception as e:
        print(f"Failed: {e}")
    print("-" * 20)
