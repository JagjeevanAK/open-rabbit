"""
Bot Models

Pydantic models for bot webhook request/response schemas.
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any


class ReviewRequest(BaseModel):
    """Request from bot to trigger code review"""
    owner: str = Field(..., description="Repository owner")
    repo: str = Field(..., description="Repository name")
    pr_number: int = Field(..., description="Pull request number")
    branch: str = Field(..., description="Branch to review")
    changed_files: Optional[List[str]] = Field(None, description="List of changed files")
    installation_id: int = Field(0, description="GitHub App installation ID (0 for test mode)")
    comment_id: Optional[int] = Field(None, description="Comment ID that triggered the review")
    
    # Test mode flags
    test_mode: bool = Field(False, description="If true, use test endpoints (PAT auth)")
    dry_run: bool = Field(True, description="If true, save results to file instead of posting")


class UnitTestRequest(BaseModel):
    """Request to generate unit tests"""
    owner: str = Field(..., description="Repository owner")
    repo: str = Field(..., description="Repository name")
    issue_number: int = Field(..., description="Issue/PR number")
    branch: str = Field(..., description="Branch to generate tests for")
    installation_id: int = Field(..., description="GitHub App installation ID")
    comment_id: Optional[int] = Field(None, description="Comment ID that triggered the request")


class TaskResponse(BaseModel):
    """Response for task creation"""
    task_id: str
    status: str
    message: str
    test_branch: Optional[str] = None


class TaskStatus(BaseModel):
    """Status of a bot task"""
    task_id: str
    status: str
    owner: str
    repo: str
    created_at: str
    completed_at: Optional[str] = None
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


class TaskListResponse(BaseModel):
    """Response for listing tasks"""
    total: int
    tasks: List[Dict[str, Any]]


class HealthResponse(BaseModel):
    """Health check response"""
    status: str
    service: str
    mock_llm: bool
