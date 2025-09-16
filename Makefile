GAZ_DB 		   ?= data/gazetteer.duckdb
PBF_URL 	   ?= https://download.geofabrik.de/asia/malaysia-singapore-brunei-latest.osm.pbf
APP_NAME       ?= scout
APP_MODULE     ?= app:app
HOST           ?= 0.0.0.0
PORT           ?= 8081
VENV           ?= .venv
ENV_FILE       ?= .env

# Prefer uv if present
UV := $(shell command -v uv 2>/dev/null)

PY  := $(VENV)/bin/python
PIP := $(VENV)/bin/pip

# Helper: source .env at runtime (safe, portable)
ENV_PREFIX = set -a; [ -f $(ENV_FILE) ] && . $(ENV_FILE); set +a;

.PHONY: setup venv install install-dev
setup: venv install-dev

venv:
ifdef UV
	uv venv $(VENV)
else
	python3 -m venv $(VENV)
endif

install:
ifdef UV
	uv sync
else ifneq (,$(wildcard pyproject.toml))
	$(PIP) install .
else ifneq (,$(wildcard requirements.txt))
	$(PIP) install -r requirements.txt
else
	@echo "No pyproject.toml or requirements.txt found"; exit 1
endif

install-dev:
ifdef UV
	uv sync --all-extras --dev
else ifneq (,$(wildcard pyproject.toml))
	$(PIP) install -e ".[dev]"
else
	@echo "Dev install requires pyproject extras or uv"; exit 1
endif

.PHONY: run dev
run:
ifdef UV
	$(ENV_PREFIX) uv run uvicorn $(APP_MODULE) --host $(HOST) --port $(PORT)
else
	$(ENV_PREFIX) $(VENV)/bin/uvicorn $(APP_MODULE) --host $(HOST) --port $(PORT)
endif

dev:
ifdef UV
	$(ENV_PREFIX) uv run uvicorn $(APP_MODULE) --host $(HOST) --port $(PORT) --reload
else
	$(ENV_PREFIX) $(VENV)/bin/uvicorn $(APP_MODULE) --host $(HOST) --port $(PORT) --reload
endif

.PHONY: build-gaz download-pbf
download-pbf:
	@mkdir -p data
	@curl -L "$(PBF_URL)" -o data/region.osm.pbf

build-gaz:
	@python3 scripts/build_gazetteer.py --pbf "$(PBF_URL)" --out "$(GAZ_DB)" --overwrite