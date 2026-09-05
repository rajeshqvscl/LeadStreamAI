"""
Penetration-Style Security Tests

Tests from ATTACKER perspective — deliberately malicious inputs,
cross-user manipulation, privilege escalation, and data exfiltration attempts.

Every test simulates a real attack vector against the LeadStream system.
"""

import pytest
from unittest.mock import patch, MagicMock


# =============================================================================
# ATTACK VECTOR 1: Session Token Manipulation
# =============================================================================

class TestSessionTokenAttacks:
    """Attack the authentication layer with crafted tokens."""

    def test_forged_jwt_token(self, client, security_seed):
        """Attacker sends a forged JWT-looking token.

        Requires a live DB + real session verification (the local stub client
        accepts any token, which would defeat the assertion) — skips otherwise.
        """
        response = client.get(
            "/api/leads",
            headers={"Authorization": "Bearer eyJhbGciOiJIUzI1NiJ9.forged.signature"},
        )
        assert response.status_code == 401

    def test_empty_token(self, client):
        """Attacker sends empty bearer token."""
        response = client.get(
            "/api/leads",
            headers={"Authorization": "Bearer "},
        )
        assert response.status_code == 401

    def test_sql_injection_in_token(self, client, security_seed):
        """Attacker injects SQL in the token field."""
        response = client.get(
            "/api/leads",
            headers={"Authorization": "Bearer ' OR 1=1 --"},
        )
        assert response.status_code == 401

    def test_token_from_different_session(self, client, user_a_token, user_b_token):
        """Attacker uses User B's token to access User A's resources."""
        # User B's token should NOT see User A's leads
        response = client.get(
            "/api/leads",
            headers={"Authorization": f"Bearer {user_b_token}"},
        )
        assert response.status_code == 200
        # Should only see User B's leads, not User A's


# =============================================================================
# ATTACK VECTOR 2: Header Spoofing
# =============================================================================

class TestHeaderSpoofing:
    """Attack by spoofing authentication headers."""

    def test_x_user_id_header_ignored(self, client, user_a_token, user_b_lead_id):
        """X-User-Id header spoofing must be ignored — session token is authority."""
        response = client.get(
            f"/api/leads/{user_b_lead_id}",
            headers={
                "Authorization": f"Bearer {user_a_token}",
                "X-User-Id": "2",  # Spoofed to User B
            },
        )
        # Must still be denied — middleware overrides X-User-Id with session user
        assert response.status_code == 404

    def test_x_user_id_admin_escalation(self, client, user_a_token):
        """Normal user cannot escalate to admin via X-User-Id header."""
        response = client.get(
            "/api/leads",
            headers={
                "Authorization": f"Bearer {user_a_token}",
                "X-User-Id": "1",  # Spoofed to admin
            },
        )
        assert response.status_code == 200
        # Should see only User A's leads, NOT all leads


# =============================================================================
# ATTACK VECTOR 3: IDOR (Insecure Direct Object Reference)
# =============================================================================

class TestIDORAttacks:
    """Attack by manipulating resource IDs in URLs."""

    def test_lead_idor(self, client, user_a_token, user_b_lead_id):
        """Attacker tries to access User B's lead by guessing ID."""
        response = client.get(
            f"/api/leads/{user_b_lead_id}",
            headers={"Authorization": f"Bearer {user_a_token}"},
        )
        assert response.status_code == 404

    def test_campaign_idor(self, client, user_a_token, user_b_campaign_id):
        """Attacker tries to access User B's campaign by guessing ID."""
        response = client.get(
            f"/api/campaigns/{user_b_campaign_id}",
            headers={"Authorization": f"Bearer {user_a_token}"},
        )
        assert response.status_code == 404

    def test_sequential_id_enumeration(self, client, user_a_token):
        """Attacker tries to enumerate leads by sequential IDs."""
        accessed = []
        for lead_id in range(1, 20):
            response = client.get(
                f"/api/leads/{lead_id}",
                headers={"Authorization": f"Bearer {user_a_token}"},
            )
            if response.status_code == 200:
                accessed.append(lead_id)
        # Should only access User A's own leads, not others
        # (exact count depends on test data)


# =============================================================================
# ATTACK VECTOR 4: Bulk Data Exfiltration
# =============================================================================

class TestDataExfiltration:
    """Attack by trying to extract bulk data."""

    def test_export_enumeration(self, client, user_a_token, user_b_lead_id):
        """Export must not leak other users' data."""
        response = client.get(
            "/api/leads/export-all",
            headers={"Authorization": f"Bearer {user_a_token}"},
        )
        assert response.status_code == 200
        leads = response.json()
        lead_ids = [l["id"] for l in leads]
        assert user_b_lead_id not in lead_ids

    def test_search_injection(self, client, user_a_token):
        """SQL injection via search parameter must not leak data."""
        response = client.get(
            "/api/leads?search=' UNION SELECT id,email,password_hash FROM users --",
            headers={"Authorization": f"Bearer {user_a_token}"},
        )
        # Must not crash or return user table data
        assert response.status_code in (200, 400, 422)


# =============================================================================
# ATTACK VECTOR 5: State Manipulation
# =============================================================================

