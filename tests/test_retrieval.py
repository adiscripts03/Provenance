"""Tests for Component 4: Hybrid Retrieval & Authority Filtering."""

from __future__ import annotations

import pytest

from provenance.models.policy import DocumentMetadata, DocumentStatus, PrecedenceLevel
from provenance.models.scenario import ScenarioFacts
from provenance.retrieval.authority import is_document_authoritative, matches_scope
from provenance.retrieval.hybrid import HybridRetriever

def test_is_document_authoritative():
    active_meta = DocumentMetadata(
        doc_id="POL-001",
        title="Active Policy",
        doc_type="policy",
        level=PrecedenceLevel.LEVEL_3_ENTERPRISE,
        owner="CPO",
        effective_date="2025-01-01",
        status=DocumentStatus.ACTIVE,
    )
    assert is_document_authoritative(active_meta) is True

    superseded_meta = active_meta.model_copy(update={"status": DocumentStatus.SUPERSEDED})
    assert is_document_authoritative(superseded_meta) is False

    expired_meta = active_meta.model_copy(update={"status": DocumentStatus.EXPIRED})
    assert is_document_authoritative(expired_meta) is False

    draft_meta = active_meta.model_copy(update={"status": DocumentStatus.DRAFT})
    assert is_document_authoritative(draft_meta) is False

    untrusted_meta = active_meta.model_copy(update={"status": DocumentStatus.UNTRUSTED})
    assert is_document_authoritative(untrusted_meta) is False

    historical_level5 = active_meta.model_copy(update={"level": PrecedenceLevel.LEVEL_5_HISTORICAL})
    assert is_document_authoritative(historical_level5) is False

def test_matches_scope():
    mumbai_facts = ScenarioFacts(
        department="Operations",
        region="Mumbai",
        action_type="purchase",
        amount=480000.0,
    )

    mumbai_policy = DocumentMetadata(
        doc_id="POL-MUM-01",
        title="Mumbai Policy",
        doc_type="regional_policy",
        level=PrecedenceLevel.LEVEL_2_REGIONAL_DEPT,
        owner="Director",
        region="Mumbai",
        effective_date="2025-01-01",
        status=DocumentStatus.ACTIVE,
    )
    assert matches_scope(mumbai_policy, mumbai_facts) is True

    delhi_policy = mumbai_policy.model_copy(update={"region": "Delhi-NCR"})
    assert matches_scope(delhi_policy, mumbai_facts) is False

    global_policy = mumbai_policy.model_copy(update={"region": "Global"})
    assert matches_scope(global_policy, mumbai_facts) is True

def test_hybrid_retriever_mumbai_scenario():
    """Verify that hybrid retrieval fetches both key policies from the README example."""
    retriever = HybridRetriever.from_saved_indexes()

    mumbai_facts = ScenarioFacts(
        department="Operations",
        region="Mumbai",
        action_type="purchase",
        amount=480000.0,
        vendor_status="new",
    )

    query = (
        "A Mumbai warehouse wants to purchase equipment worth ₹4,80,000 from a new vendor. "
        "The warehouse manager approved the purchase, but procurement has not reviewed the vendor."
    )

    results = retriever.retrieve(query=query, facts=mumbai_facts, top_k=6)
    assert len(results) > 0

    retrieved_chunk_ids = [c.chunk_id for c, _ in results]

    assert "POL-PROC-2025-001#§4.2" in retrieved_chunk_ids

    assert "POL-REG-MUM-2026-002#§2.1" in retrieved_chunk_ids

def test_superseded_policy_excluded():
    """Verify that superseded policy POL-PROC-2023-000 is excluded from authoritative results."""
    retriever = HybridRetriever.from_saved_indexes()
    query = "vendor engagement local manager up to 500000"

    results = retriever.retrieve(query=query, top_k=5, filter_non_authoritative=True)
    retrieved_doc_ids = [c.doc_id for c, _ in results]
    assert "POL-PROC-2023-000" not in retrieved_doc_ids
