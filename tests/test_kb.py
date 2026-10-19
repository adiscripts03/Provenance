"""Tests for Component 1: Synthetic Knowledge Base."""

from __future__ import annotations

import json
import re
from pathlib import Path
import pytest
import yaml

KB_DIR = Path("data/kb")
MANIFEST_PATH = Path("eval/test_injected_manifest.json")

REQUIRED_FRONTMATTER_FIELDS = {
    "doc_id",
    "title",
    "doc_type",
    "level",
    "owner",
    "department",
    "region",
    "legal_entity",
    "effective_date",
    "expiry_date",
    "status",
    "supersedes",
}

VALID_STATUSES = {"active", "superseded", "draft", "expired", "untrusted"}

def load_all_docs() -> list[tuple[Path, dict, str]]:
    docs = []
    assert KB_DIR.exists(), f"{KB_DIR} does not exist"
    for file_path in KB_DIR.glob("*.md"):
        content = file_path.read_text(encoding="utf-8")
        parts = content.split("---", 2)
        assert len(parts) >= 3, f"Document {file_path.name} missing front matter delimiters"
        front_matter = yaml.safe_load(parts[1])
        body = parts[2]
        docs.append((file_path, front_matter, body))
    return docs

def test_kb_document_count():
    docs = load_all_docs()
    assert len(docs) >= 25, f"Expected at least 25 documents, found {len(docs)}"

def test_frontmatter_schema_and_precedence():
    docs = load_all_docs()
    for path, meta, _ in docs:
        missing = REQUIRED_FRONTMATTER_FIELDS - set(meta.keys())
        assert not missing, f"{path.name} is missing fields: {missing}"
        assert meta["level"] in {1, 2, 3, 4, 5}, f"{path.name} has invalid level: {meta['level']}"
        assert meta["status"] in VALID_STATUSES, f"{path.name} has invalid status: {meta['status']}"
        assert meta["doc_id"] == path.stem, f"doc_id '{meta['doc_id']}' does not match file stem '{path.stem}'"

def test_section_numbering_present():
    docs = load_all_docs()
    section_pattern = re.compile(r"§\d+\.\d+")
    for path, _, body in docs:
        sections = section_pattern.findall(body)
        assert len(sections) >= 1, f"{path.name} does not contain any section numbered like §X.Y"

def test_readme_example_documents_present():
    docs_by_id = {meta["doc_id"]: (meta, body) for _, meta, body in load_all_docs()}

    assert "POL-PROC-2025-001" in docs_by_id
    meta, body = docs_by_id["POL-PROC-2025-001"]
    assert meta["status"] == "active"
    assert "§4.2" in body
    assert "New vendors require Procurement approval before purchase execution" in body

    assert "POL-REG-MUM-2026-002" in docs_by_id
    meta, body = docs_by_id["POL-REG-MUM-2026-002"]
    assert meta["status"] == "active"
    assert meta["region"] == "Mumbai"
    assert "§2.1" in body
    assert "Warehouse purchases above ₹3,00,000 require regional approval" in body

def test_superseded_policy_and_conflicts():
    docs_by_id = {meta["doc_id"]: (meta, body) for _, meta, body in load_all_docs()}

    assert "POL-PROC-2023-000" in docs_by_id
    old_meta, _ = docs_by_id["POL-PROC-2023-000"]
    assert old_meta["status"] == "superseded"
    new_meta, _ = docs_by_id["POL-PROC-2025-001"]
    assert new_meta["supersedes"] == "POL-PROC-2023-000"

    assert "POL-FIN-2025-004" in docs_by_id
    assert "POL-IT-2025-005" in docs_by_id
    fin_meta, fin_body = docs_by_id["POL-FIN-2025-004"]
    it_meta, it_body = docs_by_id["POL-IT-2025-005"]
    assert fin_meta["level"] == 3
    assert it_meta["level"] == 3
    assert "CFO" in fin_body and "exceeding ₹1,00,000" in fin_body
    assert "sole and exclusive approval authority" in it_body and "₹10,00,000" in it_body

def test_exceptions_and_threshold_table():
    docs_by_id = {meta["doc_id"]: (meta, body) for _, meta, body in load_all_docs()}

    assert "POL-EXC-BLR-2026-003" in docs_by_id
    blr_meta, blr_body = docs_by_id["POL-EXC-BLR-2026-003"]
    assert blr_meta["level"] == 1
    assert blr_meta["status"] == "active"
    assert "exempt from advance procurement pre-clearance" in blr_body

    _, proc_body = docs_by_id["POL-PROC-2025-001"]
    assert "§3.2 Spend Authorization Thresholds" in proc_body
    assert "Up to ₹50,000" in proc_body
    assert "₹50,001 to ₹3,00,000" in proc_body
    assert "₹3,00,001 to ₹10,00,000" in proc_body
    assert "Above ₹10,00,000" in proc_body

def test_distractor_documents():
    docs_by_id = {meta["doc_id"]: (meta, body) for _, meta, body in load_all_docs()}
    assert "POL-DIST-CAF-2025-016" in docs_by_id
    assert "POL-DIST-ERG-2025-017" in docs_by_id
    assert "POL-DIST-HOL-2026-018" in docs_by_id

def test_prompt_injection_manifest():
    assert MANIFEST_PATH.exists(), f"Missing hidden manifest at {MANIFEST_PATH}"
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    injected_ids = manifest.get("injected_doc_ids", [])
    assert len(injected_ids) >= 3, f"Expected at least 3 injected docs in manifest, found {len(injected_ids)}"

    docs_by_id = {meta["doc_id"]: (meta, body) for _, meta, body in load_all_docs()}
    for doc_id in injected_ids:
        assert doc_id in docs_by_id, f"Injected doc {doc_id} not found in KB"
        meta, body = docs_by_id[doc_id]

        assert "injected" not in meta
        assert "is_injected" not in meta

        lower_body = body.lower()
        assert (
            "system override" in lower_body
            or "ignore previous" in lower_body
            or "ignore all" in lower_body
            or "jailbreak" in lower_body
            or "exemption mode" in lower_body
        )
