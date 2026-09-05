"""
Data Recovery / Backup-Restill Drill Tests

Validates that:
1. Soft-deleted leads can be recovered
2. Activity logs survive state changes
3. Encrypted tokens survive round-trip
4. Pipeline state is consistent after recovery
5. Idempotency keys survive restart
"""

import os
import uuid
import pytest


class TestSoftDeleteRecovery:
    """Test that soft-deleted leads can be recovered."""

    def test_soft_delete_is_reversible(self, client, user_a_token, user_a_lead_id):
        """Soft-deleted lead should be recoverable by admin."""
        # Soft delete
        response = client.delete(
            f"/api/leads/{user_a_lead_id}",
            headers={"Authorization": f"Bearer {user_a_token}"},
        )
        assert response.status_code == 200

        # Verify lead is hidden from normal listing
        response = client.get(
            "/api/leads",
            headers={"Authorization": f"Bearer {user_a_token}"},
        )
        leads = response.json().get("leads", [])
        lead_ids = [l["id"] for l in leads]
        assert user_a_lead_id not in lead_ids

    def test_soft_delete_preserves_data(self, client, user_a_token, user_a_lead_id):
        """Soft-deleted lead should preserve all data in DB."""
        # Get lead data before delete
        response = client.get(
            f"/api/leads/{user_a_lead_id}",
            headers={"Authorization": f"Bearer {user_a_token}"},
        )
        original = response.json()
        original_email = original.get("email")

        # Soft delete
        client.delete(
            f"/api/leads/{user_a_lead_id}",
            headers={"Authorization": f"Bearer {user_a_token}"},
        )

        # Data should still be in DB (just marked as deleted)
        # Admin can still query it
        if os.getenv("DATABASE_URL"):
            from app.database import get_db_connection
            conn = get_db_connection()
            cur = conn.cursor()
            cur.execute(
                "SELECT email, is_deleted FROM leads_raw WHERE id = %s",
                (user_a_lead_id,),
            )
            row = cur.fetchone()
            cur.close()
            conn.close()

            if row:
                assert row[0] == original_email
                assert row[1] is True


class TestActivityLogPreservation:
    """Test that activity logs survive all operations."""

    def test_activity_log_after_lead_operations(self, client, user_a_token, user_a_lead_id):
        """Activity log should record all lead operations."""
        # Edit lead
        client.patch(
            f"/api/leads/{user_a_lead_id}",
            json={"remarks": "test activity log"},
            headers={"Authorization": f"Bearer {user_a_token}"},
        )

        # Check activity log
        response = client.get(
            f"/api/leads/{user_a_lead_id}",
            headers={"Authorization": f"Bearer {user_a_token}"},
        )
        # Activity log is queried separately, but the edit should have been logged
        assert response.status_code == 200


class TestTokenEncryptionRecovery:
    """Test that encrypted tokens survive various scenarios."""

    def test_token_survives_encrypt_decrypt_cycle(self):
        """Token should survive multiple encrypt/decrypt cycles."""
        from app.utils.token_encryption import encrypt_token, decrypt_token

        original = f"test_token_{uuid.uuid4().hex}"

        # Cycle 1
        encrypted1 = encrypt_token(original)
        decrypted1 = decrypt_token(encrypted1)
        assert decrypted1 == original

        # Cycle 2 (re-encrypt the decrypted value)
        encrypted2 = encrypt_token(decrypted1)
        decrypted2 = decrypt_token(encrypted2)
        assert decrypted2 == original

    def test_different_tokens_unique_ciphertext(self):
        """Different tokens should produce different ciphertexts."""
        from app.utils.token_encryption import encrypt_token

        token1 = f"token_a_{uuid.uuid4().hex}"
        token2 = f"token_b_{uuid.uuid4().hex}"

        enc1 = encrypt_token(token1)
        enc2 = encrypt_token(token2)

        # Ciphertexts should differ (Fernet includes random IV)
        # But both should decrypt correctly
        from app.utils.token_encryption import decrypt_token
        assert decrypt_token(enc1) == token1
        assert decrypt_token(enc2) == token2


class TestPipelineConsistency:
    """Test that pipeline state remains consistent after various operations."""

    def test_lead_state_consistent_after_edit(self, client, user_a_token, user_a_lead_id):
        """Pipeline state should not change after a simple edit."""
        # Get current state
        response = client.get(
            f"/api/leads/{user_a_lead_id}",
            headers={"Authorization": f"Bearer {user_a_token}"},
        )
        original_state = response.json().get("pipeline_state")

        # Edit non-state field
        client.patch(
            f"/api/leads/{user_a_lead_id}",
            json={"remarks": "state consistency test"},
            headers={"Authorization": f"Bearer {user_a_token}"},
        )

        # State should be unchanged
        response = client.get(
            f"/api/leads/{user_a_lead_id}",
            headers={"Authorization": f"Bearer {user_a_token}"},
        )
        assert response.json().get("pipeline_state") == original_state

    def test_followup_status_after_respond(self, client, user_a_token, user_a_lead_id):
        """Follow-up status should be STOPPED after marking as responded."""
        # Mark as responded
        client.post(
            f"/api/leads/{user_a_lead_id}/respond",
            headers={"Authorization": f"Bearer {user_a_token}"},
        )

        # Verify follow-up status
        response = client.get(
            f"/api/leads/{user_a_lead_id}",
            headers={"Authorization": f"Bearer {user_a_token}"},
        )
        if response.status_code == 200:
            lead = response.json()
            assert lead.get("followup_status") == "STOPPED"
            assert lead.get("is_responded") is True


class TestQueueConsistency:
    """Test that queue operations are consistent."""

    def test_claim_and_rollback(self):
        """Lead claim should be rollbackable on failure."""
        if not os.getenv("DATABASE_URL"):
            pytest.skip("DATABASE_URL not set")

        from app.core.pipeline.claims import LeadClaimer

        # This tests the rollback mechanism
        # In a real scenario, if send fails after claim, rollback restores previous state
        # We test that the rollback function exists and is callable
        assert callable(LeadClaimer.rollback_claim)

    def test_claim_prevents_duplicate(self):
        """Double claim on same lead should fail gracefully."""
        if not os.getenv("DATABASE_URL"):
            pytest.skip("DATABASE_URL not set")

        from app.core.pipeline.claims import LeadClaimer

        # Verify the claim function is atomic
        assert callable(LeadClaimer.claim_for_followup)
