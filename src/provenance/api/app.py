"""FastAPI application providing investigation REST endpoints.

Endpoints:
- POST /investigate: Run an end-to-end compliance investigation
- GET  /investigations: List recent investigation records
- GET  /investigations/{id}: Fetch full record by ID
- POST /investigations/{id}/override: Submit human reviewer override
- GET  /health: System health and index status check
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import List, Optional
from fastapi import FastAPI, HTTPException, status
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from provenance.audit.repository import AuditRepository
from provenance.config import settings
from provenance.graph.workflow import run_investigation
from provenance.ingestion.indexer import load_indexes
from provenance.models.audit import InvestigationRecord, ReviewerOverride
from provenance.models.decision import Decision, VerdictEnum
from provenance.models.scenario import ScenarioFacts

logger = logging.getLogger(__name__)

app = FastAPI(
    title="Provenance — AI Policy Compliance Agent",
    description="Evidence-first deterministic compliance investigator for enterprise policies.",
    version="0.1.0",
)

class InvestigateRequest(BaseModel):
    """Payload for initiating a compliance investigation."""

    scenario: str = Field(description="Business scenario in plain English", min_length=5)
    investigation_id: Optional[str] = Field(default=None, description="Optional custom investigation ID")

class InvestigateResponse(BaseModel):
    """Investigation result payload."""

    investigation_id: str
    scenario: str
    facts: ScenarioFacts
    decision: Decision
    verdict: VerdictEnum

class OverrideRequest(BaseModel):
    """Payload for submitting a reviewer override."""

    overridden_verdict: VerdictEnum
    reviewer_name: str = Field(min_length=2)
    justification: str = Field(min_length=5)

@app.post(
    "/investigate",
    response_model=InvestigateResponse,
    status_code=status.HTTP_200_OK,
    summary="Investigate a business scenario",
)
def investigate_endpoint(payload: InvestigateRequest):
    """Run full investigation workflow and return schema-validated decision."""
    try:
        final_state = run_investigation(
            scenario_text=payload.scenario,
            investigation_id=payload.investigation_id,
        )
        return InvestigateResponse(
            investigation_id=final_state["investigation_id"],
            scenario=payload.scenario,
            facts=final_state["facts"],
            decision=final_state["decision"],
            verdict=final_state["decision"].verdict,
        )
    except Exception as exc:
        logger.exception("Investigation failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Investigation workflow error: {str(exc)}",
        )

@app.get(
    "/investigations",
    response_model=list[InvestigationRecord],
    summary="List recent investigations",
)
def list_investigations_endpoint(limit: int = 50):
    """Retrieve history of compliance investigations."""
    repo = AuditRepository()
    return repo.list_investigations(limit=limit)

@app.get(
    "/investigations/{investigation_id}",
    response_model=InvestigationRecord,
    summary="Get investigation details",
)
def get_investigation_endpoint(investigation_id: str):
    """Retrieve full audit record for a specific investigation."""
    repo = AuditRepository()
    record = repo.get_investigation(investigation_id)
    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Investigation '{investigation_id}' not found.",
        )
    return record

@app.post(
    "/investigations/{investigation_id}/override",
    response_model=InvestigationRecord,
    summary="Submit human reviewer override",
)
def override_endpoint(investigation_id: str, payload: OverrideRequest):
    """Submit a justified override for an existing investigation."""
    repo = AuditRepository()
    record = repo.get_investigation(investigation_id)
    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Investigation '{investigation_id}' not found.",
        )

    override = ReviewerOverride(
        investigation_id=investigation_id,
        original_verdict=record.verdict,
        overridden_verdict=payload.overridden_verdict,
        reviewer_name=payload.reviewer_name,
        justification=payload.justification,
    )
    return repo.record_override(override)

@app.get("/health", summary="Health check")
def health_endpoint():
    """Verify application health and index readiness."""
    try:
        _, _, chunks = load_indexes()
        from provenance.llm import llm_gateway
        return {
            "status": "ok",
            "service": "provenance",
            "llm_provider": llm_gateway.provider,
            "llm_model": llm_gateway.model,
            "indexed_chunks_count": len(chunks),
            "db_path": str(settings.db_path),
        }
    except Exception as exc:
        return {
            "status": "degraded",
            "error": str(exc),
        }

UI_DIR = settings.project_root / "ui"
if UI_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(UI_DIR)), name="static")

    @app.get("/", summary="Web Application Console")
    def serve_index():
        index_file = UI_DIR / "index.html"
        if index_file.exists():
            return FileResponse(index_file)
        return {"status": "ok", "service": "provenance"}
