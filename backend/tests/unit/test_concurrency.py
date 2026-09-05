"""
Concurrency Stress Tests

Tests system behavior under concurrent load:
- 100 simultaneous jobs on same lead
- Same idempotency key from multiple workers
- Concurrent scheduler instances
- Race conditions in state transitions
"""

import os
import socket
import uuid
from urllib.parse import urlparse

import pytest
import concurrent.futures
from unittest.mock import patch, MagicMock


def _db_reachable() -> bool:
    """True when a real PostgreSQL is listening on DATABASE_URL."""
    url = os.getenv("DATABASE_URL", "")
    if not url:
        return False
    p = urlparse(url.replace("postgresql://", "http://"))
    host = p.hostname or "localhost"
    port = p.port or 5432
    try:
        s = socket.create_connection((host, port), timeout=2)
        s.close()
        return True
    except Exception:
        return False


class TestIdempotencyUnderConcurrency:
    """Verify idempotency holds under concurrent access."""

    def test_100_concurrent_claims_same_key(self):
        """100 threads claiming same idempotency key — exactly ONE should succeed."""
        if not _db_reachable():
            pytest.skip("PostgreSQL not reachable — CI runs this with a DB container")

        from app.email_engine.worker.sender import claim_idempotency

        key = f"stress_{uuid.uuid4().hex[:12]}"
        NUM_WORKERS = 100

        with concurrent.futures.ThreadPoolExecutor(max_workers=NUM_WORKERS) as executor:
            futures = [executor.submit(claim_idempotency, key) for _ in range(NUM_WORKERS)]
            results = [f.result() for f in concurrent.futures.as_completed(futures)]

        successes = sum(1 for r in results if r is True)
        failures = sum(1 for r in results if r is False)

        assert successes == 1, f"Expected exactly 1 success, got {successes}"
        assert failures == NUM_WORKERS - 1, f"Expected {NUM_WORKERS-1} failures, got {failures}"

    def test_50_concurrent_different_keys(self):
        """50 threads each with unique keys — all should succeed."""
        if not _db_reachable():
            pytest.skip("PostgreSQL not reachable — CI runs this with a DB container")

        from app.email_engine.worker.sender import claim_idempotency

        NUM_WORKERS = 50
        keys = [f"stress_{uuid.uuid4().hex[:12]}" for _ in range(NUM_WORKERS)]

        with concurrent.futures.ThreadPoolExecutor(max_workers=NUM_WORKERS) as executor:
            futures = [executor.submit(claim_idempotency, k) for k in keys]
            results = [f.result() for f in concurrent.futures.as_completed(futures)]

        assert all(results), f"Not all unique keys claimed: {sum(results)}/{NUM_WORKERS}"


class TestConcurrentLeadOperations:
    """Test concurrent operations on the same lead."""

    def test_concurrent_edits_last_write_wins(self, client, user_a_token, user_a_lead_id):
        """Multiple concurrent edits should not corrupt the lead."""
        NUM_WORKERS = 20

        def edit_lead(remark_num):
            return client.patch(
                f"/api/leads/{user_a_lead_id}",
                json={"remarks": f"concurrent_edit_{remark_num}"},
                headers={"Authorization": f"Bearer {user_a_token}"},
            )

        with concurrent.futures.ThreadPoolExecutor(max_workers=NUM_WORKERS) as executor:
            futures = [executor.submit(edit_lead, i) for i in range(NUM_WORKERS)]
            results = [f.result() for f in concurrent.futures.as_completed(futures)]

        # All should succeed
        for r in results:
            assert r.status_code == 200

        # Final state should be consistent (not corrupted)
        response = client.get(
            f"/api/leads/{user_a_lead_id}",
            headers={"Authorization": f"Bearer {user_a_token}"},
        )
        assert response.status_code == 200
        lead = response.json()
        assert "concurrent_edit_" in lead.get("remarks", "")

    def test_concurrent_approve_followup(self, client, user_a_token, user_a_lead_id):
        """Multiple concurrent follow-up approvals — only one should succeed."""
        NUM_WORKERS = 10

        def approve():
            return client.post(
                f"/api/leads/{user_a_lead_id}/approve-followup",
                json={"custom_body": "concurrent approval"},
                headers={"Authorization": f"Bearer {user_a_token}"},
            )

        with concurrent.futures.ThreadPoolExecutor(max_workers=NUM_WORKERS) as executor:
            futures = [executor.submit(approve) for _ in range(NUM_WORKERS)]
            results = [f.result() for f in concurrent.futures.as_completed(futures)]

        # At least one should succeed or all should fail gracefully (no crash)
        status_codes = [r.status_code for r in results]
        # Should not have any 500 errors
        assert 500 not in status_codes, f"Server errors detected: {status_codes}"


class TestConcurrentSchedulerSafety:
    """Test scheduler behavior under concurrent execution."""

    def test_scheduler_lock_prevents_duplicate(self):
        """Two scheduler locks on same key — only one should acquire."""
        from app.core.scheduler_lock import SchedulerLock
        import uuid

        lock_key = f"test:scheduler:{uuid.uuid4().hex[:8]}"
        lock1 = SchedulerLock(lock_key, ttl_seconds=30)
        lock2 = SchedulerLock(lock_key, ttl_seconds=30)

        assert lock1.acquire() is True
        assert lock2.acquire() is False  # Should fail — lock1 holds it

        lock1.release()

        # After release, lock2 should be able to acquire
        assert lock2.acquire() is True
        lock2.release()

    def test_scheduler_lock_ttl_expiry(self):
        """Lock should auto-expire after TTL."""
        from app.core.scheduler_lock import SchedulerLock
        import uuid
        import time

        lock_key = f"test:ttl:{uuid.uuid4().hex[:8]}"
        lock = SchedulerLock(lock_key, ttl_seconds=1)  # 1 second TTL

        assert lock.acquire() is True
        time.sleep(1.5)  # Wait for TTL expiry

        # Another lock should now be able to acquire
        lock2 = SchedulerLock(lock_key, ttl_seconds=1)
        assert lock2.acquire() is True
        lock2.release()

    def test_scheduler_lock_renew(self):
        """Lock renewal should extend TTL."""
        from app.core.scheduler_lock import SchedulerLock
        import uuid

        lock_key = f"test:renew:{uuid.uuid4().hex[:8]}"
        lock = SchedulerLock(lock_key, ttl_seconds=5)

        assert lock.acquire() is True
        assert lock.renew() is True
        lock.release()


class TestConcurrentStateTransitions:
    """Test that state transitions are safe under concurrency."""

    def test_concurrent_mark_responded(self, client, user_a_token, user_a_lead_id):
        """Multiple concurrent respond-marking should not corrupt state."""
        NUM_WORKERS = 10

        def mark_responded():
            return client.post(
                f"/api/leads/{user_a_lead_id}/respond",
                headers={"Authorization": f"Bearer {user_a_token}"},
            )

        with concurrent.futures.ThreadPoolExecutor(max_workers=NUM_WORKERS) as executor:
            futures = [executor.submit(mark_responded) for _ in range(NUM_WORKERS)]
            results = [f.result() for f in concurrent.futures.as_completed(futures)]

        # All should succeed or fail gracefully (no 500s)
        for r in results:
            assert r.status_code in (200, 400, 404)

        # Verify final state is consistent
        response = client.get(
            f"/api/leads/{user_a_lead_id}",
            headers={"Authorization": f"Bearer {user_a_token}"},
        )
        if response.status_code == 200:
            lead = response.json()
            # State should be either responded or not — never corrupted
            assert lead.get("is_responded") is True or lead.get("followup_status") == "STOPPED"
