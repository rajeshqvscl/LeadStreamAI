"""
Cross-User Security Test Suite

Tests that User A cannot access, modify, or act on User B's resources.
Every test follows: Correct user + malicious ID = NO DATA + NO SIDE EFFECT.

Severity: P0 — these tests must ALL pass before any production deploy.
"""

import pytest


def _db_available() -> bool:
    """True if the TEST database is reachable (CI service container).

    Delegates to tests.conftest.db_reachable, which checks the sandbox
    ``_TEST_DATABASE_URL`` — never the ambient ``DATABASE_URL`` env var.
    App modules flip that var to the production URL at import time
    (``load_dotenv(override=True)``), so reading it here made local runs
    detect the production Neon DB as "available" and seed it with pytest
    rows.
    """
    from tests.conftest import db_reachable
    return db_reachable()


# DB-aware fixtures: with a live DB (CI) the tests exercise the REAL API with
# seeded users/leads/sessions; without one (local) the client fixture stubs the
# DB with FakeRow (user_id 0) so cross-user requests still fail with 404.
@pytest.fixture(scope="session")
def security_seed():
    """Seed real users/leads/sessions when a DB is up, else None (stub mode)."""
    if not _db_available():
        return None
    from tests.unit.conftest import seed_security_data
    return seed_security_data()


@pytest.fixture
def user_a_token(security_seed):
    """Token for User A. Real session token when a DB is up; otherwise any
    string works because the client fixture bypasses session verification."""
    if security_seed is None:
        return "test-token-user-a"
    return security_seed["token_a"]


@pytest.fixture
def user_b_lead_id(security_seed):
    """A lead ID owned by User B (not session user A). With no live DB the fake
    row has user_id=0, which still fails the ownership check -> 404."""
    if security_seed is None:
        return 99999
    return security_seed["lead_b"]


@pytest.fixture
def user_b_campaign_id(security_seed):
    """A campaign ID owned by User B."""
    if security_seed is None:
        return 99999
    return security_seed["campaign_b"]


class TestLeadOwnershipIsolation:
    """Verify leads are strictly scoped to their owning user."""

    def test_user_a_cannot_read_user_b_lead(self, client, user_a_token, user_b_lead_id):
        """User A reading User B's lead must return 404 (not 403 to avoid enumeration)."""
        response = client.get(
            f"/api/leads/{user_b_lead_id}",
            headers={"Authorization": f"Bearer {user_a_token}"},
        )
        assert response.status_code == 404

    def test_user_a_cannot_edit_user_b_lead(self, client, user_a_token, user_b_lead_id):
        """User A editing User B's lead must be denied."""
        response = client.patch(
            f"/api/leads/{user_b_lead_id}",
            json={"remarks": "hacked"},
            headers={"Authorization": f"Bearer {user_a_token}"},
        )
        assert response.status_code in (404, 403)

    def test_user_a_cannot_delete_user_b_lead(self, client, user_a_token, user_b_lead_id):
        """User A deleting User B's lead must be denied."""
        response = client.delete(
            f"/api/leads/{user_b_lead_id}",
            headers={"Authorization": f"Bearer {user_a_token}"},
        )
        assert response.status_code in (404, 403)

    def test_user_a_cannot_approve_user_b_followup(self, client, user_a_token, user_b_lead_id):
        """User A approving a follow-up on User B's lead must be denied."""
        response = client.post(
            f"/api/leads/{user_b_lead_id}/approve-followup",
            json={"custom_body": "test"},
            headers={"Authorization": f"Bearer {user_a_token}"},
        )
        assert response.status_code in (404, 403)

    def test_user_a_cannot_mark_user_b_lead_responded(self, client, user_a_token, user_b_lead_id):
        """User A marking User B's lead as responded must be denied."""
        response = client.post(
            f"/api/leads/{user_b_lead_id}/respond",
            headers={"Authorization": f"Bearer {user_a_token}"},
        )
        assert response.status_code in (404, 403)

    def test_leads_list_does_not_include_other_users(self, client, user_a_token, user_b_lead_id):
        """User A's lead list must not contain User B's leads."""
        response = client.get(
            "/api/leads",
            headers={"Authorization": f"Bearer {user_a_token}"},
        )
        assert response.status_code == 200
        leads = response.json().get("leads", [])
        lead_ids = [l["id"] for l in leads]
        assert user_b_lead_id not in lead_ids

    def test_export_does_not_include_other_users(self, client, user_a_token, user_b_lead_id):
        """User A's export must not contain User B's leads."""
        response = client.get(
            "/api/leads/export-all",
            headers={"Authorization": f"Bearer {user_a_token}"},
        )
        assert response.status_code == 200
        leads = response.json()
        lead_ids = [l["id"] for l in leads]
        assert user_b_lead_id not in lead_ids


