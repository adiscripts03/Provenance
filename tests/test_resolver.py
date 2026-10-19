"""Tests for Component 7: Deterministic Resolver Engine."""

from __future__ import annotations

import pytest

from provenance.models.decision import VerdictEnum
from provenance.models.policy import PrecedenceLevel
from provenance.models.rule import ExtractedRequirement
from provenance.models.scenario import ScenarioFacts
from provenance.resolver.engine import resolve_compliance

@pytest.fixture
def procurement_rule():
    return ExtractedRequirement(
        rule_id="RULE-PROC-4.2",
        chunk_id="POL-PROC-2025-001#§4.2",
        policy_title="Enterprise Procurement Policy 2025",
        section="§4.2",
        precedence_level=PrecedenceLevel.LEVEL_3_ENTERPRISE,
        exact_quote="New vendors require Procurement approval before purchase execution.",
        required_approval="Procurement",
        mandatory=True,
    )

@pytest.fixture
def mumbai_rule():
    return ExtractedRequirement(
        rule_id="RULE-MUM-2.1",
        chunk_id="POL-REG-MUM-2026-002#§2.1",
        policy_title="Mumbai Regional Logistics & Warehouse Governance Policy 2026",
        section="§2.1",
        precedence_level=PrecedenceLevel.LEVEL_2_REGIONAL_DEPT,
        exact_quote="Warehouse purchases above ₹3,00,000 require regional approval.",
        condition_threshold=300000.0,
        required_approval="Regional Director",
        mandatory=True,
    )

def test_mumbai_scenario_non_compliant(procurement_rule, mumbai_rule):
    """Canonical README example: Mumbai ₹4,80,000 purchase with only warehouse manager approval."""
    facts = ScenarioFacts(
        department="Operations",
        region="Mumbai",
        action_type="purchase",
        amount=480000.0,
        vendor_status="new",
        approvals_obtained=["warehouse manager"],
    )

    output = resolve_compliance(facts, [procurement_rule, mumbai_rule])
    assert output.verdict == VerdictEnum.NON_COMPLIANT
    assert len(output.missing_requirements) == 2
    assert any("Procurement" in mr for mr in output.missing_requirements)
    assert any("regional" in mr.lower() for mr in output.missing_requirements)

def test_mumbai_scenario_compliant(procurement_rule, mumbai_rule):
    """When both Procurement and Regional approvals are obtained, verdict must be COMPLIANT."""
    facts = ScenarioFacts(
        department="Operations",
        region="Mumbai",
        action_type="purchase",
        amount=480000.0,
        vendor_status="new",
        approvals_obtained=["warehouse manager", "Procurement Head", "Mumbai Regional Director"],
    )

    output = resolve_compliance(facts, [procurement_rule, mumbai_rule])
    assert output.verdict == VerdictEnum.COMPLIANT
    assert len(output.missing_requirements) == 0

def test_conflict_detection_forces_requires_review():
    """Conflicting rules in Level 3 must resolve to REQUIRES_REVIEW."""
    fin_rule = ExtractedRequirement(
        rule_id="RULE-FIN-5.2",
        chunk_id="POL-FIN-2025-004#§5.2",
        policy_title="CapEx Policy",
        section="§5.2",
        precedence_level=PrecedenceLevel.LEVEL_3_ENTERPRISE,
        exact_quote="must receive prior written sign-off exclusively from the Chief Financial Officer (CFO).",
        required_approval="CFO",
    )
    it_rule = ExtractedRequirement(
        rule_id="RULE-IT-4.1",
        chunk_id="POL-IT-2025-005#§4.1",
        policy_title="IT Policy",
        section="§4.1",
        precedence_level=PrecedenceLevel.LEVEL_3_ENTERPRISE,
        exact_quote="holds sole and exclusive approval authority for all IT hardware, requiring no finance or CFO pre-approval.",
        required_approval="Head of IT",
    )
    facts = ScenarioFacts(department="IT", amount=250000.0, action_type="hardware")

    output = resolve_compliance(facts, [fin_rule, it_rule])
    assert output.verdict == VerdictEnum.REQUIRES_REVIEW
    assert len(output.conflicts_detected) > 0

def test_exception_waiver_applied(procurement_rule):
    """Level 1 exception waives standard procurement onboarding."""
    blr_exception = ExtractedRequirement(
        rule_id="RULE-EXC-BLR",
        chunk_id="POL-EXC-BLR-2026-003#§2.3",
        policy_title="Bangalore Hub Exception Memo",
        section="§2.3",
        precedence_level=PrecedenceLevel.LEVEL_1_UPDATE_EXCEPTION,
        exact_quote="Bangalore automated sorting center operations are exempt from advance procurement pre-clearance for critical mechanical spares under ₹2,00,000",
        condition_threshold=200000.0,
    )
    facts = ScenarioFacts(
        department="Operations",
        region="Bangalore",
        action_type="purchase",
        amount=150000.0,
        vendor_status="new",
        approvals_obtained=["Site Manager"],
    )

    output = resolve_compliance(facts, [procurement_rule, blr_exception])
    assert len(output.exceptions_applied) > 0

    assert not any("Procurement vendor review" in mr for mr in output.missing_requirements)

def test_missing_facts_forces_requires_review():
    """Uncertainty rule: missing facts must yield REQUIRES_REVIEW."""
    facts = ScenarioFacts(missing_facts=["Purchase amount is unknown", "Vendor status is unknown"])
    output = resolve_compliance(facts, [])
    assert output.verdict == VerdictEnum.REQUIRES_REVIEW
