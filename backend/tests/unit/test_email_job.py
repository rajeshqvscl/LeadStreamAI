"""
Unit tests for EmailJob dataclass and serialization.
Pure logic — no DB, no network.
"""

import json
from datetime import datetime, timezone

import pytest

from app.email_engine.queue.job import EmailJob, EmailPriority


class TestEmailPriority:
    """EmailPriority enum values."""

    def test_high_is_one(self):
        assert EmailPriority.HIGH == 1

    def test_normal_is_five(self):
        assert EmailPriority.NORMAL == 5

    def test_low_is_ten(self):
        assert EmailPriority.LOW == 10

    def test_high_less_than_normal(self):
        assert EmailPriority.HIGH < EmailPriority.NORMAL

    def test_normal_less_than_low(self):
        assert EmailPriority.NORMAL < EmailPriority.LOW


class TestEmailJobCreation:
    """EmailJob with required and optional fields."""

    def test_required_fields(self):
        job = EmailJob(
            to_email="test@example.com",
            subject="Hello",
            html_content="<p>Hello</p>",
            user_id=1,
        )
        assert job.to_email == "test@example.com"
        assert job.subject == "Hello"
        assert job.user_id == 1
        assert job.priority == EmailPriority.NORMAL
        assert job.retry_count == 0
        assert job.max_retries == 3
        assert job.attachments == []
        assert job.tracking_enabled is True

    def test_optional_fields_default_none(self):
        job = EmailJob(
            to_email="test@example.com",
            subject="Hello",
            html_content="<p>Hello</p>",
            user_id=1,
        )
        assert job.from_email is None
        assert job.from_name is None
        assert job.cc is None
        assert job.bcc is None
        assert job.lead_id is None
        assert job.thread_id is None
        assert job.in_reply_to is None
        assert job.template_name is None
        assert job.idempotency_key is None
        assert job.scheduled_at is None
        assert job.queued_at is None
        assert job.started_at is None
        assert job.completed_at is None
        assert job.last_error is None


class TestToDict:
    """to_dict serialization."""

    def test_all_fields_present(self):
        job = EmailJob(
            to_email="test@example.com",
            subject="Test",
            html_content="<p>Hi</p>",
            user_id=1,
        )
        data = job.to_dict()
        assert "to_email" in data
        assert "subject" in data
        assert "html_content" in data
        assert "user_id" in data
        assert "priority" in data
        assert "retry_count" in data
        assert "created_at" in data
        assert "attachments" in data

    def test_priority_as_int(self):
        job = EmailJob(
            to_email="test@example.com",
            subject="Test",
            html_content="<p>Hi</p>",
            user_id=1,
            priority=EmailPriority.HIGH,
        )
        data = job.to_dict()
        assert isinstance(data["priority"], int)
        assert data["priority"] == 1

    def test_created_at_as_iso_string(self):
        job = EmailJob(
            to_email="test@example.com",
            subject="Test",
            html_content="<p>Hi</p>",
            user_id=1,
        )
        data = job.to_dict()
        assert isinstance(data["created_at"], str)

    def test_scheduled_at_as_iso_string(self):
        now = datetime.now(timezone.utc)
        job = EmailJob(
            to_email="test@example.com",
            subject="Test",
            html_content="<p>Hi</p>",
            user_id=1,
            scheduled_at=now,
        )
        data = job.to_dict()
        assert isinstance(data["scheduled_at"], str)


class TestFromDict:
    """from_dict deserialization reverses to_dict."""

    def test_roundtrip(self):
        job = EmailJob(
            to_email="test@example.com",
            subject="Hello",
            html_content="<p>Hello</p>",
            user_id=1,
            priority=EmailPriority.HIGH,
        )
        data = job.to_dict()
        restored = EmailJob.from_dict(data)
        assert restored.to_email == job.to_email
        assert restored.subject == job.subject
        assert restored.html_content == job.html_content
        assert restored.user_id == job.user_id
        assert restored.priority == EmailPriority.HIGH

    def test_from_dict_optional_fields_default(self):
        data = {
            "to_email": "test@example.com",
            "subject": "Test",
            "html_content": "<p>Hi</p>",
            "user_id": 1,
        }
        job = EmailJob.from_dict(data)
        assert job.to_email == "test@example.com"
        assert job.from_email is None
        assert job.lead_id is None
        assert job.attachments == []


class TestToFromJson:
    """JSON round-trip serialization."""

    def test_json_roundtrip(self):
        job = EmailJob(
            to_email="test@example.com",
            subject="Hello",
            html_content="<p>Hello</p>",
            user_id=1,
            priority=EmailPriority.LOW,
        )
        json_str = job.to_json()
        assert isinstance(json_str, str)
        restored = EmailJob.from_json(json_str)
        assert restored.to_email == job.to_email
        assert restored.subject == job.subject
        assert restored.priority == EmailPriority.LOW

    def test_json_is_valid_json(self):
        job = EmailJob(
            to_email="test@example.com",
            subject="Test",
            html_content="<p>Hi</p>",
            user_id=1,
        )
        json_str = job.to_json()
        parsed = json.loads(json_str)
        assert isinstance(parsed, dict)


class TestWithIdempotencyKey:
    """with_idempotency_key sets key and returns self."""

    def test_sets_key(self):
        job = EmailJob(
            to_email="test@example.com",
            subject="Test",
            html_content="<p>Hi</p>",
            user_id=1,
        )
        result = job.with_idempotency_key("key-123")
        assert job.idempotency_key == "key-123"

    def test_returns_self(self):
        job = EmailJob(
            to_email="test@example.com",
            subject="Test",
            html_content="<p>Hi</p>",
            user_id=1,
        )
        result = job.with_idempotency_key("key-123")
        assert result is job


class TestIncrementRetry:
    """increment_retry increments count and returns self."""

    def test_increments_count(self):
        job = EmailJob(
            to_email="test@example.com",
            subject="Test",
            html_content="<p>Hi</p>",
            user_id=1,
        )
        assert job.retry_count == 0
        job.increment_retry()
        assert job.retry_count == 1
        job.increment_retry()
        assert job.retry_count == 2

    def test_returns_self(self):
        job = EmailJob(
            to_email="test@example.com",
            subject="Test",
            html_content="<p>Hi</p>",
            user_id=1,
        )
        result = job.increment_retry()
        assert result is job
