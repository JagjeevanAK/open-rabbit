"""
Knowledge Base Module

A structured knowledge base for storing and retrieving code learnings
using Elasticsearch and OpenAI embeddings.

Main Components:
- FastAPI app for REST API
- Celery tasks for async processing
- Elasticsearch for vector search

Usage:
    from knowledge_base import app, settings
    from knowledge_base.tasks import process_learning
"""

from .config import settings
from .app import app
from .celery_app import celery_app
from .main import query_knowledge_base, create_retriever

__all__ = [
    "app",
    "settings",
    "celery_app",
    "query_knowledge_base",
    "create_retriever",
]
