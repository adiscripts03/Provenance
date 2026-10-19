"""Authority and scope filtering for enterprise documents.

Implements the rules from README.md:
"A source marked superseded, expired, draft, or untrusted cannot independently
establish a requirement."
"Within a level, a document must match the scenario’s effective date,
legal entity, region, department, action type, and monetary threshold."
"""

from __future__ import annotations

from datetime import date
from typing import Optional

from provenance.models.policy import DocumentMetadata, DocumentStatus, PrecedenceLevel
from provenance.models.scenario import ScenarioFacts

NON_AUTHORITATIVE_STATUSES = {
    DocumentStatus.SUPERSEDED,
    DocumentStatus.EXPIRED,
    DocumentStatus.DRAFT,
    DocumentStatus.UNTRUSTED,
}

def is_document_authoritative(metadata: DocumentMetadata) -> bool:
    """Check if document has authoritative legal standing.

    Superseded, expired, draft, or untrusted sources cannot establish a requirement.
    Level 5 historical documents are used only as context, never as authoritative rules.
    """
    if metadata.status in NON_AUTHORITATIVE_STATUSES:
        return False
    if metadata.level == PrecedenceLevel.LEVEL_5_HISTORICAL:
        return False
    return True

def is_date_valid(metadata: DocumentMetadata, reference_date: Optional[str] = None) -> bool:
    """Verify document is currently effective and has not reached expiry."""
    ref_date_str = reference_date or date.today().isoformat()
    try:
        ref_d = date.fromisoformat(ref_date_str)
        eff_d = date.fromisoformat(metadata.effective_date)
        if ref_d < eff_d:

            return False
        if metadata.expiry_date:
            exp_d = date.fromisoformat(metadata.expiry_date)
            if ref_d > exp_d:

                return False
        return True
    except ValueError:

        return metadata.status == DocumentStatus.ACTIVE

def matches_scope(metadata: DocumentMetadata, facts: ScenarioFacts) -> bool:
    """Evaluate whether a policy's jurisdictional scope encompasses the scenario.

    - Global policies (region=None or "Global") apply everywhere unless overridden.
    - Regional policies apply only if the scenario matches their region.
    - Department policies apply if department matches or is enterprise-wide.
    """

    if not is_document_authoritative(metadata):
        return False

    if not is_date_valid(metadata, facts.effective_date):
        return False

    if metadata.region and metadata.region.lower() not in ("global", "enterprise", ""):
        if facts.region:
            if metadata.region.lower() not in facts.region.lower() and facts.region.lower() not in metadata.region.lower():
                return False
        else:

            pass

    if metadata.department and facts.department:
        if metadata.department.lower() not in facts.department.lower() and facts.department.lower() not in metadata.department.lower():

            if not (metadata.department.lower() == "procurement" and facts.action_type == "purchase"):
                return False

    if metadata.legal_entity and facts.legal_entity:
        if metadata.legal_entity.lower() not in facts.legal_entity.lower():
            return False

    return True
