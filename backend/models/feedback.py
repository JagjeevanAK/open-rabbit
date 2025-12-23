"""
Feedback Models

Pydantic models for code review feedback endpoints.
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any


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


class FileReviewRequest(BaseModel):
    """Request model for reviewing specific files"""
    file_paths: List[str] = Field(..., description="List of file paths to review")
    repo_path: str = Field(..., description="Path to the repository")
    context: Optional[str] = Field(None, description="Additional context about the review")
    generate_tests: bool = Field(False, description="Whether to generate unit tests")


class ReviewResponse(BaseModel):
    """Response model for review results"""
    task_id: str
    status: str
    message: str
    review_url: Optional[str] = None


class ReviewStatus(BaseModel):
    """Status model for review task"""
    task_id: str
    status: str
    created_at: str
    completed_at: Optional[str] = None
    result: Optional[Dict[str, Any]] = None
