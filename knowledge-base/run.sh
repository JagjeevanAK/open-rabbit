#!/bin/bash

# Knowledge Base Runner Script
# This script helps you start the different components of the knowledge base

case "$1" in
    api)
        echo "Starting FastAPI server..."
        uv run uvicorn app:app --reload --host 0.0.0.0 --port 8000
        ;;
    worker)
        echo "Starting Celery worker..."
        uv run celery -A celery_app worker --loglevel=info
        ;;
    flower)
        echo "Starting Celery Flower monitoring..."
        uv run celery -A celery_app flower
        ;;
    all)
        echo "Starting all services requires multiple terminals."
        echo "Please run the following commands in separate terminals:"
        echo ""
        echo "Terminal 1 - API Server:"
        echo "  ./run.sh api"
        echo ""
        echo "Terminal 2 - Celery Worker:"
        echo "  ./run.sh worker"
        echo ""
        echo "Terminal 3 (Optional) - Flower Monitoring:"
        echo "  ./run.sh flower"
        ;;
    *)
        echo "Usage: ./run.sh {api|worker|flower|all}"
        echo ""
        echo "Commands:"
        echo "  api     - Start the FastAPI server"
        echo "  worker  - Start the Celery worker"
        echo "  flower  - Start Celery Flower monitoring"
        echo "  all     - Show instructions for running all services"
        exit 1
        ;;
esac