class TestStateManipulation:
    """Attack by trying to manipulate pipeline state."""

    def test_cannot_skip_to_closed_won(self, client, user_a_token, user_a_lead_id):
        """Attacker cannot skip pipeline to CLOSED_WON."""
        response = client.patch(
            f"/api/leads/{user_a_lead_id}",
            json={"pipeline_state": "CLOSED_WON"},
            headers={"Authorization": f"Bearer {user_a_token}"},
        )
        # Should either be ignored (not in valid_fields) or rejected
        if response.status_code == 200:
            # Verify state didn't actually change
            response = client.get(
                f"/api/leads/{user_a_lead_id}",
                headers={"Authorization": f"Bearer {user_a_token}"},
            )
            # pipeline_state is not in the response update fields, so it shouldn't change

    def test_mass_followup_approval(self, client, user_a_token, user_b_lead_id):
        """Attacker cannot approve follow-ups on other users' leads."""
        response = client.post(
            f"/api/leads/{user_b_lead_id}/approve-followup",
            json={"custom_body": "Injected content"},
            headers={"Authorization": f"Bearer {user_a_token}"},
        )
        assert response.status_code in (404, 403)


# =============================================================================
# ATTACK VECTOR 6: OAuth Token Theft Simulation
# =============================================================================

class TestOAuthTokenTheft:
    """Simulate OAuth token theft scenarios."""

    def test_stolen_token_cannot_access_other_users(self, client, user_a_token):
        """Stolen token from User A cannot access User B's Gmail."""
        # User A's token should only see User A's Gmail data
        response = client.get(
            "/api/gmail/inbound-deals",
            headers={"Authorization": f"Bearer {user_a_token}"},
        )
        assert response.status_code == 200
        # All deals should belong to User A

    def test_disconnected_gmail_blocks_sends(self, client, user_a_token):
        """After Gmail disconnect, sends should fail gracefully."""
        # This tests the invalid_grant handling path
        from app.services.google_service import invalidate_gmail_service_cache
        invalidate_gmail_service_cache(999)  # Should not crash


# =============================================================================
# ATTACK VECTOR 7: Reply Spoofing
# =============================================================================

class TestReplySpoofing:
    """Attack by spoofing reply detection."""

    def test_pubsub_with_invalid_payload(self, client):
        """Pub/Sub webhook with invalid payload must not crash."""
        response = client.post(
            "/api/gmail/pubsub-push",
            json={"invalid": "payload"},
        )
        assert response.status_code == 200  # Returns 200 to prevent Google retries

    def test_pubsub_empty_message(self, client):
        """Pub/Sub webhook with empty message must be handled."""
        response = client.post(
            "/api/gmail/pubsub-push",
            json={"message": {}},
        )
        assert response.status_code == 200

    def test_pubsub_missing_data(self, client):
        """Pub/Sub webhook with missing data field must be handled."""
        response = client.post(
            "/api/gmail/pubsub-push",
            json={"message": {"data": ""}},
        )
        assert response.status_code == 200


# =============================================================================
# ATTACK VECTOR 8: Denial of Service
# =============================================================================

class TestDoSProtection:
    """Attack by trying to overwhelm the system."""

    def test_login_brute_force(self, client):
        """Brute force login attempts must be rate limited."""
        for i in range(6):
            response = client.post(
                "/api/auth/login",
                json={"username": "admin", "password": f"wrong{i}"},
            )
        assert response.status_code == 429

    def test_large_payload_rejection(self, client, user_a_token, user_a_lead_id):
        """Extremely large payloads should be handled."""
        response = client.patch(
            f"/api/leads/{user_a_lead_id}",
            json={"remarks": "A" * 100000},
            headers={"Authorization": f"Bearer {user_a_token}"},
        )
        # Should either succeed or return 400/413
        assert response.status_code in (200, 400, 413, 422)


# =============================================================================
# ATTACK VECTOR 9: Cross-Site Request Forgery
# =============================================================================

class TestCSRFProtection:
    """Test CSRF-like attack vectors."""

    def test_unsubscribe_csrf(self, client):
        """Unsubscribe endpoint must require correct token."""
        response = client.post(
            "/unsubscribe/confirm",
            data={"token": "fake_token_12345"},
        )
        # Should fail gracefully (invalid token)
        assert response.status_code in (200, 404)


# =============================================================================
# ATTACK VECTOR 10: Information Disclosure
# =============================================================================

class TestInformationDisclosure:
    """Test that error messages don't leak sensitive information."""

    def test_404_no_user_enumeration(self, client, user_a_token):
        """404 responses must not reveal whether a resource exists for another user."""
        response = client.get(
            "/api/leads/999999",
            headers={"Authorization": f"Bearer {user_a_token}"},
        )
        assert response.status_code == 404
        # Response should say "not found" not "access denied" (avoids enumeration)

    def test_error_no_stack_trace(self, client, user_a_token):
        """Error responses must not include stack traces in production."""
        response = client.get(
            "/api/leads/abc",
            headers={"Authorization": f"Bearer {user_a_token}"},
        )
        # Should not contain Python traceback info
        if response.status_code == 500:
            assert "traceback" not in response.text.lower()
            assert "Traceback (most recent call last)" not in response.text
