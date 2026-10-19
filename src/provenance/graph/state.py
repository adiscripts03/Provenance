"""Investigation state definition for LangGraph pipeline."""

from __future__ import annotations

from typing import List, Optional, TypedDict

from provenance.models.decision import Decision
from provenance.models.policy import PolicyChunk
from provenance.models.rule import ExtractedRequirement
from provenance.models.scenario import ScenarioFacts
from provenance.resolver.engine import ResolverOutput

class InvestigationState(TypedDict):
    """Complete typed state passing through the LangGraph investigation workflow."""

    scenario_text: str
    facts: Optional[ScenarioFacts]
    retrieved_chunks: list[PolicyChunk]
    flagged_documents: list[str]
    safe_chunks: list[PolicyChunk]
    extracted_rules: list[ExtractedRequirement]
    resolver_output: Optional[ResolverOutput]
    decision: Optional[Decision]
    investigation_id: Optional[str]
