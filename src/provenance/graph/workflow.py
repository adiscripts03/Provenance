"""LangGraph investigation workflow implementation."""

from __future__ import annotations

import logging
from typing import Optional
from langgraph.graph import END, START, StateGraph

from provenance.agents.explainer import generate_explanation
from provenance.agents.rule_extractor import extract_requirements, verify_requirement_quote
from provenance.agents.scenario_parser import parse_scenario
from provenance.audit.repository import AuditRepository
from provenance.defense.classifier import filter_and_flag_chunks
from provenance.graph.state import InvestigationState
from provenance.retrieval.hybrid import HybridRetriever
from provenance.resolver.engine import resolve_compliance

logger = logging.getLogger(__name__)

def node_understand_scenario(state: InvestigationState) -> dict:
    """Step 1: Extract structured facts and missing information."""
    facts = parse_scenario(state["scenario_text"])
    return {"facts": facts}

def node_retrieve_evidence(state: InvestigationState) -> dict:
    """Step 2: Hybrid search + metadata/authority filtering."""
    retriever = HybridRetriever.from_saved_indexes()
    results = retriever.retrieve(
        query=state["scenario_text"],
        facts=state.get("facts"),
        top_k=6,
        filter_non_authoritative=True,
    )
    chunks = [chunk for chunk, _ in results]
    return {"retrieved_chunks": chunks}

def node_defend_injections(state: InvestigationState) -> dict:
    """Step 3: Scan retrieved chunks for adversarial injections and quarantine."""
    chunks = state.get("retrieved_chunks", [])
    safe_chunks, flagged_docs = filter_and_flag_chunks(chunks)
    return {"safe_chunks": safe_chunks, "flagged_documents": flagged_docs}

def node_extract_and_verify_rules(state: InvestigationState) -> dict:
    """Step 4 & 5: Extract candidate rules and verify exact quotes in code."""
    facts = state["facts"]
    safe_chunks = state.get("safe_chunks", [])
    extracted = extract_requirements(facts=facts, chunks=safe_chunks)
    return {"extracted_rules": extracted}

def node_resolve_precedence(state: InvestigationState) -> dict:
    """Step 6: Pure Python deterministic precedence and verdict resolver."""
    facts = state["facts"]
    rules = state.get("extracted_rules", [])
    resolver_out = resolve_compliance(facts=facts, rules=rules)
    return {"resolver_output": resolver_out}

def node_explain_decision(state: InvestigationState) -> dict:
    """Step 7: Explain findings and recommend next operational steps."""
    scenario_text = state["scenario_text"]
    facts = state["facts"]
    resolver_out = state["resolver_output"]
    flagged = state.get("flagged_documents", [])

    decision = generate_explanation(
        scenario_text=scenario_text,
        facts=facts,
        resolver_output=resolver_out,
        flagged_docs=flagged,
    )
    return {"decision": decision}

def node_audit_log(state: InvestigationState) -> dict:
    """Step 8: Persist the investigation and evidence trail to SQLite."""
    repo = AuditRepository()
    scenario_text = state["scenario_text"]
    facts = state["facts"]
    retrieved_cids = [c.chunk_id for c in state.get("retrieved_chunks", [])]
    extracted_rids = [r.rule_id for r in state.get("extracted_rules", [])]
    decision = state["decision"]
    inv_id = state.get("investigation_id")

    record = repo.save_investigation(
        scenario_text=scenario_text,
        facts=facts,
        retrieved_chunk_ids=retrieved_cids,
        extracted_rule_ids=extracted_rids,
        decision=decision,
        investigation_id=inv_id,
    )
    return {"investigation_id": record.id}

def build_investigation_graph():
    """Build and compile the LangGraph workflow."""
    workflow = StateGraph(InvestigationState)

    workflow.add_node("understand_scenario", node_understand_scenario)
    workflow.add_node("retrieve_evidence", node_retrieve_evidence)
    workflow.add_node("defend_injections", node_defend_injections)
    workflow.add_node("extract_and_verify_rules", node_extract_and_verify_rules)
    workflow.add_node("resolve_precedence", node_resolve_precedence)
    workflow.add_node("explain_decision", node_explain_decision)
    workflow.add_node("audit_log", node_audit_log)

    workflow.add_edge(START, "understand_scenario")
    workflow.add_edge("understand_scenario", "retrieve_evidence")
    workflow.add_edge("retrieve_evidence", "defend_injections")
    workflow.add_edge("defend_injections", "extract_and_verify_rules")
    workflow.add_edge("extract_and_verify_rules", "resolve_precedence")
    workflow.add_edge("resolve_precedence", "explain_decision")
    workflow.add_edge("explain_decision", "audit_log")
    workflow.add_edge("audit_log", END)

    return workflow.compile()

investigation_app = build_investigation_graph()

def run_investigation(scenario_text: str, investigation_id: Optional[str] = None) -> InvestigationState:
    """High-level runner executing the full investigation workflow on a scenario."""
    initial_state: InvestigationState = {
        "scenario_text": scenario_text,
        "facts": None,
        "retrieved_chunks": [],
        "flagged_documents": [],
        "safe_chunks": [],
        "extracted_rules": [],
        "resolver_output": None,
        "decision": None,
        "investigation_id": investigation_id,
    }
    return investigation_app.invoke(initial_state)
