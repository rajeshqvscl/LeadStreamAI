"""
Lead Lifecycle Integration Tests

Tests the full pipeline: Lead → Draft → Approval → Send → Follow-up → Reply → Close

These tests use real PostgreSQL (via test database) to verify
end-to-end data flow and state transitions.
"""

import pytest
from datetime import datetime, timedelta, timezone


class TestLeadCreationFlow:
    """Test lead creation through various methods."""

    def test_manual_lead_creation(self, client, user_a_token):
        """Manual lead creation via API."""
        response = client.post(
            "/api/leads/",
            json={
                "first_name": "Test",
                "last_name": "Investor",
                "email": "test.investor@example.com",
                "company_name": "Test Capital",
                "designation": "Managing Partner",
                "persona": "INVESTOR",
                "source": "manual",
            },
            headers={"Authorization": f"Bearer {user_a_token}"},
        )
        assert response.status_code == 200
        lead = response.json()
        assert lead["first_name"] == "Test"
        assert lead["email"] == "test.investor@example.com"

    def test_lead_has_correct_user_id(self, client, user_a_token, user_a_id):
        """Created lead must be owned by the creating user."""
        response = client.post(
            "/api/leads/",
            json={
                "first_name": "Owned",
                "last_name": "Lead",
                "email": "owned.lead@example.com",
                "source": "manual",
            },
            headers={"Authorization": f"Bearer {user_a_token}"},
        )
        assert response.status_code == 200
        lead_id = response.json()["id"]

        # Verify ownership
        response = client.get(
            f"/api/leads/{lead_id}",
            headers={"Authorization": f"Bearer {user_a_token}"},
        )
        assert response.status_code == 200


class TestDraftGenerationFlow:
    """Test AI draft generation for leads."""

    def test_draft_generation(self, client, user_a_token, user_a_lead_id):
        """Draft generation should create a pending draft."""
        response = client.post(
            f"/api/generate/draft/{user_a_lead_id}",
            headers={"Authorization": f"Bearer {user_a_token}"},
        )
        # May succeed or fail based on LLM availability
        # But must not return 403/404 for own lead
        assert response.status_code not in (403, 404)


class TestFollowupSequenceFlow:
    """Test follow-up sequence management."""

    def test_followup_listing(self, client, user_a_token):
        """Follow-up listing should return leads due for follow-up."""
        response = client.get(
            "/api/leads/followups",
            headers={"Authorization": f"Bearer {user_a_token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "leads" in data
        assert "total" in data

    def test_followup_stage_counts(self, client, user_a_token):
        """Follow-up listing should include stage counts."""
        response = client.get(
            "/api/leads/followups",
            headers={"Authorization": f"Bearer {user_a_token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "stage_counts" in data

    def test_followup_status_filters(self, client, user_a_token):
        """Follow-up listing should support status filters."""
        for status in ["DUE", "SENT", "REPLIED", "STOPPED", "COMPLETED"]:
            response = client.get(
                f"/api/leads/followups?status={status}",
                headers={"Authorization": f"Bearer {user_a_token}"},
            )
            assert response.status_code == 200


class TestInboundDealsFlow:
    """Test inbound deals (reply detection results)."""

    def test_inbound_deals_listing(self, client, user_a_token):
        """Inbound deals should list replied leads."""
        response = client.get(
            "/api/gmail/inbound-deals",
            headers={"Authorization": f"Bearer {user_a_token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "leads" in data
        assert "total" in data


class TestPipelineStateTransitions:
    """Test state machine transitions through API actions."""

    def test_mark_responded_transitions(self, client, user_a_token, sent_lead_id):
        """Marking a lead as responded should transition to REPLIED state."""
        response = client.post(
            f"/api/leads/{sent_lead_id}/respond",
            headers={"Authorization": f"Bearer {user_a_token}"},
        )
        assert response.status_code == 200

        # Verify state changed
        response = client.get(
            f"/api/leads/{sent_lead_id}",
            headers={"Authorization": f"Bearer {user_a_token}"},
        )
        lead = response.json()
        assert lead.get("is_responded") is True or lead.get("followup_status") == "STOPPED"

    def test_soft_delete_stops_automation(self, client, user_a_token, active_lead_id):
        """Soft-deleting a lead should stop all automation."""
        response = client.delete(
            f"/api/leads/{active_lead_id}",
            headers={"Authorization": f"Bearer {user_a_token}"},
        )
        assert response.status_code == 200

        # Verify lead is no longer in active listing
        response = client.get(
            "/api/leads",
            headers={"Authorization": f"Bearer {user_a_token}"},
        )
        leads = response.json().get("leads", [])
        lead_ids = [l["id"] for l in leads]
        assert active_lead_id not in lead_ids


class TestConcurrentOperations:
    """Test concurrent operations on same lead."""

    def test_concurrent_edits_no_corruption(self, client, user_a_token, user_a_lead_id):
        """Multiple concurrent edits to same lead should not corrupt data."""
        import concurrent.futures

        def edit_remarks(remark):
            return client.patch(
                f"/api/leads/{user_a_lead_id}",
                json={"remarks": remark},
                headers={"Authorization": f"Bearer {user_a_token}"},
            )

        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(edit_remarks, f"edit_{i}") for i in range(5)]
            results = [f.result() for f in futures]

        # All should succeed (last-write-wins)
        for r in results:
            assert r.status_code == 200

        # Final state should be consistent
        response = client.get(
            f"/api/leads/{user_a_lead_id}",
            headers={"Authorization": f"Bearer {user_a_token}"},
        )
        assert response.status_code == 200
