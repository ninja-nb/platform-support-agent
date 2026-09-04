VENV_PY := $(CURDIR)/.venv/bin/python
PY ?= $(if $(wildcard $(VENV_PY)),$(VENV_PY),python3)
export PYTHONPATH := src

.PHONY: help setup index eval test lint ui up down clean

help:
	@echo "make setup   - create .venv and install dev extras"
	@echo "make index   - build the retrieval index from data/corpus"
	@echo "make eval    - run the golden set, write docs/EVALS.md table"
	@echo "make test    - pytest"
	@echo "make lint    - ruff"
	@echo "make ui      - run the Streamlit console"
	@echo "make up      - docker compose up"

setup:
	uv venv --allow-existing && uv pip install -e '.[dev]'

index:
	$(PY) -m psa.rag.index

# Runs with PROVIDER=stub by default: no API key, no network, deterministic.
eval:
	$(PY) -m psa.evals.runner --write-report

test:
	$(PY) -m pytest -q

lint:
	$(PY) -m ruff check src tests ui

ui:
	$(PY) -m streamlit run ui/app.py

up:
	docker compose -f infra/docker-compose.yml up --build

down:
	docker compose -f infra/docker-compose.yml down -v

clean:
	rm -rf .index runs audit.log .pytest_cache .ruff_cache
