import os
import sys
from pathlib import Path

# Add backend to path
sys.path.append(str(Path(__file__).resolve().parent.parent))

# Mock Environment
os.environ["GOOGLE_CLIENT_ID"] = "test-id"
os.environ["GOOGLE_CLIENT_SECRET"] = "test-secret"
os.environ["GOOGLE_REDIRECT_URI"] = "https://production.com/callback"

from app.services.google_service import get_google_flow

class MockRequest:
    def __init__(self, base_url):
        self.base_url = base_url

def test_dynamic_flow():
    # Simulate a local request
    mock_request = MockRequest("http://localhost:8000")
    
    base_url = str(mock_request.base_url).rstrip("/")
    redirect_uri = f"{base_url}/api/auth/google/callback"
    
    print(f"Testing with dynamic redirect_uri: {redirect_uri}")
    
    flow = get_google_flow(redirect_uri=redirect_uri)
    
    # Check if the flow's internal config uses the dynamic URI
    # The flow object from google-auth-oauthlib store it in redirect_uri
    assert flow.redirect_uri == "http://localhost:8000/api/auth/google/callback"
    print("SUCCESS: Flow picked up the dynamic local redirect URI.")

    # Simulate a production request
    prod_request = MockRequest("https://lead-backend-ipls.onrender.com")
    base_url_prod = str(prod_request.base_url).rstrip("/")
    redirect_uri_prod = f"{base_url_prod}/api/auth/google/callback"
    
    print(f"Testing with dynamic production redirect_uri: {redirect_uri_prod}")
    flow_prod = get_google_flow(redirect_uri=redirect_uri_prod)
    assert flow_prod.redirect_uri == "https://lead-backend-ipls.onrender.com/api/auth/google/callback"
    print("SUCCESS: Flow picked up the dynamic production redirect URI.")

if __name__ == "__main__":
    try:
        test_dynamic_flow()
    except Exception as e:
        print(f"FAILED: {e}")
        sys.exit(1)
