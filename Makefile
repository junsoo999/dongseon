.PHONY: install dev serve backend frontend lint fmt test gen-types db-upgrade usage launchd-install daily prices scout launchd-uninstall launchd-status app-restart clean help

# Default python version
PYTHON_VERSION ?= 3.12
# Test configuration
TEST_MODE ?= all
COVERAGE ?= 0

# Validate TEST_MODE value
ifeq ($(filter $(TEST_MODE),all backend frontend),)
$(error TEST_MODE must be one of 'all', 'backend', 'frontend')
endif

# Installation target
install:
	@echo "Installing dev environment (Python $(PYTHON_VERSION))..."
	@bash scripts/install_packages.sh --python_ver $(PYTHON_VERSION)

# Run the dev backend (127.0.0.1:DEV_API_PORT, auto-reload) and frontend (port 5174, all interfaces) together.
# Port 8100 belongs to the always-on app (launchd JOB=serve); the dev backend uses 8101 so both can run.
# jipsa uses 8000 / 8001 / 5173, so both repos can run side by side.
DEV_API_PORT ?= 8101
dev:
	@trap 'kill 0' INT TERM EXIT; \
	uv run --no-sync dongseon serve --port $(DEV_API_PORT) & \
	DONGSEON_API_PORT=$(DEV_API_PORT) pnpm --dir frontend dev --host & \
	wait

# Production-style: build the frontend, then serve it and /api on one port (PORT, HOST)
PORT ?= 8100
HOST ?= 127.0.0.1
serve:
	@pnpm --dir frontend build
	@uv run --no-sync dongseon serve --no-reload --host $(HOST) --port $(PORT)

backend:
	@uv run --no-sync dongseon serve --port $(DEV_API_PORT)

frontend:
	@DONGSEON_API_PORT=$(DEV_API_PORT) pnpm --dir frontend dev --host

# Run pre-commit on all files (ruff, pyright, oxlint, prettier, tsc, markdownlint, ...)
lint:
	@echo "Running pre-commit on all files..."
	@uv run --no-sync pre-commit run --all-files

# Auto-format both sides
fmt:
	@uv run --no-sync ruff check --fix .
	@uv run --no-sync ruff format .
	@pnpm --dir frontend format

# Run tests
test:
	@echo "Running $(TEST_MODE) tests..."
	@if [ "$(TEST_MODE)" = "all" ] || [ "$(TEST_MODE)" = "backend" ]; then \
		if [ "$(COVERAGE)" = "1" ]; then bash scripts/run_pytest.sh --coverage; \
		else bash scripts/run_pytest.sh; fi; \
	fi
	@if [ "$(TEST_MODE)" = "all" ] || [ "$(TEST_MODE)" = "frontend" ]; then \
		pnpm --dir frontend test; \
	fi

# Regenerate frontend API types from the backend OpenAPI schema
gen-types:
	@mkdir -p data
	@uv run --no-sync dongseon openapi --out data/openapi.json
	@pnpm --dir frontend gen-types
	@pnpm --dir frontend exec prettier --write src/api/schema.d.ts >/dev/null

# Apply DB migrations
db-upgrade:
	@uv run --no-sync dongseon db upgrade

# Google API calls per SKU this month against the free caps
usage:
	@uv run --no-sync dongseon usage

# Always-on services and the daily job via macOS launchd (JOB=serve|daily)
JOB ?= serve
HOUR ?= 6
MINUTE ?= 0
launchd-install:
	@bash scripts/launchd.sh install --job $(JOB) $(if $(filter daily,$(JOB)),--hour $(HOUR) --minute $(MINUTE),)

launchd-uninstall:
	@bash scripts/launchd.sh uninstall --job $(JOB)

launchd-status:
	@bash scripts/launchd.sh status --job $(JOB)

# Rebuild the frontend and restart the always-on app after pulling new code
app-restart:
	@bash scripts/launchd.sh restart --job serve

# Daily pipeline (what launchd JOB=daily runs), and its steps
daily:
	@uv run --no-sync dongseon daily

prices:
	@uv run --no-sync dongseon prices

scout:
	@uv run --no-sync dongseon scout

# Clean caches and build artifacts
clean:
	@echo "Cleaning caches and build artifacts..."
	@rm -rf build/ dist/ ./*.egg-info/ frontend/dist/
	@rm -rf .ruff_cache/ .pytest_cache/
	@rm -f pytest-report.xml coverage.xml .coverage
	@find . -path ./frontend/node_modules -prune -o -type d -name "__pycache__" -exec rm -rf {} +
	@echo "Clean done."

# Help target
help:
	@echo "Available targets:"
	@echo "  install    - uv sync + pre-commit install + pnpm install + local config copies"
	@echo "               Usage: make install [PYTHON_VERSION=3.12|3.13] (default: 3.12)"
	@echo "  dev        - Dev backend (127.0.0.1:8101, reload) + frontend (:5174, LAN); 8100 stays with the always-on app"
	@echo "  serve      - Build frontend and serve it with the API on one port"
	@echo "               Usage: make serve [HOST=127.0.0.1] [PORT=8100]"
	@echo "  backend    - Run backend only"
	@echo "  frontend   - Run frontend only"
	@echo "  lint       - Run pre-commit hooks on all files"
	@echo "  fmt        - Auto-format Python (ruff) and frontend (prettier)"
	@echo "  test       - Run tests"
	@echo "               Usage: make test [TEST_MODE=all|backend|frontend] (default: all)"
	@echo "                                [COVERAGE=0|1] (default: 0)"
	@echo "  gen-types  - Regenerate frontend/src/api/schema.d.ts from OpenAPI"
	@echo "  db-upgrade - Apply DB migrations"
	@echo "  usage      - Google API calls per SKU this month vs free caps"
	@echo "  daily      - Live prices then AI scouting (what launchd JOB=daily runs)"
	@echo "  prices     - Ignav fares + Rakuten Travel vacancies for upcoming trips"
	@echo "  scout      - AI research for places and stays (Claude Code)"
	@echo "  launchd-install   - Install an always-on service via launchd (serve: 127.0.0.1:8100) ([JOB=serve|daily] [HOUR=6])"
	@echo "  launchd-uninstall - Remove a launchd agent ([JOB=serve|daily])"
	@echo "  launchd-status    - Show agent state and last log lines ([JOB=serve|daily])"
	@echo "  app-restart       - Rebuild the frontend and restart the always-on app"
	@echo "  clean      - Remove caches and build artifacts"
	@echo "  help       - Show this help message"
