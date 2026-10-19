"""Explanation agent for generating human-readable compliance decisions.

AGENTS.md Rule: The LLM never decides the verdict. Deterministic code applies
precedence and decides. The LLM writes the reasoning summary and recommended
next action from the resolver's structured output only.
"""

from __future__ import annotations

import logging
from typing import List, Optional

from provenance.llm import LLMGateway, llm_gateway
from provenance.models.decision import Decision, PolicyCitation, VerdictEnum
from provenance.models.scenario import ScenarioFacts
from provenance.resolver.engine import ResolverOutput

logger = logging.getLogger(__name__)

EXPLAINER_SYSTEM_PROMPT = """You are a senior corporate compliance officer for Logistics Company.
Your task is to draft a professional, executive-ready compliance decision document based STRICTLY
on the structured findings provided by the deterministic compliance resolver.

RULES:
1. Do NOT alter the verdict. The verdict is already decided deterministically.
2. Formulate a concise, factual "reason" explaining why the action is or is not permitted based on the applicable rules.
3. Formulate a practical, step-by-step "recommended_action" explaining what operational steps the team should take next.
4. Populate "applicable_policies" with precise citations referencing the policies evaluated by the resolver.
"""

def formulate_recommended_action(resolver_output: ResolverOutput) -> str:
    """Formulate actionable operational next steps based on resolver findings."""
    missing = resolver_output.missing_requirements
    if not missing:
        if resolver_output.verdict == VerdictEnum.COMPLIANT:
            return "Proceed with purchase and operational execution adhering to standard documentation."
        if resolver_output.conflicts_detected:
            return "Submit request to Governance Committee and Legal to resolve conflicting policy mandates."
        return "Operational review complete. Proceed in accordance with applicable policy guidelines."

    actions = []
    for req in missing:
        r_low = req.lower()
        if "procurement" in r_low:
            actions.append("submit the vendor onboarding and purchase request to Procurement")
        elif "regional" in r_low:
            actions.append("obtain Mumbai regional approval" if "mumbai" in r_low else "obtain regional approval")
        elif "cfo" in r_low:
            actions.append("obtain written CFO sign-off")
        elif "it" in r_low:
            actions.append("obtain Head of Global IT approval")
        elif "manager" in r_low:
            actions.append("obtain cost center / warehouse manager authorization")
        else:
            actions.append(f"satisfy requirement: {req}")

    if len(actions) == 1:
        return f"{actions[0].capitalize()} before issuing commitment."
    elif len(actions) == 2:
        return f"{actions[0].capitalize()}, then {actions[1]} before issuing a purchase order."
    else:
        return f"Complete the following before commitment: {'; '.join(actions)}."

def generate_explanation(
    scenario_text: str,
    facts: ScenarioFacts,
    resolver_output: ResolverOutput,
    flagged_docs: Optional[list[str]] = None,
    gateway: Optional[LLMGateway] = None,
) -> Decision:
    """Generate final schema-validated Decision payload from deterministic resolver output."""
    flagged = flagged_docs or []

    default_citations: list[PolicyCitation] = []
    for r in resolver_output.applicable_rules:
        default_citations.append(
            PolicyCitation(
                doc_id=r.chunk_id.split("#")[0],
                policy_title=r.policy_title,
                section=r.section,
                citation_text=r.exact_quote,
                precedence_level=int(r.precedence_level),
            )
        )

    client = gateway or llm_gateway
    rule_summaries = [
        f"- {r.policy_title}, {r.section} (Level {int(r.precedence_level)}): \"{r.exact_quote}\""
        for r in resolver_output.applicable_rules
    ]

    user_prompt = f"""Scenario Text:
"{scenario_text}"

Deterministic Findings:
- Fixed Verdict: {resolver_output.verdict.value}
- Preliminary Reason: {resolver_output.reason}
- Applicable Policy Rules:
{chr(10).join(rule_summaries) if rule_summaries else "None"}
- Missing Requirements: {resolver_output.missing_requirements}
- Conflicts Detected: {resolver_output.conflicts_detected}
- Exceptions Applied: {resolver_output.exceptions_applied}
- Flagged Adversarial Docs: {flagged}

Generate a complete, professional Decision object strictly reflecting the verdict '{resolver_output.verdict.value}'.
"""

    try:
        decision = client.generate_structured(
            user_prompt=user_prompt,
            response_model=Decision,
            system_prompt=EXPLAINER_SYSTEM_PROMPT,
            max_retries=1,
        )

        decision.verdict = resolver_output.verdict
        decision.flagged_documents = flagged
        if not decision.applicable_policies and default_citations:
            decision.applicable_policies = default_citations
        return decision

    except Exception as exc:
        logger.error("Failed to generate explanation via LLM: %s. Using deterministic fallback.", exc)
        rec_action = formulate_recommended_action(resolver_output)
        return Decision(
            verdict=resolver_output.verdict,
            reason=resolver_output.reason,
            applicable_policies=default_citations,
            missing_requirements=resolver_output.missing_requirements,
            recommended_action=rec_action,
            flagged_documents=flagged,
            confidence_notes=resolver_output.confidence_notes or "Generated via deterministic fallback.",
        )
