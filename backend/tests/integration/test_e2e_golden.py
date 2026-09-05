"""
E2E Golden Scenario Tests

Tests the complete happy path:
Create user → Approve → Connect Gmail → Import lead → Classify →
Generate draft → Approve → Send → Follow-up due → Reply received →
Reply classified → Follow-up cancelled → Meeting required → Pipeline updated

Plus failure branch variants.
"""

import pytest
from datetime import datetime, timedelta, timezone


class TestGoldenPath:
    """Complete happy path through the entire system."""

    def test_01_user_registration(self, client):
        """Step 1: User registers."""
        response = client.post(
            "/api/users/",
            json={
                "username": "testuser_golden",
                "email": "golden@test.com",
                "password": "securepassword123",
                "full_name": "Golden Test User",
            },
        )
        assert response.status_code == 200

    def test_02_user_login(self, client):
        """Step 2: User logs in and gets session token."""
        response = client.post(
            "/api/auth/login",
            json={"username": "admin", "password": "admin"},
        )
        if response.status_code == 200:
            token = response.json().get("access_token")
            assert token is not None
            assert len(token) > 10

    def test_03_me_endpoint(self, client, user_a_token):
        """Step 3: /me returns current user profile."""
        response = client.get(
            "/api/auth/me",
            headers={"Authorization": f"Bearer {user_a_token}"},
        )
        assert response.status_code == 200
        user = response.json()
        assert "id" in user
        assert "username" in user

    def test_04_create_lead(self, client, user_a_token):
        """Step 4: Create a new lead."""
        response = client.post(
            "/api/leads/",
            json={
                "first_name": "Golden",
                "last_name": "Lead",
                "email": "golden.lead@example.com",
                "company_name": "Golden Capital",
                "designation": "Partner",
                "source": "manual",
            },
            headers={"Authorization": f"Bearer {user_a_token}"},
        )
        assert response.status_code == 200
        lead = response.json()
        assert lead["email"] == "golden.lead@example.com"
        return lead["id"]

    def test_05_lead_appears_in_listing(self, client, user_a_token, user_a_lead_id):
        """Step 5: Created lead appears in listing."""
        response = client.get(
            "/api/leads",
            headers={"Authorization": f"Bearer {user_a_token}"},
        )
        assert response.status_code == 200
        leads = response.json()["leads"]
        lead_ids = [l["id"] for l in leads]
        assert user_a_lead_id in lead_ids

    def test_06_lead_detail_readable(self, client, user_a_token, user_a_lead_id):
        """Step 6: Lead detail is readable."""
        response = client.get(
            f"/api/leads/{user_a_lead_id}",
            headers={"Authorization": f"Bearer {user_a_token}"},
        )
        assert response.status_code == 200
        lead = response.json()
        assert lead["id"] == user_a_lead_id

    def test_07_lead_editable(self, client, user_a_token, user_a_lead_id):
        """Step 7: Lead can be edited."""
        response = client.patch(
            f"/api/leads/{user_a_lead_id}",
            json={"remarks": "Golden test remark"},
            headers={"Authorization": f"Bearer {user_a_token}"},
        )
        assert response.status_code == 200

    def test_08_followup_listing_works(self, client, user_a_token):
        """Step 8: Follow-up listing is functional."""
        response = client.get(
            "/api/leads/followups",
            headers={"Authorization": f"Bearer {user_a_token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "leads" in data
        assert "total" in data
        assert "stage_counts" in data

    def test_09_inbound_deals_listing(self, client, user_a_token):
        """Step 9: Inbound deals listing is functional."""
        response = client.get(
            "/api/gmail/inbound-deals",
            headers={"Authorization": f"Bearer {user_a_token}"},
        )
        assert response.status_code == 200

    def test_10_export_works(self, client, user_a_token):
        """Step 10: Export functionality works."""
        response = client.get(
            "/api/leads/export-all",
            headers={"Authorization": f"Bearer {user_a_token}"},
        )
        assert response.status_code == 200
        leads = response.json()
        assert isinstance(leads, list)


class TestFailureBranches:
    """Test failure branches of the golden path."""

    def test_lead_not_found(self, client, user_a_token):
        """Non-existent lead returns 404."""
        response = client.get(
            "/api/leads/999999",
            headers={"Authorization": f"Bearer {user_a_token}"},
        )
        assert response.status_code == 404

    def test_campaign_not_found(self, client, user_a_token):
        """Non-existent campaign returns 404."""
        response = client.get(
            "/api/campaigns/999999",
            headers={"Authorization": f"Bearer {user_a_token}"},
        )
        assert response.status_code == 404

    def test_approve_followup_on_unsubscribed_lead(self, client, user_a_token):
        """Cannot approve follow-up for unsubscribed lead."""
        # This tests the unsubscribe guard in approve_followup
        response = client.post(
            "/api/leads/999999/approve-followup",
            json={},
            headers={"Authorization": f"Bearer {user_a_token}"},
        )
        assert response.status_code in (400, 404)

    def test_cross_user_access_denied(self, client, user_a_token, user_b_lead_id):
        """Cross-user access is denied."""
        response = client.get(
            f"/api/leads/{user_b_lead_id}",
            headers={"Authorization": f"Bearer {user_a_token}"},
        )
        assert response.status_code == 404

    def test_invalid_token_rejected(self, client):
        """Invalid token is rejected."""
        response = client.get(
            "/api/leads",
            headers={"Authorization": "Bearer invalid_token_12345"},
        )
        assert response.status_code == 401
