import requests
import os
from dotenv import load_dotenv

load_dotenv()

key = "1c888d2k03d45e1abaf81b3b592708a7febca3fe"
headers = {
    "Api-Key": key,
    "Accept": "application/json",
    "User-Agent": "RocketReach-Python-SDK/1.0.0"
}

url = "https://api.rocketreach.co/api/v2/account"

try:
    print(f"Testing {url} with SDK-like headers...")
    resp = requests.get(url, headers=headers, timeout=10)
    print(f"Status: {resp.status_code}")
    if resp.ok:
        print(f"Body: {resp.json()}")
    else:
        print(f"Error: {resp.text[:500]}")
except Exception as e:
    print(f"Failed: {e}")
