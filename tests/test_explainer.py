"""Tests for Component 8: Explanation Agent."""

from __future__ import annotations

import pytest
from unittest.mock import MagicMock

from provenance.agents.explainer import generate_explanation
from provenance.llm import LLMGateway, LLMValidationError
from provenance.models.decision import Decision, PolicyCitation, VerdictEnum
from provenance.models.policy import PrecedenceLevel
from provenance.models.rule import ExtractedRequirement
from provenance.models.scenario import ScenarioFacts
from provenance.resolver.engine import ResolverOutput

def test_explainer_fallback_on_error():
    """Verify fallback Decision object is built cleanly if LLM call fails."""
    mock_gateway = MagicMock(spec=LLMGateway)
    mock_gateway.generate_structured.side_effect = LLMValidationError("LLM timeout")

    facts = ScenarioFacts(region="Mumbai", amount=480000.0)
    rule = ExtractedRequirement(
        rule_id="RULE-MUM-2.1",
        chunk_id="POL-REG-MUM-2026-002#§2.1",
        policy_title="Mumbai Regional Policy 2026",
        section="§2.1",
        precedence_level=PrecedenceLevel.LEVEL_2_REGIONAL_DEPT,
        exact_quote="Warehouse purchases above ₹3,00,000 require regional approval.",
    )
    resolver_out = ResolverOutput(
        verdict=VerdictEnum.NON_COMPLIANT,
        reason="Purchase exceeds ₹3,00,000 without regional approval.",
        applicable_rules=[rule],
        missing_requirements=["Mumbai regional approval"],
    )

    decision = generate_explanation(
        scenario_text="Mumbai purchase ₹4,80,000",
        facts=facts,
        resolver_output=resolver_out,
        gateway=mock_gateway,
    )

    assert isinstance(decision, Decision)
    assert decision.verdict == VerdictEnum.NON_COMPLIANT
    assert "Mumbai regional approval" in decision.missing_requirements
    assert len(decision.applicable_policies) == 1
    assert decision.applicable_policies[0].section == "§2.1"
    assert "regional approval" in decision.recommended_action.lower() or "missing" in decision.recommended_action.lower()

def test_explainer_preserves_deterministic_verdict():
    """Verify that even if the LLM hallucinated a different verdict, code overrides with resolver verdict."""
    mock_gateway = MagicMock(spec=LLMGateway)

    mock_decision = Decision(
        verdict=VerdictEnum.COMPLIANT,
        reason="Looks fine to me.",
        recommended_action="Proceed immediately.",
    )
    mock_gateway.generate_structured.return_value = mock_decision

    resolver_out = ResolverOutput(
        verdict=VerdictEnum.NON_COMPLIANT,
        reason="Mandatory procurement approval unmet.",
        missing_requirements=["Procurement review"],
    )

    decision = generate_explanation(
        scenario_text="Test scenario",
        facts=ScenarioFacts(),
        resolver_output=resolver_out,
        gateway=mock_gateway,
    )

    assert decision.verdict == VerdictEnum.NON_COMPLIANT
