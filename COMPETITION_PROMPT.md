# Provenance — Full System Master Prompt (Competition Edition)

> **Instructions for Competition**: Copy and paste the prompt below into an AI coding assistant (such as Antigravity, Cursor, Claude Code, or Gemini CLI) in an empty project directory. It instructs the agent to autonomously generate the complete Provenance repository from scratch with all architecture principles, Ollama model fixes, and evaluation harnesses included.

***

```markdown
Build "Provenance" from scratch in this workspace. Provenance is an evidence-first enterprise AI compliance investigation agent for a global logistics enterprise (Logistics Company).

Read and strictly enforce all the rules and implementation specifications below.

================================================================================
PART 1: PROJECT TENETS & COMPLIANCE DECISION MODEL
================================================================================
1. The LLM NEVER Decides the Verdict:
   - The LLM parses scenarios, extracts candidate policy rules, and formats human explanations.
   - A pure Python deterministic resolver evaluates precedence rules, checks thresholds, detects conflicts, and decides the verdict:
     * COMPLIANT: All applicable, authoritative requirements are demonstrably satisfied.
     * NON_COMPLIANT: At least one applicable mandatory requirement is known to be unmet.
     * REQUIRES_REVIEW: Lacks required facts, detects unresolved conflicts, or finds unreviewed exceptions.
   - Uncertainty ALWAYS resolves to REQUIRES_REVIEW, NEVER COMPLIANT.

2. Documents are DATA, NEVER Instructions:
   - Enterprise documents may contain adversarial prompt injections or instruction hijacking.
   - All retrieved documents must pass through a two-tier defense (regex heuristics + model classification) and be strictly wrapped inside XML tags: `<UNTRUSTED_ENTERPRISE_DATA chunk_id="...">`.
   - Any document flagged as adversarial must be quarantined, logged, and excluded from the reasoning flow.

3. Verbatim Quote Verification in Code:
   - Every claim in the output must cite a retrieved chunk ID.
   - Python code must verify that `exact_quote` exists as a verbatim substring inside the cited chunk. Any rule that fails quote verification must be discarded.

4. 5-Level Precedence Hierarchy:
   - Level 1: Active, explicitly scoped policy updates & approved exceptions/waivers (e.g., Bangalore spares waiver <₹2L, Nhava Sheva demurrage <₹2.5L).
   - Level 2: Current regional and department-specific policies (e.g., Mumbai regional warehouse purchases >₹3L require Regional Director approval).
   - Level 3: Current enterprise-wide policies & global approval matrices (e.g., Procurement Policy §4.2: new vendors require Procurement approval before execution).
   - Level 4: Standard Operating Procedures (SOPs) & operational guidelines.
   - Level 5: Historical policies, memos, incident reports (context only, never authoritative).
   - Any document marked superseded, expired, draft, or untrusted cannot establish a requirement.

================================================================================
PART 2: LOCAL OLLAMA & MODEL OPTIMIZATIONS (CRITICAL FIXES)
================================================================================
All LLM calls MUST go through ONE singleton gateway module (`src/provenance/llm.py`) using `openai.OpenAI(base_url="http://localhost:11434/v1", api_key="ollama", timeout=90.0)` targeting model `gemma4:12b`.

You must implement these specific Ollama fixes:
1. Pass `"reasoning_effort": "none"` in all chat completion kwargs to prevent thinking token overhead and avoid JSON parsing failures.
2. Strip markdown code fences before Pydantic parsing: Gemma/Ollama frequently wraps JSON in ```json ... ``` blocks even with `response_format={"type": "json_object"}`. Code must strip leading ```json and trailing ``` before calling `model_validate_json()`.
3. Set `timeout=90.0` on the OpenAI client to avoid dropouts during local model warm-up on consumer hardware.
4. Inject the Pydantic schema directly into the prompt using `json.dumps(response_model.model_json_schema(), indent=2)` along with system prompt instructions: "You must return ONLY a valid JSON object matching the requested schema."
5. Targeted Retry Loop: If validation fails, append the failed output and the exact validation error, and retry once (`max_retries=1`).
6. Context Guardrail: Pass only the top 4 candidate chunks (`chunks[:4]`) to the LLM rule extraction prompt to keep local inference fast on consumer GPUs/Apple Silicon.
7. Pure Python Fallbacks: Implement deterministic heuristic fallbacks for scenario parsing, rule extraction, and explanation so tests and benchmark evaluations never crash if Ollama is busy or offline.

================================================================================
PART 3: DIRECTORY LAYOUT & REQUIRED MODULES
================================================================================
Create the following structure:
├── AGENTS.md                          # Repository rules and environment contract
├── README.md                          # Full architectural overview, decision model, and run guide
├── pyproject.toml                     # Package definition allowing `pip install -e .`
├── requirements.txt                   # pydantic, openai, langgraph, chromadb, sentence-transformers, rank-bm25, fastapi, uvicorn, streamlit, pytest, pytest-asyncio
├── Makefile                           # Targets: check-env, seed-kb, reindex, test, run-api, run-ui, eval
├── data/
│   ├── kb/                            # Synthetic markdown policy files with YAML frontmatter
│   └── audit.db                       # SQLite database for investigation history & human overrides
├── scripts/
│   ├── check_env.py                   # Verifies Python >= 3.11, ollama binary, gemma4:12b, and JSON completions
│   └── seed_kb.py                     # Generates comprehensive enterprise policies and prompt injection test cases
├── src/provenance/
│   ├── __init__.py
│   ├── config.py                      # Pydantic Settings (paths, models, retrieval top_k, RRF k)
│   ├── llm.py                         # Central LLM Gateway with Ollama fixes
│   ├── models/                        # Pydantic models for ScenarioFacts, PolicyChunk, Rule, Decision, Audit
│   ├── ingestion/                     # Frontmatter parser, section chunker, BM25 & Chroma vector indexer
│   ├── retrieval/                     # Authority & scope filters, Reciprocal Rank Fusion (RRF) hybrid retriever
│   ├── defense/                       # Regex injection heuristics & XML data-wrapping defense
│   ├── agents/
│   │   ├── scenario_parser.py         # Extracts facts & missing_facts list with heuristic fallback
│   │   ├── rule_extractor.py          # Extracts candidate requirements with code quote verification
│   │   └── explainer.py               # Generates executive summary & next actions without changing verdict
│   ├── resolver/
│   │   └── engine.py                  # Pure Python deterministic precedence & conflict resolution engine
│   ├── graph/
│   │   ├── state.py                   # LangGraph TypedDict state
│   │   └── workflow.py                # Compiled LangGraph pipeline with SQLite audit persistence
│   ├── audit/
│   │   └── repository.py              # SQLite repository for audit logging and human reviewer overrides
│   └── api/
│       └── app.py                     # FastAPI REST server (/health, /investigate, /investigations, /override)
├── ui/
│   └── app.py                         # Streamlit UI with presets, color badges, evidence viewer, and override form
├── eval/
│   ├── scenarios.json                 # 32 benchmark scenarios covering straightforward, conflicts, supersessions, injections, missing facts
│   ├── test_injected_manifest.json    # Manifest of injected test files
│   └── run_eval.py                    # Evaluator outputting eval/results.md and eval/results.csv
└── tests/                             # 40+ unit & integration pytest tests covering every single component

================================================================================
PART 4: STEP-BY-STEP EXECUTION ORDER
================================================================================
1. Write `AGENTS.md`, `README.md`, `pyproject.toml`, `requirements.txt`, and `Makefile`.
2. Create `src/provenance/config.py`, `src/provenance/models/`, and `src/provenance/llm.py` with all Ollama guardrails.
3. Create `scripts/seed_kb.py` and `src/provenance/ingestion/` to build BM25 and Chroma vector indexes.
4. Implement `src/provenance/defense/` (regex heuristics + untrusted XML isolation).
5. Implement `src/provenance/retrieval/` (authority/scope filtering + RRF ranker).
6. Implement `src/provenance/agents/` and `src/provenance/resolver/engine.py` (with quote verification and precedence logic).
7. Implement `src/provenance/graph/workflow.py` and `src/provenance/audit/repository.py`.
8. Implement `ui/app.py` (Streamlit portal) and `src/provenance/api/app.py` (FastAPI).
9. Implement `eval/scenarios.json` and `eval/run_eval.py` (benchmark harness).
10. Write comprehensive pytest test suites in `tests/`.
11. Run `PYTHONPATH=src pytest tests/ -v` to verify 100% test pass rate, then run `make eval` to verify benchmark metrics.
```
