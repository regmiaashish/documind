UV ?= uv
COMPOSE := docker compose
.DEFAULT_GOAL := help
.PHONY: help setup up migrate restart stop down logs lint test dev-web build-web test-web evaluate evaluation-report
EVAL_ARGS ?=

help: ## Show available commands
	@awk 'BEGIN {FS = ":.*## "} /^[a-z-]+:.*## / {printf "  %-12s %s\n", $$1, $$2}' $(MAKEFILE_LIST)

setup: ## Install locked dependencies and fill .env defaults, preserving existing values
	$(UV) sync --project backend --frozen
	backend/.venv/bin/python scripts/setup_env.py

up: ## Build and start services, waiting for readiness
	$(COMPOSE) up --build -d --wait

migrate: ## Start the database and apply pending migrations
	$(COMPOSE) up -d --wait db
	$(COMPOSE) run --build --rm --no-deps api alembic upgrade head

restart: ## Restart existing containers (use up after code or config changes)
	$(COMPOSE) restart

stop: ## Stop services, keeping containers and data
	$(COMPOSE) stop

down: ## Remove containers and networks, keeping database data
	$(COMPOSE) down

logs: ## Follow service logs
	$(COMPOSE) logs -f

lint: ## Check Python style and common mistakes
	$(UV) run --project backend ruff check backend/src backend/migrations backend/tests scripts

test: ## Run offline backend tests (no Gemini key required)
	cd backend && $(UV) run pytest

dev-web: ## Run the frontend locally (API must be running)
	cd frontend && npm ci --no-audit --no-fund && npm run dev

build-web: ## Type-check and build the frontend
	cd frontend && npm ci --no-audit --no-fund && npm run build

test-web: ## Check frontend streaming behavior
	cd frontend && npm test

evaluate: ## Run or resume the 90-case PostgreSQL/Gemini evaluation
	PYTHONPATH=backend/src $(UV) run --project backend python -m documind.evaluation run $(EVAL_ARGS)

evaluation-report: ## Generate a Markdown report from saved evaluation results
	PYTHONPATH=backend/src $(UV) run --project backend python -m documind.evaluation report $(EVAL_ARGS)
