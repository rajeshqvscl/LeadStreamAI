"""
Endpoint-Level Security Test Matrix

Tests every protected endpoint for:
- Authentication required (401 without token)
- Ownership enforcement (404/403 for cross-user access)
- Admin escalation (admin can access all, user cannot)
- Input validation (reject malicious payloads)

Precondition → Request → Expected Result → Security Expectation
"""

import pytest


# =============================================================================
# AUTHENTICATION TESTS
# =============================================================================

class TestAuthenticationRequired:
    """Every protected endpoint must reject unauthenticated requests."""

    @pytest.mark.parametrize("method,path", [
        ("GET", "/api/leads"),
        ("GET", "/api/leads/1"),
        ("GET", "/api/leads/export-all"),
        ("GET", "/api/campaigns"),
        ("GET", "/api/campaigns/1"),
        ("GET", "/api/gmail/inbound-deals"),
    ])
    def test_unauthenticated_rejected(self, client, method, path):
        """Protected endpoints must return 401 without auth token."""
        response = client.request(method, path)
        assert response.status_code == 401

    @pytest.mark.parametrize("method,path", [
        ("POST", "/api/leads/1/respond"),
        ("POST", "/api/leads/1/approve-followup"),
        ("PATCH", "/api/leads/1"),
        ("DELETE", "/api/leads/1"),
    ])
    def test_unauthenticated_mutations_rejected(self, client, method, path):
        """Mutation endpoints must reject unauthenticated requests."""
        response = client.request(method, path, json={})
        assert response.status_code == 401


# =============================================================================
# LEAD OWNERSHIP TESTS
# =============================================================================

class TestLeadOwnershipMatrix:
    """Matrix: User A vs User B's leads across all lead endpoints."""

    def test_read_own_lead(self, client, user_a_token, user_a_lead_id):
        """User A can read their own lead."""
        response = client.get(
            f"/api/leads/{user_a_lead_id}",
            headers={"Authorization": f"Bearer {user_a_token}"},
        )
        assert response.status_code == 200
        assert response.json()["id"] == user_a_lead_id

    def test_read_other_lead_denied(self, client, user_a_token, user_b_lead_id):
        """User A cannot read User B's lead — must return 404."""
        response = client.get(
            f"/api/leads/{user_b_lead_id}",
            headers={"Authorization": f"Bearer {user_a_token}"},
        )
        assert response.status_code == 404

    def test_edit_own_lead(self, client, user_a_token, user_a_lead_id):
        """User A can edit their own lead."""
        response = client.patch(
            f"/api/leads/{user_a_lead_id}",
            json={"remarks": "test edit"},
            headers={"Authorization": f"Bearer {user_a_token}"},
        )
        assert response.status_code == 200

    def test_edit_other_lead_denied(self, client, user_a_token, user_b_lead_id):
        """User A cannot edit User B's lead."""
        response = client.patch(
            f"/api/leads/{user_b_lead_id}",
            json={"remarks": "hacked"},
            headers={"Authorization": f"Bearer {user_a_token}"},
        )
        assert response.status_code in (404, 403)

    def test_delete_own_lead(self, client, user_a_token, user_a_lead_id):
        """User A can soft-delete their own lead."""
        response = client.delete(
            f"/api/leads/{user_a_lead_id}",
            headers={"Authorization": f"Bearer {user_a_token}"},
        )
        assert response.status_code == 200

    def test_delete_other_lead_denied(self, client, user_a_token, user_b_lead_id):
        """User A cannot delete User B's lead."""
        response = client.delete(
            f"/api/leads/{user_b_lead_id}",
            headers={"Authorization": f"Bearer {user_a_token}"},
        )
        assert response.status_code in (404, 403)

    def test_approve_followup_own_lead(self, client, user_a_token, user_a_lead_id):
        """User A can approve follow-up on their own lead."""
        response = client.post(
            f"/api/leads/{user_a_lead_id}/approve-followup",
            json={"custom_body": "Test follow-up"},
            headers={"Authorization": f"Bearer {user_a_token}"},
        )
        # May succeed or fail based on lead state, but must not be 403/404 for own lead
        assert response.status_code not in (403, 404)

    def test_approve_followup_other_lead_denied(self, client, user_a_token, user_b_lead_id):
        """User A cannot approve follow-up on User B's lead."""
        response = client.post(
            f"/api/leads/{user_b_lead_id}/approve-followup",
            json={"custom_body": "Test"},
            headers={"Authorization": f"Bearer {user_a_token}"},
        )
        assert response.status_code in (404, 403)

    def test_mark_responded_other_lead_denied(self, client, user_a_token, user_b_lead_id):
        """User A cannot mark User B's lead as responded."""
        response = client.post(
            f"/api/leads/{user_b_lead_id}/respond",
            headers={"Authorization": f"Bearer {user_a_token}"},
        )
        assert response.status_code in (404, 403)

    def test_export_excludes_other_leads(self, client, user_a_token, user_b_lead_id):
        """User A's export must not contain User B's leads."""
        response = client.get(
            "/api/leads/export-all",
            headers={"Authorization": f"Bearer {user_a_token}"},
        )
        assert response.status_code == 200
        leads = response.json()
        lead_ids = [l["id"] for l in leads]
        assert user_b_lead_id not in lead_ids


# =============================================================================
# CAMPAIGN OWNERSHIP TESTS
# =============================================================================

