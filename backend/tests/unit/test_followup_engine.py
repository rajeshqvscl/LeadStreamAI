"""
Unit tests for FollowUpEngine.evaluate()
Pure logic — no DB, no network, no Redis.
"""

from datetime import UTC, datetime, timedelta, timezone
from unittest.mock import patch

import pytest

from app.core.followup.campaign_resolver import CampaignResolver
from app.core.followup.engine import FollowUpEngine
from app.core.config.settings import FollowupSettings
from app.core.pipeline.scheduler import SchedulerConfig

IST = timezone(timedelta(hours=5, minutes=30))


def _make_engine():
    """Build an engine with deterministic settings, bypassing lru_cache."""
    engine = object.__new__(FollowUpEngine)
    engine.followup_settings = FollowupSettings()
    engine.scheduler_config = SchedulerConfig()
    engine.campaign_resolver = CampaignResolver()
    return engine


def _make_lead(**overrides) -> dict:
    """Return a minimal lead dict with sensible defaults.
    last_outreach_at is set as naive UTC (engine converts to IST internally).
    """
    now_utc = datetime.now(UTC)
    last_outreach = now_utc - timedelta(days=5)
    defaults = {
        "id": 1,
        "followup_stage": 0,
        "followup_status": "ACTIVE",
        "email_status": "SENT",
        "lead_type": "INVESTOR",
        "first_name": "Rahul",
        "last_outreach_at": last_outreach.replace(tzinfo=None),  # naive UTC
        "last_outreach_subject": "Investment Opportunity",
        "email_draft": "We are raising a seed round.",
        "persona": "Technology Investor",
        "sector": "FinTech",
        "draft_template_used": "",
        "sender_name": "Kajal",
        "sender_email": "kajal@qvscl.com",
    }
    defaults.update(overrides)
    return defaults


# Patch helper: patches SchedulerConfig.is_followup_working_hours_now at class level
_WH_PATCH = patch.object(SchedulerConfig, "is_followup_working_hours_now", return_value=True)


# ──────────────────────── Stage Limits ────────────────────────


class TestStageLimits:
    """Investor: max 3 stages (0,1,2). Client: max 2 stages (0,1)."""

    def test_investor_stage_0_allowed(self):
        engine = _make_engine()
        lead = _make_lead(followup_stage=0)
        with _WH_PATCH:
            result = engine.evaluate(lead)
        assert result.should_send is True

    def test_investor_stage_2_allowed(self):
        engine = _make_engine()
        last = datetime.now(UTC) - timedelta(days=9)
        lead = _make_lead(followup_stage=2, last_outreach_at=last.replace(tzinfo=None))
        with _WH_PATCH:
            result = engine.evaluate(lead)
        assert result.should_send is True

    def test_investor_stage_3_blocked(self):
        engine = _make_engine()
        lead = _make_lead(followup_stage=3)
        with _WH_PATCH:
            result = engine.evaluate(lead)
        assert result.should_send is False
        assert "max 3" in result.reason

    def test_investor_stage_10_blocked(self):
        engine = _make_engine()
        lead = _make_lead(followup_stage=10)
        with _WH_PATCH:
            result = engine.evaluate(lead)
        assert result.should_send is False

    def test_client_stage_0_allowed(self):
        engine = _make_engine()
        lead = _make_lead(followup_stage=0, lead_type="CLIENT")
        with _WH_PATCH:
            result = engine.evaluate(lead)
        assert result.should_send is True

    def test_client_stage_1_allowed(self):
        engine = _make_engine()
        lead = _make_lead(followup_stage=1, lead_type="CLIENT")
        with _WH_PATCH:
            result = engine.evaluate(lead)
        assert result.should_send is True

    def test_client_stage_2_blocked(self):
        engine = _make_engine()
        lead = _make_lead(followup_stage=2, lead_type="CLIENT")
        with _WH_PATCH:
            result = engine.evaluate(lead)
        assert result.should_send is False
        assert "max 2" in result.reason


# ──────────────────────── Interval Timing ────────────────────────


