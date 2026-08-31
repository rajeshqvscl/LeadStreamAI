"""
Unit tests for EmailProducer._generate_idempotency_key()
Pure key generation — no Redis, no queue.
"""

import pytest

from app.email_engine.producer import EmailProducer


def _make_producer():
    """Create EmailProducer without __init__ (bypasses settings)."""
    return object.__new__(EmailProducer)


class TestGenerateIdempotencyKey:
    """Tests for _generate_idempotency_key method."""

    def test_key_starts_with_email(self):
        producer = _make_producer()
        key = producer._generate_idempotency_key()
        assert key.startswith("email_")

    def test_key_with_lead_id(self):
        producer = _make_producer()
        key = producer._generate_idempotency_key(lead_id=123)
        assert "lead123" in key

    def test_key_with_template_name(self):
        producer = _make_producer()
        key = producer._generate_idempotency_key(template_name="my template")
        assert "my_template" in key

    def test_key_with_stage(self):
        producer = _make_producer()
        key = producer._generate_idempotency_key(stage=2)
        assert "stage2" in key

    def test_key_with_all_params(self):
        producer = _make_producer()
        key = producer._generate_idempotency_key(
            lead_id=42, template_name="my template", stage=3
        )
        assert key.startswith("email_")
        assert "lead42" in key
        assert "my_template" in key
        assert "stage3" in key

    def test_key_without_params_has_suffix(self):
        producer = _make_producer()
        key = producer._generate_idempotency_key()
        parts = key.split("_")
        # Last part is uuid hex
        assert len(parts[-1]) == 8

    def test_two_calls_produce_different_keys(self):
        producer = _make_producer()
        key1 = producer._generate_idempotency_key(lead_id=1)
        key2 = producer._generate_idempotency_key(lead_id=1)
        assert key1 != key2

    def test_template_name_spaces_replaced(self):
        producer = _make_producer()
        key = producer._generate_idempotency_key(template_name="series a deck")
        assert "series_a_deck" in key

    def test_no_params_key_format(self):
        producer = _make_producer()
        key = producer._generate_idempotency_key()
        assert key.startswith("email_")
        assert len(key.split("_")) == 2  # "email" + uuid hex


# Run with: pytest tests/unit/test_producer_keys.py -v
