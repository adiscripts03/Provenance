"""Audit trail and human-in-the-loop schemas."""

from __future__ import annotations

from typing import Optional
from pydantic import BaseModel, Field

from provenance.models.decision import Decision, VerdictEnum
from provenance.models.scenario import ScenarioFacts

class InvestigationRecord(BaseModel):
    """Full record of a compliance investigation run."""

    id: str = Field(description="Unique UUID for the investigation")
    scenario_text: str = Field(description="Original business scenario input")
    facts: ScenarioFacts = Field(description="Extracted scenario facts")
    retrieved_chunk_ids: list[str] = Field(default_factory=list, description="IDs of all retrieved chunks")
    extracted_rule_ids: list[str] = Field(default_factory=list, description="IDs of rules extracted from chunks")
    verdict: VerdictEnum = Field(description="Deterministic verdict computed")
    reason: str = Field(description="Reasoning statement")
    decision: Decision = Field(description="Complete validated decision payload")
    created_at: str = Field(description="ISO timestamp of investigation")
    has_override: bool = Field(default=False, description="Whether human reviewer has overridden this verdict")
    override_verdict: Optional[VerdictEnum] = Field(default=None, description="Overridden verdict if applicable")
    override_reviewer: Optional[str] = Field(default=None, description="Reviewer name if overridden")
    override_justification: Optional[str] = Field(default=None, description="Reviewer justification if overridden")

class ReviewerOverride(BaseModel):
    """Reviewer override action for audit trail."""

    investigation_id: str = Field(description="Target investigation ID")
    original_verdict: VerdictEnum = Field(description="System verdict")
    overridden_verdict: VerdictEnum = Field(description="New reviewer verdict")
    reviewer_name: str = Field(description="Name or email of reviewer")
    justification: str = Field(description="Mandatory business justification for override")
