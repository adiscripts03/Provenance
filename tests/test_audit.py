"""Tests for Component 9: SQLite Audit Trail and Human-in-the-Loop Override."""

from __future__ import annotations

from pathlib import Path
import pytest

from provenance.audit.repository import AuditRepository
from provenance.models.audit import ReviewerOverride
from provenance.models.decision import Decision, PolicyCitation, VerdictEnum
from provenance.models.scenario import ScenarioFacts

@pytest.fixture
def temp_audit_repo(tmp_path: Path):
    db_file = tmp_path / "test_audit.db"
    return AuditRepository(db_path=db_file)

def test_save_and_get_investigation(temp_audit_repo: AuditRepository):
    facts = ScenarioFacts(
        department="Operations",
        region="Mumbai",
        action_type="purchase",
        amount=480000.0,
    )
    decision = Decision(
        verdict=VerdictEnum.NON_COMPLIANT,
        reason="Missing approvals",
        applicable_policies=[
            PolicyCitation(
                doc_id="POL-PROC-2025-001",
                policy_title="Procurement Policy",
                section="§4.2",
                citation_text="New vendors require Procurement approval",
                precedence_level=3,
            )
        ],
        missing_requirements=["Procurement review"],
        recommended_action="Submit review",
    )

    saved = temp_audit_repo.save_investigation(
        scenario_text="Mumbai purchase ₹4,80,000",
        facts=facts,
        retrieved_chunk_ids=["POL-PROC-2025-001#§4.2"],
        extracted_rule_ids=["RULE-PROC-4.2"],
        decision=decision,
    )

    assert saved.id is not None
    assert saved.verdict == VerdictEnum.NON_COMPLIANT

    fetched = temp_audit_repo.get_investigation(saved.id)
    assert fetched is not None
    assert fetched.id == saved.id
    assert fetched.facts.region == "Mumbai"
    assert fetched.facts.amount == 480000.0
    assert fetched.verdict == VerdictEnum.NON_COMPLIANT
    assert len(fetched.decision.applicable_policies) == 1

def test_record_override(temp_audit_repo: AuditRepository):
    facts = ScenarioFacts(region="Mumbai", amount=480000.0)
    decision = Decision(
        verdict=VerdictEnum.NON_COMPLIANT,
        reason="Missing approval",
        recommended_action="Get approval",
    )
    saved = temp_audit_repo.save_investigation(
        scenario_text="Mumbai scenario",
        facts=facts,
        retrieved_chunk_ids=[],
        extracted_rule_ids=[],
        decision=decision,
    )

    override = ReviewerOverride(
        investigation_id=saved.id,
        original_verdict=VerdictEnum.NON_COMPLIANT,
        overridden_verdict=VerdictEnum.COMPLIANT,
        reviewer_name="Aditya Singh",
        justification="Executive exception approved in offline committee meeting.",
    )

    updated = temp_audit_repo.record_override(override)
    assert updated.has_override is True
    assert updated.override_verdict == VerdictEnum.COMPLIANT
    assert updated.override_reviewer == "Aditya Singh"
    assert "Executive exception" in (updated.override_justification or "")

    re_fetched = temp_audit_repo.get_investigation(saved.id)
    assert re_fetched.has_override is True
    assert re_fetched.override_verdict == VerdictEnum.COMPLIANT

def test_list_investigations(temp_audit_repo: AuditRepository):
    facts = ScenarioFacts()
    decision = Decision(verdict=VerdictEnum.REQUIRES_REVIEW, reason="Unknown", recommended_action="Review")

    for i in range(3):
        temp_audit_repo.save_investigation(
            scenario_text=f"Scenario #{i}",
            facts=facts,
            retrieved_chunk_ids=[],
            extracted_rule_ids=[],
            decision=decision,
        )

    records = temp_audit_repo.list_investigations(limit=10)
    assert len(records) == 3
