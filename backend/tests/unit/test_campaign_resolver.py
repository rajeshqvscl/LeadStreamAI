"""
Unit tests for CampaignResolver
Rule-based campaign/template selection — pure logic, no side effects.
"""

import pytest

from app.core.config.constants import DEFAULT_TEMPLATES
from app.core.followup.campaign_resolver import CampaignResolver, LeadData


# ──────────────────────── Palak Advisory ────────────────────────


class TestPalakAdvisory:
    """INVESTOR_PALAK_ADVISORY rule."""

    def test_template_name_match(self):
        lead = LeadData(id=1, draft_template_used="palak_mam_corporate_advisory")
        assert CampaignResolver.resolve(lead) == "INVESTOR_PALAK_ADVISORY"

    def test_template_mna_match(self):
        lead = LeadData(id=1, draft_template_used="palak_mam_mna_fundraising")
        assert CampaignResolver.resolve(lead) == "INVESTOR_PALAK_ADVISORY"

    def test_template_draft1_match(self):
        lead = LeadData(id=1, draft_template_used="palak_mam_Draft_1")
        assert CampaignResolver.resolve(lead) == "INVESTOR_PALAK_ADVISORY"

    def test_subject_corporate_advisory(self):
        lead = LeadData(id=1, original_subject="Corporate Advisory Services")
        assert CampaignResolver.resolve(lead) == "INVESTOR_PALAK_ADVISORY"

    def test_draft_corporate_advisory_without_ma(self):
        lead = LeadData(id=1, email_draft="We offer corporate advisory services for growth companies.")
        assert CampaignResolver.resolve(lead) == "INVESTOR_PALAK_ADVISORY"

    def test_draft_corporate_advisory_with_ma_not_matched(self):
        """If draft has 'corporate advisory' AND 'm&a', Palak rule should NOT match."""
        lead = LeadData(id=1, email_draft="We do corporate advisory and M&A for mid-market firms.")
        result = CampaignResolver.resolve(lead)
        # Should NOT be Palak because m&a is present
        assert result != "INVESTOR_PALAK_ADVISORY"


# ──────────────────────── Kajal Health Ecosystem ────────────────────────


class TestKajalHealthEcosystem:
    """INVESTOR_KAJAL_HEALTH_ECOSYSTEM rule."""

    def test_template_name_match(self):
        lead = LeadData(id=1, draft_template_used="kajal_mam_health_ecosystem")
        assert CampaignResolver.resolve(lead) == "INVESTOR_KAJAL_HEALTH_ECOSYSTEM"


# ──────────────────────── Kajal JV ────────────────────────


class TestKajalJV:
    """INVESTOR_KAJAL_JV rule."""

    def test_template_jv_match(self):
        lead = LeadData(id=1, draft_template_used="kajal_mam_jv")
        assert CampaignResolver.resolve(lead) == "INVESTOR_KAJAL_JV"

    def test_template_qvscl_intro_match(self):
        lead = LeadData(id=1, draft_template_used="kajal_mam_qvscl_intro")
        assert CampaignResolver.resolve(lead) == "INVESTOR_KAJAL_JV"

    def test_subject_jv_match(self):
        lead = LeadData(id=1, original_subject="JV & Investment Opportunity")
        assert CampaignResolver.resolve(lead) == "INVESTOR_KAJAL_JV"

    def test_subject_strategic_partnership(self):
        lead = LeadData(id=1, original_subject="Strategic Partnership Opportunity for Growth")
        assert CampaignResolver.resolve(lead) == "INVESTOR_KAJAL_JV"


# ──────────────────────── Kajal Generic ────────────────────────


class TestKajalGeneric:
    """INVESTOR_KAJAL_GENERIC rule."""

    def test_hyphen_template(self):
        lead = LeadData(id=1, draft_template_used="kajal_mam_hyphen")
        assert CampaignResolver.resolve(lead) == "INVESTOR_KAJAL_GENERIC"

    def test_agritech_template(self):
        lead = LeadData(id=1, draft_template_used="kajal_mam_agritech")
        assert CampaignResolver.resolve(lead) == "INVESTOR_KAJAL_GENERIC"


