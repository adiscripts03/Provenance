.PHONY: help check-env seed-kb test run-api run-ui eval

VENV_PYTHON = .venv/bin/python
VENV_PYTEST = .venv/bin/pytest
VENV_STREAMLIT = .venv/bin/streamlit
VENV_UVICORN = .venv/bin/uvicorn

help:
	@echo "Available commands:"
	@echo "  make check-env   - Verify Python, Ollama, model, and JSON completions"
	@echo "  make seed-kb     - Seed synthetic policy knowledge base in data/kb"
	@echo "  make reindex     - Rebuild BM25 and Chroma vector indexes"
	@echo "  make test        - Run full pytest test suite"
	@echo "  make run-api     - Launch REST server and Web UI at http://localhost:8000"
	@echo "  make run-ui      - Launch Web UI at http://localhost:8000"
	@echo "  make eval        - Run benchmark evaluation suite across 32 scenarios"

check-env:
	$(VENV_PYTHON) scripts/check_env.py

seed-kb:
	$(VENV_PYTHON) scripts/seed_kb.py

reindex:
	PYTHONPATH=src $(VENV_PYTHON) -c "from provenance.ingestion.indexer import build_and_save_indexes; build_and_save_indexes()"

test:
	PYTHONPATH=src $(VENV_PYTEST) tests/ -v

PORT ?= 8000

run-api:
	PYTHONPATH=src $(VENV_UVICORN) provenance.api.app:app --host 0.0.0.0 --port $(PORT) --reload

run-ui: run-api

eval:
	PYTHONPATH=src $(VENV_PYTHON) eval/run_eval.py --fast
