"""
Open Rabbit Knowledge Base System

A production-ready learnings subsystem for AI code review systems.

Quick start:
    from src.learnings.core.storage import LearningStorage
    from src.learnings.core.retriever import LearningRetriever
    from src.learnings.core.config import get_settings
    
    settings = get_settings()
    storage = LearningStorage(settings)
    retriever = LearningRetriever(storage, settings)
    
    # Search for learnings
    from src.learnings.core.models import LearningSearchRequest
    results = retriever.search(
        LearningSearchRequest(query="error handling", k=5)
    )
"""

__version__ = "1.0.0"
__author__ = "Jagjeevan Kashid"
__description__ = "CodeRabbit-inspired learnings ingestion and retrieval system"

# Core exports
from src.learnings.core.models import (
    Learning,
    ReviewComment,
    LearningSource,
    FeedbackType,
    LearningSearchRequest,
    LearningSearchResponse,
)
from src.learnings.core.config import get_settings, Settings

__all__ = [
    "Learning",
    "ReviewComment", 
    "LearningSource",
    "FeedbackType",
    "LearningSearchRequest",
    "LearningSearchResponse",
    "get_settings",
    "Settings",
]