class TestCampaignOwnershipIsolation:
    """Verify campaigns are strictly scoped to their owning user."""

    def test_user_a_cannot_read_user_b_campaign(self, client, user_a_token, user_b_campaign_id):
        """User A reading User B's campaign must return 404."""
        response = client.get(
            f"/api/campaigns/{user_b_campaign_id}",
            headers={"Authorization": f"Bearer {user_a_token}"},
        )
        assert response.status_code == 404

    def test_user_a_cannot_edit_user_b_campaign(self, client, user_a_token, user_b_campaign_id):
        """User A editing User B's campaign must be denied."""
        response = client.put(
            f"/api/campaigns/{user_b_campaign_id}",
            json={"name": "hacked"},
            headers={"Authorization": f"Bearer {user_a_token}"},
        )
        assert response.status_code in (404, 403)

    def test_user_a_cannot_delete_user_b_campaign(self, client, user_a_token, user_b_campaign_id):
        """User A deleting User B's campaign must be denied."""
        response = client.delete(
            f"/api/campaigns/{user_b_campaign_id}",
            headers={"Authorization": f"Bearer {user_a_token}"},
        )
        assert response.status_code in (404, 403)

    def test_campaigns_list_does_not_include_other_users(self, client, user_a_token, user_b_campaign_id):
        """User A's campaign list must not contain User B's campaigns."""
        response = client.get(
            "/api/campaigns",
            headers={"Authorization": f"Bearer {user_a_token}"},
        )
        assert response.status_code == 200
        campaigns = response.json()
        campaign_ids = [c["id"] for c in campaigns]
        assert user_b_campaign_id not in campaign_ids


class TestWorkerOwnershipValidation:
    """Verify email workers validate lead ownership before sending."""

    def test_worker_rejects_job_for_wrong_user(self):
        """Worker must reject a job where lead belongs to a different user."""
        from app.email_engine.worker.sender import _validate_job_ownership
        from app.email_engine.queue.job import EmailJob

        # Create a job that references a lead belonging to user 2
        # but the job claims user_id=1
        job = EmailJob(
            to_email="test@example.com",
            subject="Test",
            html_content="<p>Test</p>",
            user_id=1,  # Job claims user 1
            lead_id=99999,  # Lead belongs to user 2 (or doesn't exist)
        )

        is_valid, error = _validate_job_ownership(job)
        # Should fail because lead doesn't exist or belongs to wrong user.
        # Fail-closed: when ownership can't be verified (lead missing, mismatch,
        # or DB unreachable) the worker must reject the job.
        assert not is_valid
        assert (
            "not found" in error.lower()
            or "mismatch" in error.lower()
            or "validation failed" in error.lower()
        )

    def test_worker_rejects_job_for_deleted_lead(self):
        """Worker must reject a job for a soft-deleted lead."""
        from app.email_engine.worker.sender import _validate_job_ownership
        from app.email_engine.queue.job import EmailJob

        job = EmailJob(
            to_email="test@example.com",
            subject="Test",
            html_content="<p>Test</p>",
            user_id=1,
            lead_id=99999,  # Non-existent lead
        )

        is_valid, error = _validate_job_ownership(job)
        assert not is_valid

    def test_worker_allows_system_email_without_lead(self):
        """System emails (no lead_id) should pass ownership check."""
        from app.email_engine.worker.sender import _validate_job_ownership
        from app.email_engine.queue.job import EmailJob

        job = EmailJob(
            to_email="admin@example.com",
            subject="System Alert",
            html_content="<p>Alert</p>",
            user_id=1,
            lead_id=None,  # No lead — system email
        )

        is_valid, error = _validate_job_ownership(job)
        assert is_valid


