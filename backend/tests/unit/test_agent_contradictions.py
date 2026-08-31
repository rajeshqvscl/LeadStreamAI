"""
Unit tests for AgentService.detect_contradictions()
Pure dict comparison — no DB, no LLM, no network.
"""

import pytest

from app.services.agent_service import AgentService


def _make_service():
    """Create AgentService without instantiating LLM."""
    return object.__new__(AgentService)


class TestDetectContradictions:
    """Tests for AgentService.detect_contradictions method."""

    def test_no_contradictions(self):
        service = _make_service()
        lead_data = {"sector": "fintech", "remarks": ""}
        rag_insights = {"category": "fintech"}
        result = service.detect_contradictions(lead_data, rag_insights)
        assert result == []

    def test_sector_mismatch(self):
        service = _make_service()
        lead_data = {"sector": "fintech", "remarks": ""}
        rag_insights = {"category": "healthcare"}
        result = service.detect_contradictions(lead_data, rag_insights)
        assert len(result) == 1
        assert "Sector Mismatch" in result[0]

    def test_revenue_conflict(self):
        service = _make_service()
        lead_data = {"sector": "", "remarks": "pre-revenue startup"}
        rag_insights = {"actuals": {"revenue": "50 Cr"}}
        result = service.detect_contradictions(lead_data, rag_insights)
        assert len(result) == 1
        assert "Revenue Conflict" in result[0]

    def test_revenue_no_conflict_when_not_pre_revenue(self):
        service = _make_service()
        lead_data = {"sector": "", "remarks": "profitable company"}
        rag_insights = {"actuals": {"revenue": "50 Cr"}}
        result = service.detect_contradictions(lead_data, rag_insights)
        assert result == []

    def test_stage_mismatch(self):
        service = _make_service()
        lead_data = {"sector": "", "remarks": "seed stage"}
        rag_insights = {"stage": "series b", "actuals": {"revenue": "10 Cr"}}
        result = service.detect_contradictions(lead_data, rag_insights)
        assert len(result) == 1
        assert "Stage Mismatch" in result[0]

    def test_empty_rag_insights_no_contradictions(self):
        service = _make_service()
        lead_data = {"sector": "fintech", "remarks": "seed stage"}
        rag_insights = {}
        result = service.detect_contradictions(lead_data, rag_insights)
        assert result == []

    def test_empty_lead_data_no_contradictions(self):
        service = _make_service()
        lead_data = {}
        rag_insights = {"category": "healthcare", "stage": "series a", "actuals": {"revenue": "10 Cr"}}
        result = service.detect_contradictions(lead_data, rag_insights)
        assert result == []

    def test_partial_data_only_sector(self):
        service = _make_service()
        lead_data = {"sector": "fintech"}
        rag_insights = {"category": "fintech"}
        result = service.detect_contradictions(lead_data, rag_insights)
        assert result == []

    def test_multiple_contradictions(self):
        service = _make_service()
        lead_data = {"sector": "fintech", "remarks": "seed stage"}
        rag_insights = {
            "category": "healthcare",
            "stage": "series b",
            "actuals": {"revenue": "50 Cr"},
        }
        result = service.detect_contradictions(lead_data, rag_insights)
        assert len(result) >= 2


# Run with: pytest tests/unit/test_agent_contradictions.py -v
