from pydantic import BaseModel, Field
from typing import Optional, List, Any, Dict
from datetime import datetime
from enum import Enum


class ReviewStatusEnum(str, Enum):
    """Status of a review session."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    POSTED = "posted"
    FAILED = "failed"


class CommentSeverityEnum(str, Enum):
    """Severity level of a review comment."""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class CommentCategoryEnum(str, Enum):
    """Category of a review comment."""
    BUG = "bug"
    SECURITY = "security"
    PERFORMANCE = "performance"
    STYLE = "style"
    REFACTOR = "refactor"
    DOCUMENTATION = "documentation"
    TEST = "test"
    OTHER = "other"

class UserBase(BaseModel):
    name: str
    email: str
    org: str
    sub: bool

class UserCreate(UserBase):
    pass

class UserResponse(UserBase):
    id: int

    class Config:
        orm_mode = True

class ChangedFileReq(BaseModel):
    changedFiles: list
    pr_no: int
    owner: str
    repo: str

class PRBase(BaseModel):
    org: str
    repo: str
    pr_no: int
    branch: str
    cnt: int


# Checkpoint schemas
class CheckpointCreate(BaseModel):
    """Schema for creating a new checkpoint."""
    thread_id: str
    owner: Optional[str] = None
    repo: Optional[str] = None
    pr_number: Optional[int] = None
    current_node: str
    completed_nodes: List[str] = []
    state_data: Dict[str, Any]
    status: str = "in_progress"


class CheckpointUpdate(BaseModel):
    """Schema for updating an existing checkpoint."""
    current_node: Optional[str] = None
    completed_nodes: Optional[List[str]] = None
    state_data: Optional[Dict[str, Any]] = None
    status: Optional[str] = None
    error_message: Optional[str] = None


class CheckpointResponse(BaseModel):
    """Schema for checkpoint response."""
    id: int
    thread_id: str
    owner: Optional[str]
    repo: Optional[str]
    pr_number: Optional[int]
    current_node: Optional[str]
    completed_nodes: List[str]
    state_data: Dict[str, Any]
    status: str
    error_message: Optional[str]
    created_at: datetime
    updated_at: datetime

    class Config:
        orm_mode = True


# ============================================
# Review Session and Comment Schemas
# ============================================

class ReviewCommentBase(BaseModel):
    """Base schema for a review comment."""
    file_path: str
    line: int
    start_line: Optional[int] = None
    side: str = "RIGHT"
    start_side: Optional[str] = None
    title: Optional[str] = None
    body: str
    severity: CommentSeverityEnum = CommentSeverityEnum.MEDIUM
    category: CommentCategoryEnum = CommentCategoryEnum.OTHER
    suggestion: Optional[str] = None


class ReviewCommentCreate(ReviewCommentBase):
    """Schema for creating a new review comment."""
    pass


class ReviewCommentResponse(ReviewCommentBase):
    """Schema for review comment response."""
    id: int
    review_session_id: int
    github_comment_id: Optional[int] = None
    created_at: datetime

    class Config:
        orm_mode = True


class ReviewCommentGitHub(BaseModel):
    """Schema for a comment formatted for GitHub API."""
    path: str
    line: int
    start_line: Optional[int] = None
    side: str = "RIGHT"
    start_side: Optional[str] = None
    body: str


class ReviewSessionBase(BaseModel):
    """Base schema for a review session."""
    org: str
    repo: str
    pr_number: int
    base_branch: str = "main"
    head_sha: Optional[str] = None


class ReviewSessionCreate(ReviewSessionBase):
    """Schema for creating a new review session."""
    session_id: str


class ReviewSessionUpdate(BaseModel):
    """Schema for updating a review session."""
    files_reviewed: Optional[int] = None
    total_comments: Optional[int] = None
    summary: Optional[str] = None
    status: Optional[ReviewStatusEnum] = None
    github_review_id: Optional[int] = None
    error_message: Optional[str] = None
    posted_at: Optional[datetime] = None


class ReviewSessionResponse(ReviewSessionBase):
    """Schema for review session response."""
    id: int
    session_id: str
    files_reviewed: int
    total_comments: int
    summary: Optional[str] = None
    status: str
    github_review_id: Optional[int] = None
    error_message: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    posted_at: Optional[datetime] = None
    comments: List[ReviewCommentResponse] = []

    class Config:
        orm_mode = True


class ReviewSessionWithComments(ReviewSessionResponse):
    """Review session with all comments included."""
    comments: List[ReviewCommentResponse] = []


class GitHubReviewPayload(BaseModel):
    """
    Payload to send to the bot for posting a review to GitHub.
    
    This matches the format expected by the bot's /post-review endpoint.
    """
    owner: str
    repo: str
    pr_number: int = Field(..., alias="prNumber")
    commit_sha: str = Field(..., alias="commitSha")
    summary: str
    comments: List[ReviewCommentGitHub]
    session_id: str = Field(..., alias="sessionId")

    class Config:
        populate_by_name = True