# ──────────────────────── AI Hiring ────────────────────────


class TestAIHiring:
    """INVESTOR_AI_HIRING rule."""

    def test_subject_hiring(self):
        lead = LeadData(id=1, original_subject="AI Hiring Platform Overview")
        assert CampaignResolver.resolve(lead) == "INVESTOR_AI_HIRING"

    def test_persona_recruitment(self):
        lead = LeadData(id=1, persona="Recruitment Tech Expert")
        assert CampaignResolver.resolve(lead) == "INVESTOR_AI_HIRING"

    def test_sector_hiring(self):
        lead = LeadData(id=1, sector="Hiring & Staffing")
        assert CampaignResolver.resolve(lead) == "INVESTOR_AI_HIRING"

    def test_draft_hiring(self):
        lead = LeadData(id=1, email_draft="This platform revolutionizes hiring with AI.")
        assert CampaignResolver.resolve(lead) == "INVESTOR_AI_HIRING"


# ──────────────────────── HealthTech ────────────────────────


class TestHealthTech:
    """INVESTOR_HEALTHTECH rule."""

    def test_subject_health(self):
        lead = LeadData(id=1, original_subject="HealthTech Startup Overview")
        assert CampaignResolver.resolve(lead) == "INVESTOR_HEALTHTECH"

    def test_sector_diagnostic(self):
        lead = LeadData(id=1, sector="Diagnostics & Imaging")
        assert CampaignResolver.resolve(lead) == "INVESTOR_HEALTHTECH"

    def test_draft_health(self):
        lead = LeadData(id=1, email_draft="Our health monitoring platform uses AI.")
        assert CampaignResolver.resolve(lead) == "INVESTOR_HEALTHTECH"


# ──────────────────────── Defence (skip) ────────────────────────


class TestDefence:
    """INVESTOR_DEFENCE rule — note: engine skips defence, but resolver still matches."""

    def test_subject_defence(self):
        lead = LeadData(id=1, original_subject="Defence Systems Opportunity")
        assert CampaignResolver.resolve(lead) == "INVESTOR_DEFENCE"

    def test_sector_deeptech(self):
        lead = LeadData(id=1, sector="Deeptech & Aerospace")
        assert CampaignResolver.resolve(lead) == "INVESTOR_DEFENCE"

    def test_persona_idex(self):
        lead = LeadData(id=1, persona="iDEX Challenge Winner")
        assert CampaignResolver.resolve(lead) == "INVESTOR_DEFENCE"


# ──────────────────────── Agritech ────────────────────────


class TestAgritech:
    """INVESTOR_AGRITECH / INVESTOR_YASHIKA_AGRITECH rules."""

    def test_subject_agritech(self):
        lead = LeadData(id=1, original_subject="Climate Agritech Platform")
        assert CampaignResolver.resolve(lead) == "INVESTOR_AGRITECH"

    def test_subject_climate(self):
        lead = LeadData(id=1, original_subject="Climate-Smart Agriculture Opportunity")
        assert CampaignResolver.resolve(lead) == "INVESTOR_AGRITECH"

    def test_sector_agritech(self):
        lead = LeadData(id=1, sector="Agritech & Climate")
        assert CampaignResolver.resolve(lead) == "INVESTOR_AGRITECH"

    def test_yashika_agritech(self):
        lead = LeadData(
            id=1,
            is_agritech=True,
            sender_name="Yashika",
            draft_template_used="some_agritech_template",
        )
        assert CampaignResolver.resolve(lead) == "INVESTOR_YASHIKA_AGRITECH"

    def test_agritech_auto_detect(self):
        """is_agritech auto-detected from draft content."""
        lead = LeadData(id=1, email_draft="An agritech platform for sustainable farming.")
        result = CampaignResolver.resolve(lead)
        # Should be INVESTOR_AGRITECH or INVESTOR_YASHIKA_AGRITECH depending on sender
        assert result in ("INVESTOR_AGRITECH", "INVESTOR_YASHIKA_AGRITECH")


