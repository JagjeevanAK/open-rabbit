.PHONY: help install setup start-infra stop-infra init-index api worker flower example clean

help:
	@echo "Knowledge Base - Available Commands"
	@echo "===================================="
	@echo "make install      - Install dependencies"
	@echo "make setup        - Complete setup (install + start infra + init index)"
	@echo "make start-infra  - Start Elasticsearch and Redis with Docker"
	@echo "make stop-infra   - Stop Elasticsearch and Redis"
	@echo "make init-index   - Initialize Elasticsearch index"
	@echo "make api          - Start FastAPI server"
	@echo "make worker       - Start Celery worker"
	@echo "make flower       - Start Celery Flower monitoring"
	@echo "make example      - Run example usage script"
	@echo "make clean        - Stop all services and clean data"

install:
	uv sync

setup: install start-infra
	@echo "Waiting for services to be ready..."
	@sleep 5
	@$(MAKE) init-index
	@echo ""
	@echo "Setup complete! Run the following in separate terminals:"
	@echo "  make api"
	@echo "  make worker"

start-infra:
	docker-compose up -d
	@echo "Infrastructure started (Elasticsearch + Redis)"

stop-infra:
	docker-compose down
	@echo "Infrastructure stopped"

init-index:
	uv run python elastic/hybrid_search.py

api:
	uv run uvicorn app:app --reload --host 0.0.0.0 --port 8000

worker:
	uv run celery -A celery_app worker --loglevel=info

flower:
	uv run celery -A celery_app flower

example:
	uv run python example_usage.py

clean: stop-infra
	docker-compose down -v
	@echo "All services stopped and data cleaned"