class TestIdempotencyRacePrevention:
    """Verify atomic idempotency claims prevent duplicate sends."""

    def test_first_claim_succeeds(self):
        """First worker to claim an idempotency key should succeed."""
        if not _db_available():
            pytest.skip("PostgreSQL not reachable — CI runs this with a DB container")
        from app.email_engine.worker.sender import claim_idempotency
        import uuid

        key = f"test_race_{uuid.uuid4().hex[:8]}"
        assert claim_idempotency(key) is True

    def test_second_claim_fails(self):
        """Second worker claiming the same key should fail."""
        if not _db_available():
            pytest.skip("PostgreSQL not reachable — CI runs this with a DB container")
        from app.email_engine.worker.sender import claim_idempotency
        import uuid

        key = f"test_race_{uuid.uuid4().hex[:8]}"
        assert claim_idempotency(key) is True
        assert claim_idempotency(key) is False

    def test_different_keys_independent(self):
        """Different idempotency keys should be independent."""
        if not _db_available():
            pytest.skip("PostgreSQL not reachable — CI runs this with a DB container")
        from app.email_engine.worker.sender import claim_idempotency
        import uuid

        key1 = f"test_race_{uuid.uuid4().hex[:8]}"
        key2 = f"test_race_{uuid.uuid4().hex[:8]}"
        assert claim_idempotency(key1) is True
        assert claim_idempotency(key2) is True


class TestTokenEncryption:
    """Verify OAuth token encryption at rest."""

    def test_encrypt_decrypt_roundtrip(self):
        """Encrypted token should decrypt to original value."""
        from app.utils.token_encryption import encrypt_token, decrypt_token

        original = "ya29.a0ARrdaM_test_token_1234567890abcdef"
        encrypted = encrypt_token(original)

        assert encrypted != original
        assert encrypted.startswith("enc:v1:")
        assert decrypt_token(encrypted) == original

    def test_already_encrypted_not_double_encrypted(self):
        """Token starting with enc:v1: should not be re-encrypted."""
        from app.utils.token_encryption import encrypt_token, is_encrypted

        token = "enc:v1:sometoken"
        assert is_encrypted(token)
        assert encrypt_token(token) == token

    def test_none_and_empty_passthrough(self):
        """None and empty strings should pass through unchanged."""
        from app.utils.token_encryption import encrypt_token, decrypt_token

        assert encrypt_token(None) is None
        assert encrypt_token("") == ""
        assert decrypt_token(None) is None
        assert decrypt_token("") == ""

    def test_plaintext_token_stored_with_prefix(self):
        """If encryption key not set, plaintext stored with prefix."""
        import os
        from app.utils.token_encryption import encrypt_token, _get_fernet

        # Temporarily remove the key (conftest sets one) so the fallback runs
        had_key = os.environ.pop('TOKEN_ENCRYPTION_KEY', None)
        try:
            _get_fernet.cache_clear()
            token = "test_token"
            result = encrypt_token(token)
            assert result == token  # Falls back to plaintext
        finally:
            if had_key is not None:
                os.environ['TOKEN_ENCRYPTION_KEY'] = had_key
            _get_fernet.cache_clear()
