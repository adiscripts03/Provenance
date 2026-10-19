"""Decision and citation schemas."""

from __future__ import annotations

from enum import Enum
from pydantic import BaseModel, Field

class VerdictEnum(str, Enum):
    """The three valid verdicts per README specification."""

    COMPLIANT = "COMPLIANT"
    NON_COMPLIANT = "NON_COMPLIANT"
    REQUIRES_REVIEW = "REQUIRES_REVIEW"

class PolicyCitation(BaseModel):
    """Citation to an authoritative policy section supporting the decision."""

    doc_id: str = Field(description="Policy document ID, e.g. POL-PROC-2025-001")
    policy_title: str = Field(description="Human-readable title, e.g. Procurement Policy 2025")
    section: str = Field(description="Section number, e.g. §4.2")
    citation_text: str = Field(description="Summary or exact citation statement of the requirement")
    precedence_level: int = Field(description="Precedence level 1-5")

class Decision(BaseModel):
    """Schema-validated decision output matching README specification."""

    verdict: VerdictEnum = Field(description="Investigation verdict: COMPLIANT, NON_COMPLIANT, or REQUIRES_REVIEW")
    reason: str = Field(description="Concise rationale explaining why the action is or is not permitted")
    applicable_policies: list[PolicyCitation] = Field(default_factory=list, description="Authoritative cited policies")
    missing_requirements: list[str] = Field(default_factory=list, description="Unmet mandatory requirements or missing approvals")
    recommended_action: str = Field(description="Clear next operational steps to achieve compliance")
    flagged_documents: list[str] = Field(default_factory=list, description="doc_ids of any adversarial/injected documents detected and excluded")
    confidence_notes: str = Field(default="", description="Observations on evidence completeness or conflict resolution")
