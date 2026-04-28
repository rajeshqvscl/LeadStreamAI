import requests
import os
from dotenv import load_dotenv

load_dotenv()

key = "1c888d2k03d45e1abaf81b3b592708a7febca3fe"
headers = {"Api-Key": key, "Content-Type": "application/json"}

url = "https://api.rocketreach.co/api/v2/person/search"
payload = {"query": {"name": "John Doe"}, "page_size": 1}

try:
    print(f"Testing {url}...")
    resp = requests.post(url, json=payload, headers=headers, timeout=10)
    print(f"Status: {resp.status_code}")
    print(f"Headers: {resp.headers}")
    if resp.ok:
        print(f"Body: {resp.text[:500]}")
    else:
        print(f"Error: {resp.text[:200]}")
except Exception as e:
    print(f"Failed: {e}")
