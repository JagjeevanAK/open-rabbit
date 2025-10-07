"""
Data models for the Learnings subsystem.

Defines the schema for project learnings extracted from code review comments,
matching CodeRabbit's architecture for storing and retrieving context-aware feedback.
"""

from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field
from enum import Enum


class FeedbackType(str, Enum):
    """Types of human feedback on review comments"""
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    MODIFIED = "modified"
    THANKED = "thanked"
    DEBATED = "debated"
    IGNORED = "ignored"


class LearningSource(BaseModel):
    """
    Metadata about where a learning originated.
    
    This tracks the PR context so learnings can be filtered
    or weighted by repository, author, or file type.
    """
    repo_name: str = Field(..., description="Repository identifier (e.g., 'org/repo')")
    pr_number: int = Field(..., description="Pull request number")
    pr_title: Optional[str] = Field(None, description="Pull request title")
    file_path: str = Field(..., description="File path where comment was made")
    author: str = Field(..., description="Comment author (bot or human)")
    reviewer: Optional[str] = Field(None, description="Human reviewer who responded")
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class ReviewComment(BaseModel):
    """
    Raw review comment payload received from the review system.
    
    This is the input format when a review comment is submitted
    to the learnings ingestion endpoint.
    """
    comment_id: str = Field(..., description="Unique comment identifier")
    raw_comment: str = Field(..., description="The actual review comment text")
    code_snippet: Optional[str] = Field(None, description="Associated code snippet")
    language: Optional[str] = Field(None, description="Programming language")
    feedback_type: Optional[FeedbackType] = Field(None, description="Human feedback classification")
    source: LearningSource = Field(..., description="Context metadata")


class Learning(BaseModel):
    """
    A normalized, summarized project learning extracted from a review comment.
    
    This is the core entity stored in both the vector DB (for semantic search)
    and optionally a relational DB (for structured queries).
    
    Design matches CodeRabbit's approach:
    - learning_text: The distilled insight (e.g., "Always use const for immutable variables")
    - embedding: Vector representation for similarity search
    - metadata: Rich context for filtering and ranking
    """
    learning_id: str = Field(..., description="Unique learning identifier (UUID)")
    learning_text: str = Field(..., description="Summarized learning or best practice")
    original_comment: str = Field(..., description="Original raw comment for reference")
    code_context: Optional[str] = Field(None, description="Code snippet if relevant")
    language: Optional[str] = Field(None, description="Programming language")
    
    # Metadata for retrieval and ranking
    source: LearningSource = Field(..., description="Origin metadata")
    feedback_type: Optional[FeedbackType] = Field(None, description="Human feedback signal")
    confidence_score: float = Field(default=1.0, ge=0.0, le=1.0, description="Quality/confidence score")
    
    # Vector DB fields (optional, generated during storage)
    embedding: Optional[List[float]] = Field(default=None, description="Embedding vector (not serialized to API)")
    
    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    class Config:
        json_schema_extra = {
            "example": {
                "learning_id": "550e8400-e29b-41d4-a716-446655440000",
                "learning_text": "The project prefers automated dependency updates with security audits post-upgrade.",
                "original_comment": "Bump outdated dependencies to the latest stable versions and run npm audit.",
                "code_context": "package.json dependency update",
                "language": "javascript",
                "source": {
                    "repo_name": "acme/web-app",
                    "pr_number": 1234,
                    "file_path": "package.json",
                    "author": "dependabot",
                    "timestamp": "2025-10-07T10:00:00Z"
                },
                "feedback_type": "accepted",
                "confidence_score": 0.95
            }
        }


class LearningSearchRequest(BaseModel):
    """Request model for semantic search endpoint"""
    query: str = Field(..., description="Search query text")
    k: int = Field(default=5, ge=1, le=50, description="Number of results to return")
    repo_filter: Optional[str] = Field(default=None, description="Filter by repository")
    language_filter: Optional[str] = Field(default=None, description="Filter by programming language")
    min_confidence: float = Field(default=0.0, ge=0.0, le=1.0, description="Minimum confidence score")


class LearningSearchResponse(BaseModel):
    """Response model for semantic search endpoint"""
    query: str
    results: List[Learning]
    total_results: int
    search_time_ms: float


class IngestionRequest(BaseModel):
    """Request model for ingestion endpoint"""
    comment: ReviewComment = Field(..., description="Review comment to ingest")
    async_processing: bool = Field(default=True, description="Process async via Celery or sync")


class IngestionResponse(BaseModel):
    """Response model for ingestion endpoint"""
    task_id: Optional[str] = Field(None, description="Celery task ID if async")
    status: str = Field(..., description="Status message")
    learning_id: Optional[str] = Field(None, description="Learning ID if processed synchronously")
