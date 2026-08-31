"""
Unit tests for Lead Pipeline State Machine.
Pure logic — no DB, no network.
"""

from unittest.mock import patch, MagicMock

import pytest

from app.core.pipeline.state_machine import (
    LeadState,
    LeadPipeline,
    TransitionGuard,
    Lead,
    SchedulerConfig,
    TERMINAL_STATES,
    TRANSITIONS,
)


def _make_config():
    """Build a SchedulerConfig with known settings, bypassing lru_cache."""
    config = object.__new__(SchedulerConfig)
    config.scheduler = MagicMock()
    config.scheduler.working_hours_start = 9
    config.scheduler.working_hours_end = 18
    config.followup = MagicMock()
    config.followup.investor_max_stage = 3
    config.followup.client_max_stage = 2
    config.followup.investor_intervals = "0:2,1:5,2:8"
    config.followup.client_intervals = "0:2,1:5"
    config.is_working_hours_now = MagicMock(return_value=True)
    return config


def _make_lead(**overrides) -> Lead:
    defaults = {
        "id": 1,
        "pipeline_state": "NEW",
        "followup_stage": 0,
        "followup_status": "ACTIVE",
        "email_status": "SENT",
        "is_responded": False,
        "replied_at": None,
        "reply_intent": "",
        "email_opt_in": True,
        "is_unsubscribed": False,
        "auto_followup": True,
        "google_refresh_token": "dummy_token",
        "lead_type": "INVESTOR",
        "user_id": 1,
    }
    defaults.update(overrides)
    return Lead(**defaults)


class TestLeadStateEnum:
    """Verify LeadState enum completeness."""

    def test_all_states_exist(self):
        expected = [
            "NEW", "DRAFT_PENDING", "SCHEDULED", "SENT",
            "FOLLOWUP_ACTIVE", "FOLLOWUP_PAUSED", "REPLIED",
            "MEETING_REQUIRED", "CLOSED_WON", "CLOSED_LOST",
            "UNSUBSCRIBED", "BOUNCED",
        ]
        for state in expected:
            assert hasattr(LeadState, state)
            assert LeadState(state).value == state

    def test_terminal_states_set(self):
        expected = {LeadState.CLOSED_WON, LeadState.CLOSED_LOST, LeadState.UNSUBSCRIBED, LeadState.BOUNCED}
        assert TERMINAL_STATES == expected


