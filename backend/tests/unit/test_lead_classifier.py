"""
Unit tests for LeadClassifier and infer_lead_classification.
Pure logic — no DB, no network.
"""

import pytest

from app.core.classification.lead_classifier import (
    LeadClassifier,
    infer_lead_classification,
    get_lead_classifier,
)


class TestLeadClassifierOwnerOverride:
    """Owner-based overrides take highest priority."""

    def test_yashika_override(self):
        classifier = LeadClassifier()
        lead_type, sector = classifier.classify(
            company_name="Some Corp", designation="CEO", owner_name="yashika"
        )
        assert lead_type == "INVESTOR"
        assert sector == "Investor - General"

    def test_kajal_override(self):
        classifier = LeadClassifier()
        lead_type, sector = classifier.classify(
            company_name="Some Corp", designation="CEO", owner_name="kajal"
        )
        assert lead_type == "INVESTOR"
        assert sector == "Investor - General"

    def test_palak_override(self):
        classifier = LeadClassifier()
        lead_type, sector = classifier.classify(
            company_name="Some Corp", designation="CEO", owner_name="palak"
        )
        assert lead_type == "CLIENT"
        assert sector == "Other"

    def test_vismaya_override(self):
        classifier = LeadClassifier()
        lead_type, sector = classifier.classify(
            company_name="Some Corp", designation="CEO", owner_name="vismaya"
        )
        assert lead_type == "CLIENT"
        assert sector == "Other"

    def test_ayush_override(self):
        classifier = LeadClassifier()
        lead_type, sector = classifier.classify(
            company_name="Some Corp", designation="CEO", owner_name="ayush"
        )
        assert lead_type == "INVESTOR"
        assert sector == "Investor - General"


class TestLeadClassifierKeywordMatching:
    """Keyword-based classification from company name, designation, remarks."""

    def test_investor_by_company_name(self):
        classifier = LeadClassifier()
        lead_type, sector = classifier.classify(
            company_name="Sequoia Capital", designation="Partner"
        )
        assert lead_type == "INVESTOR"

    def test_investor_by_designation(self):
        classifier = LeadClassifier()
        lead_type, sector = classifier.classify(
            company_name="Acme Corp", designation="Venture Partner"
        )
        assert lead_type == "INVESTOR"

    def test_client_default(self):
        classifier = LeadClassifier()
        lead_type, sector = classifier.classify(
            company_name="Acme Corp", designation="CTO"
        )
        assert lead_type == "CLIENT"

    def test_investor_by_remarks(self):
        classifier = LeadClassifier()
        lead_type, sector = classifier.classify(
            company_name="", designation="", remarks="Private equity fund"
        )
        assert lead_type == "INVESTOR"


class TestLeadClassifierSectorMatching:
    """Sector detection from keywords in combined text."""

    def test_ai_ml_sector(self):
        classifier = LeadClassifier()
        lead_type, sector = classifier.classify(
            company_name="The AI Company", designation="CEO"
        )
        assert lead_type == "CLIENT"
        assert sector == "AI & ML"

    def test_fintech_sector(self):
        classifier = LeadClassifier()
        lead_type, sector = classifier.classify(
            company_name="fintech company", designation="CEO"
        )
        assert lead_type == "CLIENT"
        assert sector == "FinTech"

    def test_saas_sector(self):
        classifier = LeadClassifier()
        lead_type, sector = classifier.classify(
            company_name="SaaS platform", designation="CTO"
        )
        assert lead_type == "CLIENT"
        assert sector == "SaaS"

    def test_vc_early_stage_sector(self):
        classifier = LeadClassifier()
        lead_type, sector = classifier.classify(
            company_name="Seed Fund VC", designation="Partner"
        )
        assert lead_type == "INVESTOR"
        assert sector == "VC - Early Stage"

    def test_private_equity_sector(self):
        classifier = LeadClassifier()
        lead_type, sector = classifier.classify(
            company_name="Private Equity Partners", designation="Managing Director"
        )
        assert lead_type == "INVESTOR"
        assert sector == "Private Equity"


class TestLeadClassifierEdgeCases:
    """Edge cases: empty fields, no sector match."""

    def test_empty_fields_default(self):
        classifier = LeadClassifier()
        lead_type, sector = classifier.classify(
            company_name="", designation="", remarks=""
        )
        assert lead_type == "CLIENT"
        assert sector == "Other"

    def test_investor_no_sector_match(self):
        classifier = LeadClassifier()
        lead_type, sector = classifier.classify(
            company_name="Venture Partners", designation="Partner"
        )
        assert lead_type == "INVESTOR"
        assert sector == "Investor - General"

    def test_none_owner(self):
        classifier = LeadClassifier()
        lead_type, sector = classifier.classify(
            company_name="Tech Corp", designation="CEO", owner_name=None
        )
        assert lead_type == "CLIENT"


class TestInferLeadClassificationFunction:
    """infer_lead_classification delegates to LeadClassifier correctly."""

    def test_delegates_investor(self):
        lead_type, sector = infer_lead_classification(
            company_name="Sequoia Capital", designation="Partner",
            remarks="", current_sector=None, owner_name=None
        )
        assert lead_type == "INVESTOR"

    def test_delegates_client(self):
        lead_type, sector = infer_lead_classification(
            company_name="Acme Corp", designation="CTO",
            remarks="", current_sector=None, owner_name=None
        )
        assert lead_type == "CLIENT"

    def test_delegates_with_owner(self):
        lead_type, sector = infer_lead_classification(
            company_name="Some Corp", designation="CEO",
            remarks="", current_sector=None, owner_name="palak"
        )
        assert lead_type == "CLIENT"
        assert sector == "Other"

    def test_singleton_exists(self):
        classifier = get_lead_classifier()
        assert classifier is not None
        assert isinstance(classifier, LeadClassifier)
