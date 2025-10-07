"""
Celery worker entry point.

Run this module to start Celery workers for async learning ingestion:

    celery -A src.learnings.tasks.celery_worker worker --loglevel=info

For development with auto-reload:

    watchfiles --filter python 'celery -A src.learnings.tasks.celery_worker worker --loglevel=info'
"""

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
