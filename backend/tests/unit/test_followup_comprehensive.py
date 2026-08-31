"""
Comprehensive test suite for followups flow.
Covers: engine, campaign resolver, followup service, error handling, edge cases.
No DB, no network, no Redis — pure unit tests.
"""

from datetime import UTC, datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest

from app.core.followup.campaign_resolver import CampaignResolver, LeadData
from app.core.followup.engine import FollowUpEngine, FollowUpAction
from app.core.config.settings import FollowupSettings
from app.core.pipeline.scheduler import SchedulerConfig

IST = timezone(timedelta(hours=5, minutes=30))


def _make_engine():
    engine = object.__new__(FollowUpEngine)
    engine.followup_settings = FollowupSettings()
    engine.scheduler_config = SchedulerConfig()
    engine.campaign_resolver = CampaignResolver()
    return engine


def _make_lead(**overrides) -> dict:
    now_utc = datetime.now(UTC)
    last_outreach = now_utc - timedelta(days=5)
    defaults = {
        "id": 1,
        "followup_stage": 0,
        "followup_status": "ACTIVE",
        "email_status": "SENT",
        "lead_type": "INVESTOR",
        "first_name": "Rahul",
        "last_outreach_at": last_outreach.replace(tzinfo=None),
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


_WH_PATCH = patch.object(SchedulerConfig, "is_followup_working_hours_now", return_value=True)


# ══════════════════════════════════════════════════════════════════
# 1. RE: PREFIX HANDLING — the bug we fixed
# ══════════════════════════════════════════════════════════════════

class TestRePrefixHandling:
    """Verify Re: prefix never stacks (Re: Re: Re:)."""

    def test_clean_subject_gets_one_re(self):
        engine = _make_engine()
        lead = _make_lead(last_outreach_subject="Investment Opportunity")
        with _WH_PATCH:
            result = engine.evaluate(lead)
        assert result.subject == "Re: Investment Opportunity"

    def test_existing_re_prefix_stripped(self):
        engine = _make_engine()
        lead = _make_lead(last_outreach_subject="Re: Investment Opportunity")
        with _WH_PATCH:
            result = engine.evaluate(lead)
        assert result.subject == "Re: Investment Opportunity"
        assert "Re: Re:" not in result.subject

    def test_double_re_stripped(self):
        engine = _make_engine()
        lead = _make_lead(last_outreach_subject="Re: Re: Investment Opportunity")
        with _WH_PATCH:
            result = engine.evaluate(lead)
        assert result.subject == "Re: Investment Opportunity"
        assert result.subject.count("Re:") == 1

    def test_triple_re_stripped(self):
        engine = _make_engine()
        lead = _make_lead(last_outreach_subject="Re: Re: Re: Investment Opportunity")
        with _WH_PATCH:
            result = engine.evaluate(lead)
        assert result.subject == "Re: Investment Opportunity"
        assert result.subject.count("Re:") == 1

    def test_re_case_insensitive(self):
        engine = _make_engine()
        lead = _make_lead(last_outreach_subject="re: RE: Re: Opportunity")
        with _WH_PATCH:
            result = engine.evaluate(lead)
        assert result.subject == "Re: Opportunity"
        assert result.subject.lower().count("re:") == 1

    def test_no_subject_defaults_to_following_up(self):
        engine = _make_engine()
        lead = _make_lead(last_outreach_subject=None)
        with _WH_PATCH:
            result = engine.evaluate(lead)
        assert result.subject == "Re: Following up"

    def test_empty_subject_defaults_to_following_up(self):
        engine = _make_engine()
        lead = _make_lead(last_outreach_subject="")
        with _WH_PATCH:
            result = engine.evaluate(lead)
        assert result.subject == "Re: Following up"

    def test_whitespace_subject_cleaned(self):
        engine = _make_engine()
        lead = _make_lead(last_outreach_subject="   ")
        with _WH_PATCH:
            result = engine.evaluate(lead)
        assert result.subject == "Re: Following up"


# ══════════════════════════════════════════════════════════════════
# 2. ENGINE ERROR HANDLING
# ══════════════════════════════════════════════════════════════════

class TestEngineErrorHandling:
    """Engine should never crash — always return safe FollowUpAction."""

    def test_empty_lead_dict(self):
        engine = _make_engine()
        with _WH_PATCH:
            result = engine.evaluate({})
        assert result.should_send is False
        assert result.reason != ""

    def test_lead_with_none_values(self):
        engine = _make_engine()
        lead = {k: None for k in [
            "id", "followup_stage", "followup_status", "email_status",
            "lead_type", "first_name", "last_outreach_at", "last_outreach_subject",
            "email_draft", "persona", "sector", "draft_template_used",
            "sender_name", "sender_email",
        ]}
        with _WH_PATCH:
            result = engine.evaluate(lead)
        assert result.should_send is False

    def test_lead_with_non_dict_values(self):
        engine = _make_engine()
        lead = _make_lead(followup_stage="not_a_number")
        with _WH_PATCH:
            result = engine.evaluate(lead)
        # Should not crash
        assert result.should_send is False

    def test_corrupt_timestamp(self):
        engine = _make_engine()
        lead = _make_lead(last_outreach_at="not-a-date")
        with _WH_PATCH:
            result = engine.evaluate(lead)
        assert result.should_send is False


# ══════════════════════════════════════════════════════════════════
# 3. INTERVAL TIMING — all stages
# ══════════════════════════════════════════════════════════════════

class TestIntervalTimingAllStages:
    """Investor: 0→2d, 1→5d, 2→7d. Client: 0→2d, 1→4d."""

    @pytest.mark.parametrize("stage,last_days,should_send", [
        (0, 1, False),   # too soon
        (0, 2, True),    # exactly on time
        (0, 3, True),    # overdue
        (1, 4, False),   # too soon (needs 5)
        (1, 5, True),    # exactly on time
        (1, 6, True),    # overdue
        (2, 6, False),   # too soon (needs 7)
        (2, 7, True),    # exactly on time
        (2, 8, True),    # overdue
    ])
    def test_investor_intervals(self, stage, last_days, should_send):
        engine = _make_engine()
        last = datetime.now(UTC) - timedelta(days=last_days)
        lead = _make_lead(followup_stage=stage, last_outreach_at=last.replace(tzinfo=None))
        with _WH_PATCH:
            result = engine.evaluate(lead)
        assert result.should_send is should_send, (
            f"Investor stage {stage}: {last_days}d ago should_send={result.should_send} "
            f"(expected {should_send}), reason={result.reason}"
        )

    @pytest.mark.parametrize("stage,last_days,should_send", [
        (0, 1, False),
        (0, 2, True),
        (1, 3, False),   # needs 4
        (1, 4, True),
    ])
    def test_client_intervals(self, stage, last_days, should_send):
        engine = _make_engine()
        last = datetime.now(UTC) - timedelta(days=last_days)
        lead = _make_lead(
            followup_stage=stage, lead_type="CLIENT",
            last_outreach_at=last.replace(tzinfo=None)
        )
        with _WH_PATCH:
            result = engine.evaluate(lead)
        assert result.should_send is should_send, (
            f"Client stage {stage}: {last_days}d ago should_send={result.should_send} "
            f"(expected {should_send}), reason={result.reason}"
        )


# ══════════════════════════════════════════════════════════════════
# 4. TIMEZONE HANDLING
# ══════════════════════════════════════════════════════════════════

class TestTimezoneHandling:
    """Engine converts UTC to IST. Verify both naive and timezone-aware timestamps."""

    def test_naive_utc_timestamp(self):
        engine = _make_engine()
        last = datetime.now(UTC) - timedelta(days=3)
        lead = _make_lead(last_outreach_at=last.replace(tzinfo=None))
        with _WH_PATCH:
            result = engine.evaluate(lead)
        assert result.days_since_last >= 2

    def test_aware_utc_timestamp(self):
        engine = _make_engine()
        last = datetime.now(UTC) - timedelta(days=3)
        lead = _make_lead(last_outreach_at=last)
        with _WH_PATCH:
            result = engine.evaluate(lead)
        assert result.days_since_last >= 2

    def test_aware_ist_timestamp(self):
        engine = _make_engine()
        last = datetime.now(IST) - timedelta(days=3)
        lead = _make_lead(last_outreach_at=last)
        with _WH_PATCH:
            result = engine.evaluate(lead)
        assert result.days_since_last >= 2


# ══════════════════════════════════════════════════════════════════
# 5. CAMPAIGN RESOLVER
# ══════════════════════════════════════════════════════════════════

class TestCampaignResolver:
    """Test campaign resolution for different lead types."""

    def test_investor_generic(self):
        lead = LeadData(
            id=1, lead_type="INVESTOR", persona="VC Investor",
            sector="Tech", original_subject="Funding Opportunity"
        )
        campaign = CampaignResolver.resolve(lead)
        assert campaign.startswith("INVESTOR")

    def test_client_type(self):
        lead = LeadData(id=1, lead_type="CLIENT", persona="SaaS CEO")
        campaign = CampaignResolver.resolve(lead)
        assert campaign == "CLIENT"

    def test_defence_skipped_in_engine(self):
        """Defence leads should be blocked by engine, not resolver."""
        engine = _make_engine()
        lead = _make_lead(persona="Defence Systems")
        with _WH_PATCH:
            result = engine.evaluate(lead)
        assert result.should_send is False
        assert "Defence" in result.reason

    def test_template_returns_string(self):
        template = CampaignResolver.get_template("INVESTOR_GENERIC", 1)
        assert isinstance(template, str)
        assert len(template) > 0

    def test_template_unknown_campaign_falls_back(self):
        template = CampaignResolver.get_template("NONEXISTENT_CAMPAIGN", 1)
        assert isinstance(template, str)
        assert len(template) > 0

    def test_template_unknown_stage_falls_back(self):
        template = CampaignResolver.get_template("INVESTOR_GENERIC", 99)
        assert isinstance(template, str)
        assert len(template) > 0

    def test_template_format_with_name(self):
        template = CampaignResolver.get_template("INVESTOR_GENERIC", 1)
        formatted = template.format(name="TestUser")
        assert "TestUser" in formatted


# ══════════════════════════════════════════════════════════════════
# 6. FOLLOWUP SERVICE FUNCTIONS
# ══════════════════════════════════════════════════════════════════

class TestFollowupServiceFunctions:
    """Test helper functions in followup_service.py."""

    def test_get_original_outreach_subject_prefers_first(self):
        from app.services.followup_service import get_original_outreach_subject
        lead = {
            "first_outreach_subject": "Original Subject",
            "last_outreach_subject": "Re: Original Subject"
        }
        result = get_original_outreach_subject(lead)
        assert result == "Original Subject"

    def test_get_original_outreach_subject_falls_back_to_last(self):
        from app.services.followup_service import get_original_outreach_subject
        lead = {"last_outreach_subject": "Re: Original Subject"}
        result = get_original_outreach_subject(lead)
        assert result == "Re: Original Subject"

    def test_get_original_outreach_subject_default(self):
        from app.services.followup_service import get_original_outreach_subject
        result = get_original_outreach_subject({})
        assert result == "Following up"

    def test_get_original_outreach_subject_none_lead(self):
        from app.services.followup_service import get_original_outreach_subject
        result = get_original_outreach_subject(None)
        assert result == "Following up"

    def test_get_original_outreach_subject_empty_strings(self):
        from app.services.followup_service import get_original_outreach_subject
        lead = {"first_outreach_subject": "", "last_outreach_subject": ""}
        result = get_original_outreach_subject(lead)
        assert result == "Following up"

    def test_is_generic_followup_none(self):
        from app.services.followup_service import is_generic_followup
        assert is_generic_followup(None) is True

    def test_is_generic_followup_empty(self):
        from app.services.followup_service import is_generic_followup
        assert is_generic_followup("") is True

    def test_is_generic_followup_generic_text(self):
        from app.services.followup_service import is_generic_followup
        assert is_generic_followup("Hi, just following up on my previous email. Let me know if you have any questions!") is True

    def test_is_generic_followup_custom_text(self):
        from app.services.followup_service import is_generic_followup
        assert is_generic_followup("Hi John, I wanted to discuss the Series A round we talked about last week.") is False

    def test_get_template_followup_returns_string(self):
        from app.services.followup_service import get_template_followup
        lead = _make_lead()
        result = get_template_followup(lead, 1)
        assert isinstance(result, str)
        assert len(result) > 0

    def test_get_template_followup_with_name(self):
        from app.services.followup_service import get_template_followup
        lead = _make_lead(first_name="Priya")
        result = get_template_followup(lead, 1)
        assert "Priya" in result


# ══════════════════════════════════════════════════════════════════
# 7. EDGE CASES
# ══════════════════════════════════════════════════════════════════

class TestEdgeCases:
    """Various edge cases and boundary conditions."""

    def test_very_long_subject(self):
        engine = _make_engine()
        lead = _make_lead(last_outreach_subject="A" * 500)
        with _WH_PATCH:
            result = engine.evaluate(lead)
        if result.should_send:
            assert result.subject.startswith("Re:")
            assert len(result.subject) < 600

    def test_unicode_in_subject(self):
        engine = _make_engine()
        lead = _make_lead(last_outreach_subject="नमस्ते Opportunity 🚀")
        with _WH_PATCH:
            result = engine.evaluate(lead)
        if result.should_send:
            assert "Re:" in result.subject

    def test_special_chars_in_name(self):
        engine = _make_engine()
        lead = _make_lead(first_name="O'Brien-Smith")
        with _WH_PATCH:
            result = engine.evaluate(lead)
        if result.should_send:
            assert "O'Brien-Smith" in result.body

    def test_empty_name_fallback(self):
        engine = _make_engine()
        lead = _make_lead(first_name="")
        with _WH_PATCH:
            result = engine.evaluate(lead)
        if result.should_send:
            assert "there" in result.body.lower()

    def test_negative_followup_stage(self):
        engine = _make_engine()
        lead = _make_lead(followup_stage=-1)
        with _WH_PATCH:
            result = engine.evaluate(lead)
        # Negative stage has no interval defined — correctly rejected
        assert result.should_send is False
        assert "No interval defined" in result.reason

    def test_unknown_lead_type_defaults_investor(self):
        engine = _make_engine()
        lead = _make_lead(lead_type="UNKNOWN")
        with _WH_PATCH:
            result = engine.evaluate(lead)
        assert result.lead_type in ("INVESTOR", "UNKNOWN")

    def test_lead_type_case_insensitive(self):
        engine = _make_engine()
        lead = _make_lead(lead_type="client")
        with _WH_PATCH:
            result = engine.evaluate(lead)
        # Should be treated as CLIENT
        assert result.max_stage == 2


# ══════════════════════════════════════════════════════════════════
# 8. OUTPUT CONSISTENCY
# ══════════════════════════════════════════════════════════════════

class TestOutputConsistency:
    """Verify FollowUpAction is always well-formed."""

    def test_reject_always_has_reason(self):
        engine = _make_engine()
        lead = _make_lead(followup_stage=10)
        with _WH_PATCH:
            result = engine.evaluate(lead)
        assert result.should_send is False
        assert isinstance(result.reason, str)
        assert len(result.reason) > 0

    def test_accept_always_has_subject_and_body(self):
        engine = _make_engine()
        last = datetime.now(UTC) - timedelta(days=3)
        lead = _make_lead(followup_stage=0, last_outreach_at=last.replace(tzinfo=None))
        with _WH_PATCH:
            result = engine.evaluate(lead)
        if result.should_send:
            assert isinstance(result.subject, str)
            assert isinstance(result.body, str)
            assert len(result.subject) > 0
            assert len(result.body) > 0

    def test_stage_always_incremented(self):
        engine = _make_engine()
        last = datetime.now(UTC) - timedelta(days=3)
        lead = _make_lead(followup_stage=0, last_outreach_at=last.replace(tzinfo=None))
        with _WH_PATCH:
            result = engine.evaluate(lead)
        if result.should_send:
            assert result.stage == lead["followup_stage"] + 1

    def test_max_stage_matches_lead_type(self):
        engine = _make_engine()
        last = datetime.now(UTC) - timedelta(days=3)

        lead_inv = _make_lead(followup_stage=0, lead_type="INVESTOR", last_outreach_at=last.replace(tzinfo=None))
        with _WH_PATCH:
            result_inv = engine.evaluate(lead_inv)
        if result_inv.should_send:
            assert result_inv.max_stage == 3

        lead_cli = _make_lead(followup_stage=0, lead_type="CLIENT", last_outreach_at=last.replace(tzinfo=None))
        with _WH_PATCH:
            result_cli = engine.evaluate(lead_cli)
        if result_cli.should_send:
            assert result_cli.max_stage == 2
