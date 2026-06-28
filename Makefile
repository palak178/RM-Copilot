# RM Copilot — developer entry points.
# On Windows, run via Git Bash, or invoke the underlying commands directly.
# Targets that depend on not-yet-implemented code (seed/run/ui) will work once
# the corresponding milestone lands.

PYTHON ?= python

.PHONY: help setup hooks lint format format-check test cov seed run ui api demo docker-build docker-run clean

help:
	@echo "setup        install package + dev tooling (editable)"
	@echo "hooks        install pre-commit git hooks"
	@echo "lint         ruff lint"
	@echo "format       ruff auto-format"
	@echo "format-check ruff format --check (CI)"
	@echo "test         run pytest"
	@echo "cov          run pytest with coverage"
	@echo "seed         build the deterministic synthetic SQLite dataset (M1)"
	@echo "run          run the conversational CLI (M5)"
	@echo "ui           run the Streamlit demo (M5)"
	@echo "api          run the FastAPI server (M5.5; needs .[api])"
	@echo "demo         scripted 3-scenario walkthrough (needs a live LLM key)"
	@echo "docker-build / docker-run   container workflow"
	@echo "clean        remove caches and runtime artifacts"

setup:
	$(PYTHON) -m pip install -e ".[dev]"

# Per-milestone installs (recommended): .[dev,seed] at M1, add llm at M4, add ui at M5.

hooks:
	pre-commit install

lint:
	ruff check .

format:
	ruff format .
	ruff check --fix .

format-check:
	ruff format --check .

test:
	pytest

cov:
	pytest --cov --cov-report=term-missing

seed:
	$(PYTHON) scripts/seed_db.py

run:
	$(PYTHON) ui/cli.py

ui:
	streamlit run ui/streamlit_app.py

api:
	uvicorn rm_copilot.api.app:create_app --factory --port 8000

demo:
	$(PYTHON) scripts/demo.py

docker-build:
	docker build -t rm-copilot .

docker-run:
	docker run --rm -p 8501:8501 --env-file .env rm-copilot

clean:
	rm -rf .pytest_cache .ruff_cache htmlcov .coverage var/*.db
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
