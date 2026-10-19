"""Rule and requirement extraction schemas."""

from __future__ import annotations

from typing import Optional
from pydantic import BaseModel, Field

from provenance.models.policy import PrecedenceLevel

class ExtractedRequirement(BaseModel):
    """A requirement extracted from an authoritative policy chunk.

    Per AGENTS.md: Every claim must cite a retrieved chunk ID, and exact_quote
    must be verified against the chunk in deterministic code.
    """

    rule_id: str = Field(description="Unique rule ID, e.g. RULE-PROC-4.2")
    chunk_id: str = Field(description="Cited chunk ID, e.g. POL-PROC-2025-001#§4.2")
    policy_title: str = Field(description="Title of source policy document")
    section: str = Field(description="Section reference, e.g. §4.2")
    precedence_level: PrecedenceLevel = Field(description="Authority precedence level (1-5)")
    exact_quote: str = Field(description="Verbatim supporting quote from the chunk text")
    condition_threshold: Optional[float] = Field(default=None, description="Monetary threshold amount if rule specifies one")
    required_approval: Optional[str] = Field(default=None, description="Specific role/authority required (e.g. 'Procurement', 'Regional Director')")
    mandatory: bool = Field(default=True, description="Whether requirement is mandatory (True) or advisory (False)")
    scope_region: Optional[str] = Field(default=None, description="Regional scope of the rule, or 'Global' / None")
    scope_department: Optional[str] = Field(default=None, description="Department scope of the rule, or None")
    scope_action_type: Optional[str] = Field(default=None, description="Action type affected (e.g. 'purchase', 'hardware')")
    applies_to_scenario: bool = Field(default=True, description="Whether rule applies to the given scenario facts")
    verification_passed: bool = Field(default=False, description="Set True only after code verifies exact_quote in chunk")