# ──────────────────────── Fallback ────────────────────────


class TestFallback:
    """Fallback rules: CLIENT → CLIENT, otherwise → INVESTOR_GENERIC."""

    def test_client_lead_type(self):
        lead = LeadData(id=1, lead_type="CLIENT")
        assert CampaignResolver.resolve(lead) == "CLIENT"

    def test_investor_fallback(self):
        lead = LeadData(id=1, lead_type="INVESTOR")
        assert CampaignResolver.resolve(lead) == "INVESTOR_GENERIC"

    def test_empty_lead_resolves(self):
        """Completely empty lead should still resolve without crashing."""
        lead = LeadData(id=0)
        result = CampaignResolver.resolve(lead)
        assert result in ("CLIENT", "INVESTOR_GENERIC")


# ──────────────────────── Rule Priority ────────────────────────


class TestRulePriority:
    """More specific rules should match before generic fallbacks."""

    def test_palak_beats_generic(self):
        lead = LeadData(
            id=1,
            draft_template_used="palak_mam_corporate_advisory",
            lead_type="INVESTOR",
        )
        assert CampaignResolver.resolve(lead) == "INVESTOR_PALAK_ADVISORY"

    def test_kajal_jv_beats_generic(self):
        lead = LeadData(
            id=1,
            original_subject="JV & Investment Opportunity in Healthcare",
            lead_type="INVESTOR",
        )
        # Should match JV (more specific) not just HEALTHTECH
        assert CampaignResolver.resolve(lead) == "INVESTOR_KAJAL_JV"

    def test_template_name_beats_content(self):
        """Explicit template name should beat content-based detection."""
        lead = LeadData(
            id=1,
            draft_template_used="kajal_mam_hyphen",
            original_subject="Healthcare AI Platform",  # would match HEALTHTECH
        )
        # KAJAL_GENERIC (template name) should match before HEALTHTECH
        assert CampaignResolver.resolve(lead) == "INVESTOR_KAJAL_GENERIC"


# ──────────────────────── get_template ────────────────────────


class TestGetTemplate:
    """CampaignResolver.get_template() returns correct templates with fallback."""

    def test_known_template_stage1(self):
        tpl = CampaignResolver.get_template("INVESTOR_GENERIC", 1)
        assert "{name}" in tpl
        assert len(tpl) > 20

    def test_known_template_stage2(self):
        tpl = CampaignResolver.get_template("INVESTOR_GENERIC", 2)
        assert "{name}" in tpl

    def test_known_template_stage3(self):
        tpl = CampaignResolver.get_template("INVESTOR_GENERIC", 3)
        assert "{name}" in tpl

    def test_unknown_campaign_falls_back_to_generic(self):
        tpl = CampaignResolver.get_template("NONEXISTENT_CAMPAIGN", 1)
        generic = CampaignResolver.get_template("INVESTOR_GENERIC", 1)
        assert tpl == generic

    def test_missing_stage_falls_back_to_stage1(self):
        """If a campaign doesn't have a specific stage, should fall back to stage 1."""
        tpl = CampaignResolver.get_template("INVESTOR_GENERIC", 999)
        stage1 = CampaignResolver.get_template("INVESTOR_GENERIC", 1)
        assert tpl == stage1

    def test_all_campaign_templates_have_name_placeholder(self):
        """Every template in DEFAULT_TEMPLATES should have {name} placeholder.
        Known exceptions: templates that are intentionally static (no personalization).
        """
        SKIP = {
            ("INVESTOR_KAJAL_JV", 1),  # static template, no {name}
        }
        for campaign_key, stages in DEFAULT_TEMPLATES.items():
            for stage_num, template in stages.items():
                if (campaign_key, stage_num) in SKIP:
                    continue
                assert "{name}" in template, (
                    f"Template {campaign_key} stage {stage_num} missing {{name}} placeholder"
                )

    def test_all_campaigns_have_stage1(self):
        """Every campaign should at least have stage 1."""
        for campaign_key, stages in DEFAULT_TEMPLATES.items():
            assert 1 in stages, f"Campaign {campaign_key} missing stage 1"
