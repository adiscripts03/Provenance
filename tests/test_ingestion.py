"""Tests for Component 2: Ingestion & Indexing Engine."""

from __future__ import annotations

from pathlib import Path
import pytest

from provenance.config import settings
from provenance.ingestion.parser import (
    parse_all_documents,
    parse_document_file,
    parse_frontmatter_and_body,
)
from provenance.ingestion.indexer import (
    build_and_save_indexes,
    load_indexes,
    tokenize,
)
from provenance.models.policy import PrecedenceLevel, DocumentStatus

def test_parse_frontmatter_and_body():
    sample_text = """---
doc_id: "TEST-001"
title: "Test Policy"
doc_type: "policy"
level: 3
owner: "Tester"
effective_date: "2025-01-01"
status: "active"
---

# Test Policy
## §1.1 Scope
Body text here.
"""
    meta, body = parse_frontmatter_and_body(sample_text)
    assert meta["doc_id"] == "TEST-001"
    assert meta["level"] == 3
    assert "§1.1 Scope" in body

    with pytest.raises(ValueError):
        parse_frontmatter_and_body("No front matter here")

def test_parse_procurement_policy_sections():
    proc_path = settings.kb_dir / "POL-PROC-2025-001.md"
    assert proc_path.exists(), f"Missing {proc_path}"
    metadata, chunks = parse_document_file(proc_path)

    assert metadata.doc_id == "POL-PROC-2025-001"
    assert metadata.level == PrecedenceLevel.LEVEL_3_ENTERPRISE
    assert metadata.status == DocumentStatus.ACTIVE
    assert len(chunks) >= 4

    chunk_ids = [c.chunk_id for c in chunks]
    assert "POL-PROC-2025-001#§4.2" in chunk_ids
    assert "POL-PROC-2025-001#§2.1" in chunk_ids

    sec_42 = next(c for c in chunks if c.section_id == "§4.2")
    assert sec_42.chunk_id == "POL-PROC-2025-001#§4.2"
    assert "New vendors require Procurement approval before purchase execution" in sec_42.content
    assert sec_42.metadata.doc_id == "POL-PROC-2025-001"

def test_parse_all_documents():
    all_metadata, all_chunks = parse_all_documents(settings.kb_dir)
    assert len(all_metadata) >= 25
    assert len(all_chunks) >= 50

    chunk_ids = [c.chunk_id for c in all_chunks]
    assert len(chunk_ids) == len(set(chunk_ids)), "Duplicate chunk IDs found!"

    for c in all_chunks:
        assert "#" in c.chunk_id
        doc_part, sec_part = c.chunk_id.split("#", 1)
        assert doc_part == c.doc_id
        assert sec_part == c.section_id

def test_tokenizer():
    tokens = tokenize("Procurement approval for ₹4,80,000 in Mumbai!")
    assert "procurement" in tokens
    assert "approval" in tokens
    assert "mumbai" in tokens
    assert "4" in tokens or "480000" in "".join(tokens)

def test_build_and_search_indexes(tmp_path: Path):

    bm25, vector, chunks = build_and_save_indexes(
        kb_dir=settings.kb_dir,
        indexes_dir=tmp_path,
        embedding_model_name=settings.embedding_model,
    )
    assert len(chunks) >= 50

    bm25_results = bm25.search("New vendors require Procurement approval", top_k=5)
    assert len(bm25_results) > 0
    top_bm25_chunk, top_bm25_score = bm25_results[0]
    assert top_bm25_score > 0

    top_ids = [c.chunk_id for c, _ in bm25_results[:3]]
    assert "POL-PROC-2025-001#§4.2" in top_ids

    vector_results = vector.search("Mumbai warehouse purchases above 300000 regional approval", top_k=5)
    assert len(vector_results) > 0
    top_vec_chunk, top_vec_score = vector_results[0]
    assert top_vec_score > 0
    vec_ids = [c.chunk_id for c, _ in vector_results[:3]]
    assert "POL-REG-MUM-2026-002#§2.1" in vec_ids

    loaded_bm25, loaded_vector, loaded_chunks = load_indexes(
        indexes_dir=tmp_path,
        embedding_model_name=settings.embedding_model,
    )
    assert len(loaded_chunks) == len(chunks)
    re_results = loaded_bm25.search("Procurement approval", top_k=3)
    assert len(re_results) > 0
