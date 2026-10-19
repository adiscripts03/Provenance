"""Scenario understanding agent.

Extracts structured ScenarioFacts and explicit missing_facts list from
unstructured business scenario text.
"""

from __future__ import annotations

import logging
from typing import Optional

from provenance.llm import LLMValidationError, llm_gateway
from provenance.models.scenario import ScenarioFacts

import re

logger = logging.getLogger(__name__)

SCENARIO_PARSER_SYSTEM_PROMPT = """You are a senior compliance investigator for Logistics Company.
Your task is to extract objective, factual parameters from a business scenario into structured JSON.

CRITICAL RULES:
1. NEVER invent or assume facts. If a fact (e.g. region, amount, vendor status, approvals) is not explicitly stated, set its field to null (or empty list) and add a clear description of the missing information to the "missing_facts" list.
2. For "vendor_status", use values like "new", "unreviewed", "existing_approved", or null if unknown.
3. For "approvals_obtained", list only roles/names of individuals who explicitly approved (e.g. ["warehouse manager"]).
4. For "amount", extract pure numerical values (e.g. 480000 for ₹4,80,000).
5. Add any contextual nuances to "free_text_notes".
"""

def extract_facts_heuristic(text: str) -> ScenarioFacts:
    """Extract scenario facts deterministically for high-speed, reliable execution."""
    clean = text.lower()
    missing: list[str] = []

    amount = None
    amt_match = re.search(r"[₹$]\s*([\d,]+(?:\.\d+)?)", text)
    if amt_match:
        raw_num = amt_match.group(1).replace(",", "")
        try:
            amount = float(raw_num)
        except ValueError:
            pass
    elif "sgd" in clean:
        sgd_match = re.search(r"sgd\s*([\d,]+)", clean)
        if sgd_match:
            amount = float(sgd_match.group(1).replace(",", ""))

    region = None
    if "mumbai" in clean or "nhava sheva" in clean or "taloja" in clean:
        region = "Mumbai"
    elif "bangalore" in clean or "devanahalli" in clean:
        region = "Bangalore"
    elif "delhi" in clean or "ncr" in clean:
        region = "Delhi-NCR"
    elif "singapore" in clean:
        region = "APAC"
    elif "dallas" in clean:
        region = "North America"

    vendor_status = None
    if any(w in clean for w in ["new vendor", "new supplier", "unverified", "unregistered", "unreviewed", "has not been verified"]):
        vendor_status = "new"
    elif any(w in clean for w in ["existing approved", "approved vendor", "existing supplier"]):
        vendor_status = "existing_approved"

    approvals: list[str] = []
    if "warehouse manager" in clean or "manager approved" in clean:
        approvals.append("warehouse manager")
    if "procurement has not reviewed" not in clean and any(w in clean for w in ["head of procurement", "procurement approved", "procurement head"]):
        approvals.append("Procurement Head")
    if "was not requested" not in clean and "without regional" not in clean and any(w in clean for w in ["regional director", "regional vice president", "regional vp"]):
        approvals.append("Regional Director")
    if "site manager" in clean or "site general manager" in clean:
        approvals.append("Site Manager")
    if "cost center manager" in clean:
        approvals.append("Cost Center Manager")
    if "department head" in clean and "has not approved" not in clean and "not approved" not in clean:
        approvals.append("Department Head")
    if "head of global it" in clean or "head of it" in clean:
        approvals.append("Head of Global IT")
    if "cfo" in clean and "refused" not in clean and "without" not in clean and "was not consulted" not in clean:
        approvals.append("CFO")

    if any(w in clean for w in ["not been finalized", "not finalized", "somewhere in", "unknown"]):
        missing.append("Operational details or approvals not finalized")
    if amount is None and any(w in clean for w in ["purchase", "acquire", "procure", "order", "buy"]):
        missing.append("Purchase amount is unknown")
    if vendor_status is None and any(w in clean for w in ["vendor", "supplier"]):
        missing.append("Vendor onboarding status is unknown")

    return ScenarioFacts(
        region=region,
        amount=amount,
        vendor_status=vendor_status,
        approvals_obtained=approvals,
        action_type="purchase" if any(w in clean for w in ["purchase", "procure", "order", "buy", "acquire"]) else "operation",
        free_text_notes=text,
        missing_facts=missing,
    )

def parse_scenario(
    scenario_text: str,
    gateway: Optional[any] = None,
) -> ScenarioFacts:
    """Parse unstructured scenario text into a structured ScenarioFacts instance via Gemma 4."""
    client = gateway or llm_gateway

    user_prompt = f"""Extract the structured facts and missing information from this business scenario:

<SCENARIO>
{scenario_text.strip()}
</SCENARIO>
"""

    try:
        facts = client.generate_structured(
            user_prompt=user_prompt,
            response_model=ScenarioFacts,
            system_prompt=SCENARIO_PARSER_SYSTEM_PROMPT,
            max_retries=1,
        )
        if not facts.missing_facts:
            auto_missing: list[str] = []
            if facts.amount is None:
                auto_missing.append("Purchase amount is unknown")
            if not facts.region:
                auto_missing.append("Operational region is unspecified")
            if not facts.vendor_status:
                auto_missing.append("Vendor onboarding status is unknown")
            if auto_missing:
                facts.missing_facts = auto_missing
        return facts
    except LLMValidationError:
        return ScenarioFacts(
            free_text_notes=scenario_text,
            missing_facts=["System could not safely validate structured facts from input text"],
        )
    except Exception as exc:
        logger.warning("Gemma 4 parsing encountered exception (%s); falling back to rule heuristic.", exc)
        try:
            return extract_facts_heuristic(scenario_text)
        except Exception:
            return ScenarioFacts(
                free_text_notes=scenario_text,
                missing_facts=["System could not safely validate structured facts from input text"],
            )
