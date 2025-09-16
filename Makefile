UV       ?= uv
APP_MOD  ?= app:app
CONFIG   ?= config.toml
HOST     ?= 0.0.0.0
PORT     ?= 8000

.PHONY: install build-gaz run run-prod test lint lock clean

# Create/refresh the local env from pyproject + uv.lock (dev group included by default)
install:
	$(UV) sync

install-dev:
	$(UV) sync --all-extras --dev

# Build the DuckDB gazetteer using settings from config.toml
build-gaz: | install
	SCOUT_CONFIG="$(CONFIG)" $(UV) run -- python -m scripts.build_gazetteer --config "$(CONFIG)"

# Dev server (reload)
run: | install
	SCOUT_CONFIG="$(CONFIG)" $(UV) run -- uvicorn $(APP_MOD) --reload --port $(PORT)

# Prod-ish run (explicit host/port)
run-prod: | install
	SCOUT_CONFIG="$(CONFIG)" $(UV) run -- uvicorn $(APP_MOD) --host $(HOST) --port $(PORT)

test: | install
	$(UV) run -- pytest -q

lint: | install-dev
	$(UV) run -- ruff check .

lint-fix: | install-dev
	$(UV) run -- ruff check --fix .
	$(UV) run -- ruff format .

# Update lock file (pin versions)
lock:
	$(UV) lock

clean:
	rm -rf .venv __pycache__ .pytest_cache .ruff_cache