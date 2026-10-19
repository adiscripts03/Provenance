"""Tests for Component 11: FastAPI REST API Endpoints."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch

from provenance.api.app import app
from provenance.audit.repository import AuditRepository
from provenance.models.decision import Decision, VerdictEnum
from provenance.models.scenario import ScenarioFacts

client = TestClient(app)

def test_health_endpoint():
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["service"] == "provenance"
    assert data["indexed_chunks_count"] > 0

def test_list_investigations_endpoint():
    response = client.get("/investigations?limit=10")
    assert response.status_code == 200
    assert isinstance(response.json(), list)

def test_override_non_existent_investigation():
    response = client.post(
        "/investigations/non-existent-id/override",
        json={
            "overridden_verdict": "COMPLIANT",
            "reviewer_name": "Compliance Lead",
            "justification": "Approved due to emergency circumstances.",
        },
    )
    assert response.status_code == 404

def test_investigate_and_override_workflow():
    repo = AuditRepository()
    facts = ScenarioFacts(region="Mumbai", amount=480000.0, vendor_status="new")
    decision = Decision(
        verdict=VerdictEnum.NON_COMPLIANT,
        reason="Missing approvals",
        recommended_action="Obtain approvals",
    )
    saved = repo.save_investigation(
        scenario_text="Mumbai test purchase",
        facts=facts,
        retrieved_chunk_ids=[],
        extracted_rule_ids=[],
        decision=decision,
    )

    get_resp = client.get(f"/investigations/{saved.id}")
    assert get_resp.status_code == 200
    assert get_resp.json()["id"] == saved.id
    assert get_resp.json()["verdict"] == "NON_COMPLIANT"

    override_resp = client.post(
        f"/investigations/{saved.id}/override",
        json={
            "overridden_verdict": "COMPLIANT",
            "reviewer_name": "Auditor General",
            "justification": "Exemption ratified by Board.",
        },
    )
    assert override_resp.status_code == 200
    updated_data = override_resp.json()
    assert updated_data["has_override"] is True
    assert updated_data["override_verdict"] == "COMPLIANT"
    assert updated_data["override_reviewer"] == "Auditor General"
