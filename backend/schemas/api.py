"""
API Schemas Package

Pydantic models for API requests and responses.
Consolidated from the old models/ directory.
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any


# Bot / Review Request Models

class ReviewRequest(BaseModel):
    """Request from bot to trigger code review"""
    owner: str = Field(..., description="Repository owner (base repo)")
    repo: str = Field(..., description="Repository name (base repo)")
    pr_number: int = Field(..., description="Pull request number")
    branch: str = Field(..., description="Branch to review")
    base_branch: Optional[str] = Field("main", description="Base branch for diff comparison")
    head_owner: Optional[str] = Field(None, description="Head repo owner (for fork PRs)")
    head_repo: Optional[str] = Field(None, description="Head repo name (for fork PRs)")
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


class PRUnitTestRequest(BaseModel):
    """Request to generate unit tests for PR changed files and commit to branch"""
    owner: str = Field(..., description="Repository owner (base repo)")
    repo: str = Field(..., description="Repository name (base repo)")
    pr_number: int = Field(..., description="Pull request number")
    branch: str = Field(..., description="PR head branch to commit tests to")
    base_branch: str = Field("main", description="Base branch for the PR")
    head_owner: Optional[str] = Field(None, description="Head repo owner (for fork PRs)")
    head_repo: Optional[str] = Field(None, description="Head repo name (for fork PRs)")
    installation_id: int = Field(..., description="GitHub App installation ID")
    target_files: List[str] = Field(..., description="Files to generate tests for")
    changed_files: List[str] = Field(..., description="All changed files in the PR")
    existing_test_files: List[str] = Field(default_factory=list, description="Existing test files to skip")
    test_framework: str = Field("unknown", description="Detected test framework")
    test_directory: Optional[str] = Field(None, description="Detected test directory pattern")
    requested_by: Optional[str] = Field(None, description="GitHub user who requested tests")


# Task Response Models

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


# Feedback / PR Review Models

class PRReviewRequest(BaseModel):
    """Request model for PR code review"""
    repo_url: str = Field(..., description="GitHub repository URL or shorthand (e.g., 'owner/repo')")
    pr_number: Optional[int] = Field(None, description="Pull request number")
    branch: Optional[str] = Field(None, description="Branch name to review")
    changed_files: Optional[List[str]] = Field(None, description="List of changed files")
    pr_description: Optional[str] = Field(None, description="Pull request description")
    generate_tests: bool = Field(False, description="Whether to generate unit tests")
    installation_id: Optional[int] = Field(None, description="GitHub App installation ID")
    auto_post: bool = Field(True, description="Automatically post review comment to GitHub PR")






class ReviewResponse(BaseModel):
    """Response model for review results"""
    task_id: str
    status: str
    message: str
    review_url: Optional[str] = None


class ReviewStatusModel(BaseModel):
    """Status model for review task"""
    task_id: str
    status: str
    created_at: str
    completed_at: Optional[str] = None
    result: Optional[Dict[str, Any]] = None
