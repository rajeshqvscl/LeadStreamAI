"""
Unit tests for cancel_pending_jobs_for_leads() in app/email_engine/queue/registry.py

Uses fake RQ queues — no real Redis required. Verifies that queued/scheduled
jobs whose ids embed a target lead (followup_lead<id>_..., email_lead<id>_...)
are removed, while jobs for other leads are left untouched.
"""

import pytest

import app.email_engine.queue.registry as registry
from app.email_engine.queue.job import EmailPriority


class _FakeRegistry:
    """Fake scheduled-job registry."""

    def __init__(self, job_ids):
        self._ids = list(job_ids)

    def get_job_ids(self):
        return list(self._ids)


class _FakeQueue:
    """Minimal fake rq.Queue exposing just the methods the purge uses."""

    def __init__(self, name, queued=None, scheduled=None):
        self.name = name
        self.queued = list(queued or [])
        self.scheduled = _FakeRegistry(scheduled or [])
        self.cancelled = []

    def get_job_ids(self):
        return list(self.queued)

    def remove(self, job_id):
        if job_id in self.queued:
            self.queued.remove(job_id)

    @property
    def scheduled_job_registry(self):
        return self.scheduled

    def fetch_job(self, job_id):
        if job_id in self.scheduled._ids:
            return _FakeJob(job_id, self)
        return None


class _FakeJob:
    def __init__(self, job_id, queue):
        self.id = job_id
        self._queue = queue

    def cancel(self):
        self._queue.scheduled._ids.remove(self.id)
        self._queue.cancelled.append(self.id)


@pytest.fixture
def fake_queues(monkeypatch):
    """Replace the queue constructors with fakes we can inspect."""
    queues = {
        "emails_high": _FakeQueue("emails_high"),
        "emails_normal": _FakeQueue("emails_normal"),
        "emails_low": _FakeQueue("emails_low"),
        "emails_scheduled": _FakeQueue("emails_scheduled"),
    }

    def _priority_queue(priority):
        name = {
            EmailPriority.HIGH: "emails_high",
            EmailPriority.NORMAL: "emails_normal",
            EmailPriority.LOW: "emails_low",
        }.get(priority, "emails_normal")
        return queues[name]

    monkeypatch.setattr(registry, "get_priority_queue", _priority_queue)
    monkeypatch.setattr(registry, "get_scheduled_queue", lambda: queues["emails_scheduled"])
    return queues


def _enqueue(queues, priority, job_id):
    name = {
        EmailPriority.HIGH: "emails_high",
        EmailPriority.NORMAL: "emails_normal",
        EmailPriority.LOW: "emails_low",
    }[priority]
    queues[name].queued.append(job_id)


class TestCancelPendingJobsForLeads:
    def test_removes_followup_job_for_target_lead(self, fake_queues):
        queues = fake_queues
        _enqueue(queues, EmailPriority.NORMAL, "followup_lead123_stage1")
        _enqueue(queues, EmailPriority.NORMAL, "followup_lead456_stage1")

        removed = registry.cancel_pending_jobs_for_leads([123])

        assert removed == 1
        assert queues["emails_normal"].queued == ["followup_lead456_stage1"]

    def test_removes_email_job_for_target_lead(self, fake_queues):
        queues = fake_queues
        _enqueue(queues, EmailPriority.HIGH, "email_lead123_some_template_a1b2c3d4")
        _enqueue(queues, EmailPriority.HIGH, "email_lead789_other_x1y2z3")

        removed = registry.cancel_pending_jobs_for_leads([123])

        assert removed == 1
        assert queues["emails_high"].queued == ["email_lead789_other_x1y2z3"]

    def test_multiple_priority_queues_scanned(self, fake_queues):
        queues = fake_queues
        _enqueue(queues, EmailPriority.HIGH, "followup_lead7_stage1")
        _enqueue(queues, EmailPriority.NORMAL, "followup_lead7_stage2")
        _enqueue(queues, EmailPriority.LOW, "followup_lead7_stage3")

        removed = registry.cancel_pending_jobs_for_leads([7])

        assert removed == 3
        for name in ("emails_high", "emails_normal", "emails_low"):
            assert queues[name].queued == []

    def test_no_false_positive_on_longer_lead_id(self, fake_queues):
        # lead 1 pattern must not match lead 12 / lead 123's job ids
        queues = fake_queues
        _enqueue(queues, EmailPriority.NORMAL, "followup_lead12_stage1")
        _enqueue(queues, EmailPriority.NORMAL, "followup_lead123_stage2")

        removed = registry.cancel_pending_jobs_for_leads([1])

        assert removed == 0
        assert queues["emails_normal"].queued == [
            "followup_lead12_stage1",
            "followup_lead123_stage2",
        ]

    def test_cancels_delayed_scheduled_jobs(self, fake_queues):
        queues = fake_queues
        queues["emails_scheduled"].scheduled._ids.append("followup_lead999_stage1")
        queues["emails_scheduled"].scheduled._ids.append("followup_lead888_stage1")

        removed = registry.cancel_pending_jobs_for_leads([999])

        assert removed == 1
        assert queues["emails_scheduled"].scheduled._ids == ["followup_lead888_stage1"]
        assert queues["emails_scheduled"].cancelled == ["followup_lead999_stage1"]

    def test_empty_input_is_noop(self, fake_queues):
        queues = fake_queues
        _enqueue(queues, EmailPriority.NORMAL, "followup_lead1_stage1")

        assert registry.cancel_pending_jobs_for_leads([]) == 0
        assert registry.cancel_pending_jobs_for_leads(None) == 0
        assert queues["emails_normal"].queued == ["followup_lead1_stage1"]

    def test_unknown_lead_leaves_queue_untouched(self, fake_queues):
        queues = fake_queues
        _enqueue(queues, EmailPriority.NORMAL, "followup_lead123_stage1")

        assert registry.cancel_pending_jobs_for_leads([9999]) == 0
        assert queues["emails_normal"].queued == ["followup_lead123_stage1"]


# Run with: pytest tests/unit/test_queue_purge.py -v
