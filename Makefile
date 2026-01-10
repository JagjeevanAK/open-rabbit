.PHONY: help install install-backend install-bot install-web install-kb \
        dev dev-backend dev-bot dev-web dev-kb \
        build build-backend build-bot build-web \
        test test-backend test-bot \
        lint lint-web \
        docker-up docker-down docker-build docker-logs docker-ps \
        db-migrate db-upgrade db-downgrade db-history db-current \
        clean clean-backend clean-bot clean-web clean-docker \
        infra-up infra-down env-check env-setup setup

.DEFAULT_GOAL := help

help: ## Show this help message
	@echo "Usage: make [target]"
	@echo ""
	@echo "Targets:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

setup: install ## Full project setup (alias for install)

install: install-backend install-bot install-web install-kb ## Install all dependencies

install-backend: ## Install backend dependencies (uv)
	cd backend && uv sync

install-bot: ## Install bot dependencies (npm)
	cd bot && npm install

install-web: ## Install web dependencies (bun)
	cd web && bun install

install-kb: ## Install knowledge-base dependencies (uv)
	cd knowledge-base && uv sync

dev-backend: ## Run backend dev server
	cd backend && uv run uvicorn main:app --reload --host 0.0.0.0 --port 8000

dev-bot: ## Run bot dev server
	cd bot && npm run dev

dev-web: ## Run web dev server
	cd web && bun run dev

dev-kb: ## Run knowledge-base dev server
	cd knowledge-base && uv run python main.py

build: build-backend build-bot build-web ## Build all projects

build-backend: ## Build backend (no-op for Python)
	@echo "Backend is Python - no build step required"

build-bot: ## Build bot (TypeScript)
	cd bot && npm run build

build-web: ## Build web (Next.js)
	cd web && bun run build

test: test-backend test-bot ## Run all tests

test-backend: ## Run backend tests
	cd backend && uv run pytest

test-bot: ## Run bot tests
	cd bot && npm test

lint: lint-web ## Run all linters

lint-web: ## Lint web project
	cd web && bun run lint

docker-up: ## Start all Docker services
	docker compose up -d

docker-down: ## Stop all Docker services
	docker compose down

docker-build: ## Build all Docker images
	docker compose build

docker-rebuild: ## Rebuild and restart all Docker services
	docker compose down && docker compose build && docker compose up -d

docker-logs: ## View logs from all services
	docker compose logs -f

docker-logs-backend: ## View backend logs
	docker compose logs -f backend

docker-logs-bot: ## View bot logs
	docker compose logs -f bot

docker-ps: ## Show running containers
	docker compose ps

docker-exec-backend: ## Open shell in backend container
	docker compose exec backend /bin/sh

docker-exec-bot: ## Open shell in bot container
	docker compose exec bot /bin/sh

db-migrate: ## Create a new migration (usage: make db-migrate msg="message")
	cd backend && uv run alembic revision --autogenerate -m "$(msg)"

db-upgrade: ## Apply all migrations
	cd backend && uv run alembic upgrade head

db-downgrade: ## Rollback last migration
	cd backend && uv run alembic downgrade -1

db-history: ## Show migration history
	cd backend && uv run alembic history

db-current: ## Show current migration
	cd backend && uv run alembic current

infra-up: ## Start infrastructure (postgres, redis, elasticsearch)
	docker compose up -d postgres redis elasticsearch

infra-down: ## Stop infrastructure services
	docker compose stop postgres redis elasticsearch

clean: clean-backend clean-bot clean-web ## Clean all build artifacts

clean-backend: ## Clean backend artifacts
	cd backend && rm -rf __pycache__ .pytest_cache

clean-bot: ## Clean bot artifacts
	cd bot && rm -rf lib node_modules

clean-web: ## Clean web artifacts
	cd web && rm -rf .next node_modules

clean-docker: ## Remove Docker volumes and orphans
	docker compose down -v --remove-orphans

env-check: ## Check if required environment files exist
	@echo "Checking environment files..."
	@test -f backend/.env && echo "✓ backend/.env exists" || echo "✗ backend/.env missing"
	@test -f bot/.env && echo "✓ bot/.env exists" || echo "✗ bot/.env missing"
	@test -f knowledge-base/.env && echo "✓ knowledge-base/.env exists" || echo "✗ knowledge-base/.env missing"

env-setup: ## Copy example env files (if not exists)
	@test -f backend/.env || cp backend/.env.example backend/.env
	@test -f bot/.env || cp bot/.env.example bot/.env
	@test -f knowledge-base/.env || cp knowledge-base/.env.example knowledge-base/.env
	@echo "Environment files set up. Please edit them with your values."
