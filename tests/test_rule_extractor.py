"""Tests for Component 6: Rule Extraction and Verbatim Quote Verification."""

from __future__ import annotations

import pytest

from provenance.agents.rule_extractor import (
    extract_requirements,
    verify_requirement_quote,
)
from provenance.config import settings
from provenance.ingestion.parser import parse_document_file
from provenance.models.policy import PrecedenceLevel
from provenance.models.rule import ExtractedRequirement
from provenance.models.scenario import ScenarioFacts

def test_quote_verification_valid_and_invalid():
    proc_file = settings.kb_dir / "POL-PROC-2025-001.md"
    _, chunks = parse_document_file(proc_file)
    chunks_by_id = {c.chunk_id: c for c in chunks}

    valid_req = ExtractedRequirement(
        rule_id="RULE-PROC-4.2",
        chunk_id="POL-PROC-2025-001#§4.2",
        policy_title="Enterprise Procurement Policy 2025",
        section="§4.2",
        precedence_level=PrecedenceLevel.LEVEL_3_ENTERPRISE,
        exact_quote="New vendors require Procurement approval before purchase execution.",
        required_approval="Procurement",
        mandatory=True,
    )
    assert verify_requirement_quote(valid_req, chunks_by_id) is True

    fake_req = valid_req.model_copy(
        update={"exact_quote": "All vendors can be approved by warehouse manager with no checks."}
    )
    assert verify_requirement_quote(fake_req, chunks_by_id) is False

    bad_cid_req = valid_req.model_copy(update={"chunk_id": "NON-EXISTENT#§99.9"})
    assert verify_requirement_quote(bad_cid_req, chunks_by_id) is False

def test_extract_requirements_quote_dropping():
    """Verify that any unverified requirement is dropped by extract_requirements."""
    proc_file = settings.kb_dir / "POL-PROC-2025-001.md"
    _, chunks = parse_document_file(proc_file)
    sec_42 = [c for c in chunks if c.section_id == "§4.2"]

    facts = ScenarioFacts(
        department="Operations",
        region="Mumbai",
        action_type="purchase",
        amount=480000.0,
        vendor_status="new",
    )

    fake_rule = ExtractedRequirement(
        rule_id="RULE-FAKE",
        chunk_id="POL-PROC-2025-001#§4.2",
        policy_title="Procurement",
        section="§4.2",
        precedence_level=PrecedenceLevel.LEVEL_3_ENTERPRISE,
        exact_quote="Hallucinated text that does not exist in the policy",
        mandatory=True,
    )
    chunks_by_id = {c.chunk_id: c for c in sec_42}
    assert verify_requirement_quote(fake_rule, chunks_by_id) is False