class TestCanTransition:
    """Test structural + guard-based transition validation."""

    def test_new_to_draft_pending_allowed(self):
        config = _make_config()
        pipeline = LeadPipeline(config)
        lead = _make_lead(pipeline_state="NEW")
        assert pipeline.can_transition(LeadState.NEW, LeadState.DRAFT_PENDING, lead)

    def test_new_to_sent_blocked(self):
        config = _make_config()
        pipeline = LeadPipeline(config)
        lead = _make_lead(pipeline_state="NEW")
        assert not pipeline.can_transition(LeadState.NEW, LeadState.SENT, lead)

    def test_draft_pending_to_scheduled_allowed(self):
        config = _make_config()
        pipeline = LeadPipeline(config)
        lead = _make_lead(pipeline_state="DRAFT_PENDING")
        assert pipeline.can_transition(LeadState.DRAFT_PENDING, LeadState.SCHEDULED, lead)

    def test_scheduled_to_new_allowed(self):
        config = _make_config()
        pipeline = LeadPipeline(config)
        lead = _make_lead(pipeline_state="SCHEDULED")
        assert pipeline.can_transition(LeadState.SCHEDULED, LeadState.NEW, lead)

    def test_sent_to_followup_active_allowed(self):
        config = _make_config()
        pipeline = LeadPipeline(config)
        lead = _make_lead(pipeline_state="SENT")
        assert pipeline.can_transition(LeadState.SENT, LeadState.FOLLOWUP_ACTIVE, lead)

    def test_sent_to_replied_guard_direct(self):
        lead = _make_lead(pipeline_state="SENT", is_responded=True)
        assert TransitionGuard.sent_to_replied(lead)

    def test_sent_to_bounced_guard_direct(self):
        lead = _make_lead(pipeline_state="SENT", email_status="BOUNCED")
        assert TransitionGuard.any_to_bounced(lead)

    def test_terminal_blocks_outgoing(self):
        config = _make_config()
        pipeline = LeadPipeline(config)
        for state in TERMINAL_STATES:
            lead = _make_lead(pipeline_state=state.value)
            assert not pipeline.can_transition(state, LeadState.NEW, lead)

    def test_closed_won_to_anything_blocked(self):
        config = _make_config()
        pipeline = LeadPipeline(config)
        lead = _make_lead(pipeline_state="CLOSED_WON")
        for target in [LeadState.NEW, LeadState.SENT, LeadState.REPLIED]:
            assert not pipeline.can_transition(LeadState.CLOSED_WON, target, lead)

    def test_invalid_structural_transition_blocked(self):
        config = _make_config()
        pipeline = LeadPipeline(config)
        lead = _make_lead(pipeline_state="NEW")
        assert not pipeline.can_transition(LeadState.NEW, LeadState.SCHEDULED, lead)

    def test_followup_active_can_self_transition(self):
        config = _make_config()
        pipeline = LeadPipeline(config)
        lead = _make_lead(pipeline_state="FOLLOWUP_ACTIVE")
        assert pipeline.can_transition(LeadState.FOLLOWUP_ACTIVE, LeadState.FOLLOWUP_ACTIVE, lead)

    def test_followup_active_to_replied_guard_direct(self):
        lead = _make_lead(pipeline_state="FOLLOWUP_ACTIVE", is_responded=True)
        assert TransitionGuard.sent_to_replied(lead)

    def test_followup_active_to_closed_lost(self):
        config = _make_config()
        pipeline = LeadPipeline(config)
        lead = _make_lead(pipeline_state="FOLLOWUP_ACTIVE")
        assert pipeline.can_transition(LeadState.FOLLOWUP_ACTIVE, LeadState.CLOSED_LOST, lead)

    def test_replied_to_meeting_required(self):
        config = _make_config()
        pipeline = LeadPipeline(config)
        lead = _make_lead(pipeline_state="REPLIED")
        assert pipeline.can_transition(LeadState.REPLIED, LeadState.MEETING_REQUIRED, lead)

    def test_meeting_required_to_closed_won(self):
        config = _make_config()
        pipeline = LeadPipeline(config)
        lead = _make_lead(pipeline_state="MEETING_REQUIRED")
        assert pipeline.can_transition(LeadState.MEETING_REQUIRED, LeadState.CLOSED_WON, lead)


class TestForceTransition:
    """force_transition bypasses guards but respects terminal states."""

    def test_force_transition_bypasses_guards(self):
        config = _make_config()
        pipeline = LeadPipeline(config)
        lead = _make_lead(pipeline_state="NEW")
        # NEW -> SENT has no guard but is not in TRANSITIONS — force should work
        assert pipeline.force_transition(lead, LeadState.SENT)
        assert lead.pipeline_state == "SENT"

    def test_force_transition_from_terminal_blocked(self):
        config = _make_config()
        pipeline = LeadPipeline(config)
        lead = _make_lead(pipeline_state="CLOSED_WON")
        assert not pipeline.force_transition(lead, LeadState.NEW)
        assert lead.pipeline_state == "CLOSED_WON"

    def test_force_transition_unsubscribed_blocked(self):
        config = _make_config()
        pipeline = LeadPipeline(config)
        lead = _make_lead(pipeline_state="UNSUBSCRIBED")
        assert not pipeline.force_transition(lead, LeadState.NEW)

    def test_force_transition_bounced_blocked(self):
        config = _make_config()
        pipeline = LeadPipeline(config)
        lead = _make_lead(pipeline_state="BOUNCED")
        assert not pipeline.force_transition(lead, LeadState.SENT)