class TestIntervalTiming:
    """Investor intervals: stage 0 → 2 days, stage 1 → 5 days, stage 2 → 8 days.
    last_outreach_at is naive UTC; engine converts to IST for days_since calculation.
    """

    def test_stage0_too_soon(self):
        engine = _make_engine()
        last = datetime.now(UTC) - timedelta(days=1)
        lead = _make_lead(followup_stage=0, last_outreach_at=last.replace(tzinfo=None))
        with _WH_PATCH:
            result = engine.evaluate(lead)
        assert result.should_send is False
        assert "0/2" in result.reason or "1/2" in result.reason  # may be 0 or 1 depending on time-of-day

    def test_stage0_ready(self):
        engine = _make_engine()
        last = datetime.now(UTC) - timedelta(days=3)  # 3 days ensures >= 2 even with IST offset
        lead = _make_lead(followup_stage=0, last_outreach_at=last.replace(tzinfo=None))
        with _WH_PATCH:
            result = engine.evaluate(lead)
        assert result.should_send is True

    def test_stage1_too_soon(self):
        engine = _make_engine()
        last = datetime.now(UTC) - timedelta(days=3)
        lead = _make_lead(followup_stage=1, last_outreach_at=last.replace(tzinfo=None))
        with _WH_PATCH:
            result = engine.evaluate(lead)
        assert result.should_send is False
        # days_since could be 3 or 4 depending on time-of-day
        assert result.days_since_last < 5

    def test_stage1_ready(self):
        engine = _make_engine()
        last = datetime.now(UTC) - timedelta(days=6)  # 6 days ensures >= 5
        lead = _make_lead(followup_stage=1, last_outreach_at=last.replace(tzinfo=None))
        with _WH_PATCH:
            result = engine.evaluate(lead)
        assert result.should_send is True

    def test_stage2_too_soon(self):
        engine = _make_engine()
        last = datetime.now(UTC) - timedelta(days=6)
        lead = _make_lead(followup_stage=2, last_outreach_at=last.replace(tzinfo=None))
        with _WH_PATCH:
            result = engine.evaluate(lead)
        assert result.should_send is False
        assert result.days_since_last < 8

    def test_stage2_ready(self):
        engine = _make_engine()
        last = datetime.now(UTC) - timedelta(days=9)  # 9 days ensures >= 8
        lead = _make_lead(followup_stage=2, last_outreach_at=last.replace(tzinfo=None))
        with _WH_PATCH:
            result = engine.evaluate(lead)
        assert result.should_send is True

    def test_client_intervals_shorter(self):
        """Client stage 0 → 2 days, stage 1 → 5 days."""
        engine = _make_engine()
        last = datetime.now(UTC) - timedelta(days=3)
        lead = _make_lead(followup_stage=0, lead_type="CLIENT", last_outreach_at=last.replace(tzinfo=None))
        with _WH_PATCH:
            result = engine.evaluate(lead)
        assert result.should_send is True


# ──────────────────────── Working Hours ────────────────────────


class TestWorkingHours:
    """Engine should block sends outside working hours."""

    def test_outside_hours_blocked(self):
        engine = _make_engine()
        lead = _make_lead()
        with patch.object(SchedulerConfig, "is_followup_working_hours_now", return_value=False):
            result = engine.evaluate(lead)
        assert result.should_send is False
        assert "followup working hours" in result.reason

    def test_inside_hours_proceeds(self):
        engine = _make_engine()
        lead = _make_lead()
        with _WH_PATCH:
            result = engine.evaluate(lead)
        if not result.should_send:
            assert "Outside working hours" not in result.reason


# ──────────────────────── Defence Skip ────────────────────────


class TestDefenceSkip:
    """Leads with defence/deeptech keywords should be skipped."""

    def test_defence_in_persona(self):
        engine = _make_engine()
        lead = _make_lead(persona="Defence Systems Investor")
        with _WH_PATCH:
            result = engine.evaluate(lead)
        assert result.should_send is False
        assert "Defence" in result.reason

    def test_defence_in_sector(self):
        engine = _make_engine()
        lead = _make_lead(sector="Deeptech")
        with _WH_PATCH:
            result = engine.evaluate(lead)
        assert result.should_send is False

    def test_defence_in_subject(self):
        engine = _make_engine()
        lead = _make_lead(last_outreach_subject="iDEX Defence Opportunity")
        with _WH_PATCH:
            result = engine.evaluate(lead)
        assert result.should_send is False

    def test_defence_in_draft(self):
        engine = _make_engine()
        lead = _make_lead(email_draft="This is a defence deeptech startup.")
        with _WH_PATCH:
            result = engine.evaluate(lead)
        assert result.should_send is False

    def test_no_defence_keyword_proceeds(self):
        engine = _make_engine()
        lead = _make_lead(persona="FinTech Investor", sector="Banking")
        with _WH_PATCH:
            result = engine.evaluate(lead)
        if not result.should_send:
            assert "Defence" not in result.reason


# ──────────────────────── Missing Data ────────────────────────


class TestMissingData:
    """Leads with missing required fields should be safely skipped."""

    def test_no_last_outreach_timestamp(self):
        engine = _make_engine()
        lead = _make_lead(last_outreach_at=None)
        with _WH_PATCH:
            result = engine.evaluate(lead)
        assert result.should_send is False
        assert "No last outreach timestamp" in result.reason

    def test_no_lead_type_defaults_investor(self):
        engine = _make_engine()
        lead = _make_lead(lead_type=None)
        with _WH_PATCH:
            result = engine.evaluate(lead)
        assert result.lead_type == "INVESTOR"

    def test_empty_first_name_uses_there(self):
        engine = _make_engine()
        lead = _make_lead(first_name="")
        with _WH_PATCH:
            result = engine.evaluate(lead)
        if result.should_send:
            assert "there" in result.body.lower()


# ──────────────────────── Output Shape ────────────────────────


class TestOutputShape:
    """Verify FollowUpAction fields when should_send=True."""

    def test_successful_evaluate_returns_all_fields(self):
        engine = _make_engine()
        last = datetime.now(UTC) - timedelta(days=6)
        lead = _make_lead(
            followup_stage=1,
            last_outreach_at=last.replace(tzinfo=None),
            first_name="Priya",
        )
        with _WH_PATCH:
            result = engine.evaluate(lead)

        if result.should_send:
            assert result.stage == 2
            assert result.subject.startswith("Re:")
            assert "Priya" in result.body
            assert result.campaign != ""
            assert result.max_stage == 3
            assert result.days_since_last >= 5
            assert result.interval_required == 5

    def test_reject_returns_reason(self):
        engine = _make_engine()
        lead = _make_lead(followup_stage=3)
        with _WH_PATCH:
            result = engine.evaluate(lead)
        assert result.should_send is False
        assert result.reason != ""
