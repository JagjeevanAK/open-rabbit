"""
Celery worker entry point.

Run this module to start Celery workers for async learning ingestion:

    celery -A src.learnings.tasks.celery_worker worker --loglevel=info

For development with auto-reload:

    watchfiles --filter python 'celery -A src.learnings.tasks.celery_worker worker --loglevel=info'
"""
import os
from src.learnings.observability.telemetry import setup_telemetry

# Setup telemetry for workers
setup_telemetry(
    service_name="learnings-worker", 
    service_version=os.getenv("SERVICE_VERSION", "1.0.0")
)

from src.learnings.tasks.ingestor import celery_app

# Import tasks to register them with Celery
from src.learnings.tasks.ingestor import (
    ingest_learning_task,
    batch_ingest_learnings_task,
    health_check_task
)

# Export the Celery app for the worker command
__all__ = ["celery_app"]

if __name__ == "__main__":
    celery_app.start()
