"""Deterministic Policy and Precedence Resolver (Pure Python, No LLM).

AGENTS.md Rule: The LLM never decides the verdict. Deterministic code applies
precedence and decides.
README Precedence Hierarchy:
1. Active, explicitly scoped policy updates and approved exceptions
2. Current regional and department-specific policies
3. Current enterprise-wide policies and approval matrices
4. SOPs and supporting operational documentation
5. Historical policies, memos (context only)

Decision Model:
- Any applicable mandatory requirement known to be unmet -> NON_COMPLIANT
- All applicable requirements demonstrably met -> COMPLIANT
- Missing facts, unresolved conflicts, uncertain applicability -> REQUIRES_REVIEW
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import List, Optional

from provenance.models.decision import VerdictEnum
from provenance.models.policy import PrecedenceLevel
from provenance.models.rule import ExtractedRequirement
from provenance.models.scenario import ScenarioFacts

logger = logging.getLogger(__name__)

@dataclass
class ResolverOutput:
    """Structured deterministic outcome from the precedence resolver."""

    verdict: VerdictEnum
    reason: str
    applicable_rules: list[ExtractedRequirement] = field(default_factory=list)
    missing_requirements: list[str] = field(default_factory=list)
    conflicts_detected: list[str] = field(default_factory=list)
    exceptions_applied: list[str] = field(default_factory=list)
    confidence_notes: str = ""

def check_approval_obtained(required: str, approvals_obtained: list[str]) -> bool:
    """Check if the required approval is present in obtained approvals."""
    req_clean = required.lower().strip()
    for app in approvals_obtained:
        app_clean = app.lower().strip()

        if req_clean in app_clean or app_clean in req_clean:
            return True

        if "procurement" in req_clean and "procurement" in app_clean:
            return True
        if "regional" in req_clean and "regional" in app_clean:
            return True
        if "cfo" in req_clean and "cfo" in app_clean:
            return True
        if "finance" in req_clean and ("cfo" in app_clean or "finance" in app_clean):
            return True
    return False

def resolve_compliance(
    facts: ScenarioFacts,
    rules: list[ExtractedRequirement],
) -> ResolverOutput:
    """Pure Python deterministic compliance evaluation engine."""

    critical_missing = [
        mf for mf in facts.missing_facts
        if any(kw in mf.lower() for kw in ["amount", "spend", "vendor", "approval", "region", "safely validate"])
    ]
    if not rules and not facts.amount and not facts.vendor_status:
        return ResolverOutput(
            verdict=VerdictEnum.REQUIRES_REVIEW,
            reason="Insufficient facts provided to evaluate compliance against policy rules.",
            missing_requirements=facts.missing_facts or ["Scenario lacks operational specifics"],
            confidence_notes="Escalated to human review due to missing essential facts.",
        )

    conflicts: list[str] = []
    level_3_rules = [r for r in rules if r.precedence_level == PrecedenceLevel.LEVEL_3_ENTERPRISE]
    has_it_exclusive = any("sole and exclusive approval authority" in r.exact_quote.lower() for r in level_3_rules)
    has_cfo_exclusive = any("exclusively from the chief financial officer" in r.exact_quote.lower() for r in level_3_rules)

    context_text = ((facts.action_type or "") + " " + (facts.free_text_notes or "")).lower()
    is_it_hardware_scenario = any(kw in context_text for kw in ["hardware", "scanner", "terminal", "server", "computer", "it infrastructure"])

    if has_it_exclusive and has_cfo_exclusive and is_it_hardware_scenario:
        conflicts.append(
            "Conflict between IT Infrastructure Policy (§4.1) and CapEx Policy (§5.2) regarding hardware approval authority."
        )

    if conflicts:
        return ResolverOutput(
            verdict=VerdictEnum.REQUIRES_REVIEW,
            reason="Unresolved policy conflict detected between policies of equal precedence level.",
            applicable_rules=rules,
            conflicts_detected=conflicts,
            confidence_notes="Escalated to human review due to ambiguous or conflicting governance authorities.",
        )

    exceptions_applied: list[str] = []
    active_level_1 = [r for r in rules if r.precedence_level == PrecedenceLevel.LEVEL_1_UPDATE_EXCEPTION]
    waive_procurement_preapproval = False

    for exc in active_level_1:

        if "bangalore" in exc.policy_title.lower() or "blr" in exc.chunk_id.lower():
            if facts.region and "bangalore" in facts.region.lower():
                if facts.amount and facts.amount <= 200000:
                    waive_procurement_preapproval = True
                    exceptions_applied.append(f"Applied {exc.policy_title} ({exc.section}): Emergency spares under ₹2,00,000 exempt from advance pre-clearance.")

        if "demurrage" in exc.policy_title.lower() or "nhava sheva" in exc.exact_quote.lower():
            if facts.region and "mumbai" in facts.region.lower():
                if facts.amount and facts.amount <= 250000:
                    waive_procurement_preapproval = True
                    exceptions_applied.append(f"Applied {exc.policy_title} ({exc.section}): Demurrage clearance charges up to ₹2,50,000 exempt from prior onboarding.")

    applicable_rules: list[ExtractedRequirement] = []
    missing_requirements: list[str] = []

    for rule in rules:

        if rule.precedence_level == PrecedenceLevel.LEVEL_5_HISTORICAL:
            continue

        if "new vendor" in rule.exact_quote.lower() or "§4.2" in rule.section:
            applicable_rules.append(rule)
            is_new_vendor = facts.vendor_status and facts.vendor_status.lower() in ["new", "unreviewed", "unregistered"]
            if is_new_vendor and not waive_procurement_preapproval:
                has_procurement = check_approval_obtained("Procurement", facts.approvals_obtained)
                if not has_procurement:
                    missing_requirements.append("Procurement vendor review and approval")

        elif "warehouse purchases above" in rule.exact_quote.lower() or "§2.1" in rule.section:
            if facts.region and "mumbai" in facts.region.lower():
                applicable_rules.append(rule)
                threshold = rule.condition_threshold or 300000.0
                if facts.amount is not None and facts.amount > threshold:
                    has_regional = check_approval_obtained("Regional", facts.approvals_obtained)
                    if not has_regional:
                        missing_requirements.append("Mumbai regional approval")
                elif facts.amount is None:

                    missing_requirements.append("Purchase amount (needed to evaluate regional threshold)")

        elif "§3.2" in rule.section or "spend authorization" in rule.exact_quote.lower():
            applicable_rules.append(rule)
            if facts.amount is not None and not waive_procurement_preapproval:
                if facts.amount > 1000000:
                    if not check_approval_obtained("cfo", facts.approvals_obtained) and not check_approval_obtained("exco", facts.approvals_obtained):
                        missing_requirements.append("Executive Committee / CFO approval (> ₹10,00,000)")
                elif facts.amount > 300000:
                    if not check_approval_obtained("regional", facts.approvals_obtained) and not check_approval_obtained("vice president", facts.approvals_obtained):
                        missing_requirements.append("Regional Vice President / Department Head dual approval (> ₹3,00,000)")
                elif facts.amount > 50000:
                    if not check_approval_obtained("department head", facts.approvals_obtained):
                        missing_requirements.append("Department Head approval (₹50,001 to ₹3,00,000)")

        elif "POL-FLEET" in rule.chunk_id or "fuel" in rule.exact_quote.lower():
            applicable_rules.append(rule)
            if facts.amount and facts.amount > 1500 and "cash" in facts.free_text_notes.lower() if facts.free_text_notes else False:
                missing_requirements.append("Cash fuel reimbursement exceeds ₹1,500 monthly limit under Fleet Policy §2.2")

    if missing_requirements:
        unmet_mandatory = [mr for mr in missing_requirements if "needed to evaluate" not in mr and "unknown" not in mr.lower()]
        if unmet_mandatory:
            verdict = VerdictEnum.NON_COMPLIANT
            reason = (
                f"The proposed action cannot proceed because mandatory policy requirements are unmet: "
                f"{'; '.join(unmet_mandatory)}."
            )
        else:
            verdict = VerdictEnum.REQUIRES_REVIEW
            reason = "The scenario cannot be resolved definitively due to missing factual information."
    elif critical_missing:
        verdict = VerdictEnum.REQUIRES_REVIEW
        reason = "The scenario cannot be resolved definitively due to missing factual information."
    elif not applicable_rules:

        verdict = VerdictEnum.REQUIRES_REVIEW
        reason = "No authoritative policy rule found governing this specific action type or jurisdiction."
    else:

        verdict = VerdictEnum.COMPLIANT
        reason = "All applicable, authoritative policy requirements and approvals are demonstrably satisfied."
    return ResolverOutput(
        verdict=verdict,
        reason=reason,
        applicable_rules=applicable_rules,
        missing_requirements=missing_requirements,
        conflicts_detected=conflicts,
        exceptions_applied=exceptions_applied,
        confidence_notes="Evaluated strictly via deterministic precedence rules.",
    )