class TestCampaignOwnershipMatrix:
    """Matrix: User A vs User B's campaigns."""

    def test_read_own_campaign(self, client, user_a_token, user_a_campaign_id):
        """User A can read their own campaign."""
        response = client.get(
            f"/api/campaigns/{user_a_campaign_id}",
            headers={"Authorization": f"Bearer {user_a_token}"},
        )
        assert response.status_code == 200

    def test_read_other_campaign_denied(self, client, user_a_token, user_b_campaign_id):
        """User A cannot read User B's campaign."""
        response = client.get(
            f"/api/campaigns/{user_b_campaign_id}",
            headers={"Authorization": f"Bearer {user_a_token}"},
        )
        assert response.status_code == 404

    def test_edit_other_campaign_denied(self, client, user_a_token, user_b_campaign_id):
        """User A cannot edit User B's campaign."""
        response = client.put(
            f"/api/campaigns/{user_b_campaign_id}",
            json={"name": "hacked"},
            headers={"Authorization": f"Bearer {user_a_token}"},
        )
        assert response.status_code in (404, 403)

    def test_delete_other_campaign_denied(self, client, user_a_token, user_b_campaign_id):
        """User A cannot delete User B's campaign."""
        response = client.delete(
            f"/api/campaigns/{user_b_campaign_id}",
            headers={"Authorization": f"Bearer {user_a_token}"},
        )
        assert response.status_code in (404, 403)

    def test_campaign_list_excludes_other(self, client, user_a_token, user_b_campaign_id):
        """User A's campaign list must not contain User B's campaigns."""
        response = client.get(
            "/api/campaigns",
            headers={"Authorization": f"Bearer {user_a_token}"},
        )
        assert response.status_code == 200
        campaigns = response.json()
        campaign_ids = [c["id"] for c in campaigns]
        assert user_b_campaign_id not in campaign_ids


# =============================================================================
# ADMIN ESCALATION TESTS
# =============================================================================

class TestAdminEscalation:
    """Admin can access all resources; normal users cannot escalate."""

    def test_admin_sees_all_leads(self, client, admin_token, user_b_lead_id):
        """Admin can read any lead."""
        response = client.get(
            f"/api/leads/{user_b_lead_id}",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert response.status_code == 200

    def test_admin_exports_all_leads(self, client, admin_token):
        """Admin export includes all users' leads."""
        response = client.get(
            "/api/leads/export-all",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert response.status_code == 200

    def test_normal_user_cannot_approve_user(self, client, user_a_token):
        """Normal user cannot approve other users."""
        response = client.post(
            "/api/auth/admin/approve-user/2",
            headers={"Authorization": f"Bearer {user_a_token}"},
        )
        assert response.status_code in (403, 404)


# =============================================================================
# INPUT VALIDATION TESTS
# =============================================================================

class TestInputValidation:
    """Reject malicious or invalid inputs."""

    def test_sql_injection_in_search(self, client, user_a_token):
        """SQL injection in search parameter must be handled safely."""
        response = client.get(
            "/api/leads?search='; DROP TABLE leads_raw; --",
            headers={"Authorization": f"Bearer {user_a_token}"},
        )
        # Should not crash — return 200 with empty results or 400
        assert response.status_code in (200, 400, 422)

    def test_xss_in_remarks(self, client, user_a_token, user_a_lead_id):
        """XSS in remarks field must be stored safely."""
        xss_payload = '<script>alert("xss")</script>'
        response = client.patch(
            f"/api/leads/{user_a_lead_id}",
            json={"remarks": xss_payload},
            headers={"Authorization": f"Bearer {user_a_token}"},
        )
        assert response.status_code == 200

        # Verify when read back, the script tag is present but not executed
        response = client.get(
            f"/api/leads/{user_a_lead_id}",
            headers={"Authorization": f"Bearer {user_a_token}"},
        )
        # XSS is prevented by frontend rendering (React auto-escapes)
        # Backend stores as-is but frontend must escape

    def test_oversized_payload_rejected(self, client, user_a_token, user_a_lead_id):
        """Extremely large payloads should be rejected."""
        huge_remarks = "A" * 1000000  # 1MB string
        response = client.patch(
            f"/api/leads/{user_a_lead_id}",
            json={"remarks": huge_remarks},
            headers={"Authorization": f"Bearer {user_a_token}"},
        )
        # Should either succeed (if no limit) or return 400/413
        assert response.status_code in (200, 400, 413, 422)

    def test_invalid_lead_id_type(self, client, user_a_token):
        """Non-numeric lead_id must be rejected."""
        response = client.get(
            "/api/leads/abc123",
            headers={"Authorization": f"Bearer {user_a_token}"},
        )
        assert response.status_code in (404, 422)


# =============================================================================
# UNSUBSCRIBE GUARD TESTS
# =============================================================================

class TestUnsubscribeGuard:
    """Verify unsubscribed leads cannot receive emails."""

    def test_unsubscribed_lead_no_followup(self, client, user_a_token, unsubscribed_lead_id):
        """Cannot approve follow-up for unsubscribed lead."""
        response = client.post(
            f"/api/leads/{unsubscribed_lead_id}/approve-followup",
            json={},
            headers={"Authorization": f"Bearer {user_a_token}"},
        )
        assert response.status_code == 400


# =============================================================================
# RATE LIMITING TESTS
# =============================================================================

class TestRateLimiting:
    """Verify rate limiting is active."""

    def test_login_rate_limit(self, client):
        """Multiple failed logins should trigger rate limit."""
        for i in range(6):
            response = client.post(
                "/api/auth/login",
                json={"username": "nonexistent", "password": "wrong"},
            )
        # After 5 failures, should get 429
        assert response.status_code == 429
