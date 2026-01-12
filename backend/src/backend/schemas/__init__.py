"""
Schemas Package

Centralized Pydantic models for the backend.

- db: Database CRUD schemas (for SQLAlchemy models)
- api: API request/response models (for route handlers)
"""

# Database schemas
from .db import (
    # User schemas
    UserBase,
    UserCreate,
    # PR schemas
    ChangedFileReq,
    PRBase,
    # Checkpoint schemas
    CheckpointCreate,
    CheckpointUpdate,
)

# API schemas
from .api import (
    # Bot request models
    ReviewRequest,
    UnitTestRequest,
    PRUnitTestRequest,
    # Task response models
    TaskResponse,
    TaskStatus,
    TaskListResponse,
    HealthResponse,
    # Feedback models
    PRReviewRequest,
    ReviewResponse,
    ReviewStatusModel,
)

__all__ = [
    # DB User
    "UserBase",
    "UserCreate",
    # DB PR
    "ChangedFileReq",
    "PRBase",
    # DB Checkpoint
    "CheckpointCreate",
    "CheckpointUpdate",
    # API Bot
    "ReviewRequest",
    "UnitTestRequest",
    "PRUnitTestRequest",
    # API Task
    "TaskResponse",
    "TaskStatus",
    "TaskListResponse",
    "HealthResponse",
    # API Feedback
    "PRReviewRequest",
    "ReviewResponse",
    "ReviewStatusModel",
]