class TestGetValidNextStates:
    """Get all structurally valid + guard-passing next states."""

    def test_new_valid_next(self):
        config = _make_config()
        pipeline = LeadPipeline(config)
        lead = _make_lead(pipeline_state="NEW")
        states = pipeline.get_valid_next_states(lead)
        assert LeadState.DRAFT_PENDING in states

    def test_draft_pending_valid_next(self):
        config = _make_config()
        pipeline = LeadPipeline(config)
        lead = _make_lead(pipeline_state="DRAFT_PENDING")
        states = pipeline.get_valid_next_states(lead)
        assert LeadState.SCHEDULED in states
        assert LeadState.NEW in states

    def test_scheduled_valid_next(self):
        config = _make_config()
        pipeline = LeadPipeline(config)
        lead = _make_lead(pipeline_state="SCHEDULED")
        states = pipeline.get_valid_next_states(lead)
        assert LeadState.SENT in states
        assert LeadState.NEW in states

    def test_terminal_returns_empty(self):
        config = _make_config()
        pipeline = LeadPipeline(config)
        for state in TERMINAL_STATES:
            lead = _make_lead(pipeline_state=state.value)
            states = pipeline.get_valid_next_states(lead)
            assert states == []


class TestTransitionGuard:
    """Test static guard methods."""

    def test_sent_to_followup_active_requires_token(self):
        config = _make_config()
        lead = _make_lead(followup_stage=0, google_refresh_token="token")
        assert TransitionGuard.sent_to_followup_active(lead, config)

    def test_sent_to_followup_active_blocks_no_token(self):
        config = _make_config()
        lead = _make_lead(followup_stage=0, google_refresh_token=None)
        assert not TransitionGuard.sent_to_followup_active(lead, config)

    def test_sent_to_followup_active_blocks_responded(self):
        config = _make_config()
        lead = _make_lead(followup_stage=0, is_responded=True)
        assert not TransitionGuard.sent_to_followup_active(lead, config)

    def test_sent_to_followup_active_blocks_replied_at(self):
        config = _make_config()
        from datetime import datetime, timezone
        lead = _make_lead(followup_stage=0, replied_at=datetime.now(timezone.utc))
        assert not TransitionGuard.sent_to_followup_active(lead, config)

    def test_sent_to_followup_active_blocks_max_stage(self):
        config = _make_config()
        config.followup.investor_max_stage = 3
        lead = _make_lead(followup_stage=3, lead_type="INVESTOR")
        assert not TransitionGuard.sent_to_followup_active(lead, config)

    def test_sent_to_followup_active_blocks_auto_followup_off(self):
        config = _make_config()
        lead = _make_lead(followup_stage=0, auto_followup=False)
        assert not TransitionGuard.sent_to_followup_active(lead, config)

    def test_any_to_unsubscribed_checks_opt_in(self):
        lead = _make_lead(email_opt_in=False)
        assert TransitionGuard.any_to_unsubscribed(lead)

    def test_any_to_unsubscribed_checks_is_unsubscribed(self):
        lead = _make_lead(is_unsubscribed=True)
        assert TransitionGuard.any_to_unsubscribed(lead)

    def test_any_to_unsubscribed_blocks_when_opted_in(self):
        lead = _make_lead(email_opt_in=True, is_unsubscribed=False)
        assert not TransitionGuard.any_to_unsubscribed(lead)

    def test_any_to_bounced_checks_email_status(self):
        lead = _make_lead(email_status="BOUNCED")
        assert TransitionGuard.any_to_bounced(lead)

    def test_any_to_bounced_blocks_non_bounced(self):
        lead = _make_lead(email_status="SENT")
        assert not TransitionGuard.any_to_bounced(lead)
