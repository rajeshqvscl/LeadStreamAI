"""
Shared fixtures for the real-DB integration suite under tests/integration/.

tests/integration/*.py exercise the REAL API against a live PostgreSQL
(CI service container / staging DB) exactly like the security suites in
tests/unit/, and therefore need the same seeded users/sessions/leads.

The fixtures themselves live in tests/unit/conftest.py. Re-exporting the
decorated fixture objects here registers them for this directory too
(pytest picks up any module attribute carrying the fixture marker), so the
integration tests resolve user_a_token, user_a_lead_id, etc. with identical
skip-without-DB semantics. Without this, every integration test that seeds
data fails with "fixture 'user_a_token' not found".
"""

from tests.unit.conftest import (
    active_lead_id,
    admin_id,
    admin_token,
    security_seed,
    sent_lead_id,
    unsubscribed_lead_id,
    user_a_campaign_id,
    user_a_id,
    user_a_lead_id,
    user_a_token,
    user_b_campaign_id,
    user_b_id,
    user_b_lead_id,
    user_b_token,
)

__all__ = [
    "active_lead_id",
    "admin_id",
    "admin_token",
    "security_seed",
    "sent_lead_id",
    "unsubscribed_lead_id",
    "user_a_campaign_id",
    "user_a_id",
    "user_a_lead_id",
    "user_a_token",
    "user_b_campaign_id",
    "user_b_id",
    "user_b_lead_id",
    "user_b_token",
]
