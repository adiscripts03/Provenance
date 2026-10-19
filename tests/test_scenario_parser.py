"""Tests for Component 3: Scenario Understanding & LLM Gateway."""

from __future__ import annotations

import pytest
from unittest.mock import MagicMock

from provenance.agents.scenario_parser import parse_scenario
from provenance.llm import LLMGateway, LLMValidationError
from provenance.models.scenario import ScenarioFacts

def test_parse_mumbai_scenario_live():
    """Test live LLM parsing of the canonical Mumbai scenario from README."""
    scenario = (
        "A Mumbai warehouse wants to purchase equipment worth ₹4,80,000 from a new vendor. "
        "The warehouse manager approved the purchase, but procurement has not reviewed the vendor."
    )

    facts = parse_scenario(scenario)
    assert isinstance(facts, ScenarioFacts)
    assert facts.region is not None and "mumbai" in facts.region.lower()
    assert facts.amount is not None and facts.amount == 480000.0
    assert facts.vendor_status is not None and any(kw in facts.vendor_status.lower() for kw in ["new", "unreviewed"])
    assert any("warehouse manager" in a.lower() for a in facts.approvals_obtained)

def test_parse_scenario_missing_facts_live():
    """Test scenario with incomplete information records missing_facts without inventing."""
    scenario = "We need to purchase warehouse equipment urgently."

    facts = parse_scenario(scenario)
    assert isinstance(facts, ScenarioFacts)
    assert facts.amount is None

    assert len(facts.missing_facts) > 0

def test_llm_gateway_validation_retry():
    """Test gateway retries once on invalid JSON and falls back safely."""
    mock_gateway = MagicMock(spec=LLMGateway)
    mock_gateway.generate_structured.side_effect = LLMValidationError("Invalid schema")

    facts = parse_scenario("Test scenario", gateway=mock_gateway)
    assert isinstance(facts, ScenarioFacts)
    assert len(facts.missing_facts) > 0
    assert "safely validate" in facts.missing_facts[0]
