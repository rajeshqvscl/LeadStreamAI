"""
Unit tests for lead classification utilities.
"""
import pytest
from app.utils.classification import infer_lead_classification, normalize_sectors


class TestInferLeadClassification:
    """Tests for infer_lead_classification function."""

    def test_investor_by_company_name(self):
        """Test classification as INVESTOR when company name contains investor keywords."""
        lead_type, sector = infer_lead_classification(
            "Sequoia Capital",  # company_name
            "Partner",          # designation
            "",                 # remarks
            "Technology"        # current_sector
        )
        assert lead_type == "INVESTOR"

    def test_investor_by_designation(self):
        """Test classification as INVESTOR when designation contains investor keywords."""
        lead_type, sector = infer_lead_classification(
            "ABC Corp",
            "Venture Partner",
            "",
            ""
        )
        assert lead_type == "INVESTOR"

    def test_client_by_company_name(self):
        """Test classification as CLIENT when company name doesn't match investor keywords."""
        lead_type, sector = infer_lead_classification(
            "Acme Manufacturing",
            "CTO",
            "",
            "Manufacturing"
        )
        assert lead_type == "CLIENT"

    def test_sector_normalization(self):
        """Test that sector is normalized and returned (primary sector)."""
        lead_type, sector = infer_lead_classification(
            "Test Corp",
            "CEO",
            "",
            "AI/ML,  Data Science ,  FinTech"
        )
        # Should return primary sector (first one after normalization)
        assert sector == "AI/ML"

    def test_empty_sector_returns_default(self):
        """Test that empty sector returns a reasonable default."""
        lead_type, sector = infer_lead_classification(
            "Test Corp",
            "CEO",
            "",
            ""
        )
        # Should not be empty
        assert sector is not None


class TestNormalizeSectors:
    """Tests for normalize_sectors function."""

    def test_normalize_single_sector(self):
        """Test normalization of a single sector."""
        primary, all_sectors = normalize_sectors("Technology")
        assert primary == "Technology"
        assert all_sectors == ["Technology"]

    def test_normalize_multiple_sectors(self):
        """Test normalization of multiple sectors."""
        primary, all_sectors = normalize_sectors("AI/ML, FinTech, SaaS")
        assert primary == "AI/ML"
        assert "FinTech" in all_sectors
        assert "SaaS" in all_sectors

    def test_normalize_with_whitespace(self):
        """Test normalization handles extra whitespace."""
        primary, all_sectors = normalize_sectors("  Technology  ,  Healthcare  ")
        assert primary == "Technology"
        assert "Healthcare" in all_sectors

    def test_normalize_deduplicates(self):
        """Test that duplicate sectors are removed."""
        primary, all_sectors = normalize_sectors("Technology, technology, TECHNOLOGY")
        assert primary == "Technology"
        assert len(all_sectors) == 1

    def test_empty_string(self):
        """Test empty string handling."""
        primary, all_sectors = normalize_sectors("")
        assert primary is None or primary == ""
        assert all_sectors == []

    def test_none_input(self):
        """Test None input handling."""
        primary, all_sectors = normalize_sectors(None)
        assert primary is None or primary == ""
        assert all_sectors == []


# Run with: pytest tests/unit/test_classification.py -v