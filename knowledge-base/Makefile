.PHONY: help install start-services start-worker start-api test example clean

help: ## Show this help message
	@echo "Learnings System - Make Commands"
	@echo "================================"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

install: ## Install Python dependencies
	@echo "Installing dependencies..."
	uv sync
	@echo "✓ Dependencies installed"

setup-env: ## Create .env file from template
	@if [ ! -f .env ]; then \
		cp .env.example .env; \
		echo "✓ Created .env file"; \
		echo "Please edit .env and add your OPENAI_API_KEY"; \
	else \
		echo "✓ .env file already exists"; \
	fi

start-services: 
	@echo "Starting Redis and Qdrant..."
	docker-compose up -d redis qdrant
	@echo "✓ Services started"
	@echo "  Redis: localhost:6379"
	@echo "  Qdrant: http://localhost:6333"

stop-services: 
	@echo "Stopping services..."
	docker-compose down
	@echo "✓ Services stopped"

start-worker: 
	@echo "Starting Celery worker..."
	celery -A src.learnings.tasks.celery_worker worker --loglevel=info

start-api: 
	@echo "Starting FastAPI server..."
	uvicorn src.learnings.api.main:app --reload --port 8000

dev: ## Start all services (requires multiple terminals)
	@echo "To run the full system, open 4 terminals and run:"
	@echo ""
	@echo "Terminal 1: make start-services"
	@echo "Terminal 2: make start-worker"
	@echo "Terminal 3: make start-api"
	@echo "Terminal 4: make example"

example: ## Run example script
	@echo "Running example script..."
	python scripts/example.py

test-health: ## Test health endpoints
	@echo "Testing health endpoints..."
	@curl -s http://localhost:8000/health | python -m json.tool
	@echo ""
	@curl -s http://localhost:8000/worker-health | python -m json.tool

test-stats: ## Get collection stats
	@echo "Collection statistics:"
	@curl -s http://localhost:8000/stats | python -m json.tool

clean: ## Clean up temporary files
	@echo "Cleaning up..."
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	@echo "✓ Cleanup complete"

docs: ## Open API documentation
	@echo "Opening API docs..."
	@open http://localhost:8000/docs || xdg-open http://localhost:8000/docs

setup: install setup-env start-services ## Complete initial setup
	@echo ""
	@echo "✓ Setup complete!"
	@echo ""
	@echo "Next steps:"
	@echo "  1. Edit .env and add your OPENAI_API_KEY"
	@echo "  2. Run 'make start-worker' in one terminal"
	@echo "  3. Run 'make start-api' in another terminal"
	@echo "  4. Run 'make example' to test the system"
