from sqlalchemy import Column, Boolean, Integer, String, Text, DateTime, Index, ForeignKey, Enum
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from .database import Base
import enum


class ReviewStatus(str, enum.Enum):
    """Status of a review session."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    POSTED = "posted"
    FAILED = "failed"


class CommentSeverity(str, enum.Enum):
    """Severity level of a review comment."""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class CommentCategory(str, enum.Enum):
    """Category of a review comment."""
    BUG = "bug"
    SECURITY = "security"
    PERFORMANCE = "performance"
    STYLE = "style"
    REFACTOR = "refactor"
    DOCUMENTATION = "documentation"
    TEST = "test"
    OTHER = "other"

class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, index=True, primary_key=True)
    name = Column(String, index=True)
    email = Column(String, index=True)
    sub = Column(Boolean, index=True, default=False)
    org = Column(String, index=True)
    
class NewInstall(Base):
    __tablename__ = "new_install"
    
    id = Column(Integer, index=True, primary_key=True)
    name = Column(String, index=True)
    org = Column(String, index=True, default=None)

class PullRequest(Base):
    __tablename__ = "pull_request"
    
    id = Column(Integer, index=True, primary_key=True)
    org = Column(String, index=True)
    repo = Column(String, index=True)
    pr_no = Column(Integer, index=True)
    branch = Column(String, index=True)
    cnt = Column(Integer, index=True, default=1)
    changed_files = Column(Text, default=None)  # Store as JSON string for SQLite compatibility


class AgentCheckpoint(Base):
    """
    Stores agent workflow checkpoints for resumability.
    
    When an agent fails mid-workflow, we can resume from the last checkpoint
    using the thread_id to restore state.
    """
    __tablename__ = "agent_checkpoints"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # Thread ID for LangGraph - unique identifier for each workflow run
    thread_id = Column(String(64), unique=True, index=True, nullable=False)
    
    # PR context for easy lookup
    owner = Column(String(255), index=True)
    repo = Column(String(255), index=True)
    pr_number = Column(Integer, index=True)
    
    # Workflow state
    current_node = Column(String(64))  # e.g., "parse_intent", "run_parser", "run_review"
    completed_nodes = Column(Text)  # JSON array of completed node names
    
    # Full state snapshot (JSON)
    state_data = Column(Text, nullable=False)  # JSON serialized workflow state
    
    # Status tracking
    status = Column(String(32), default="in_progress")  # in_progress, completed, failed
    error_message = Column(Text)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Composite index for PR lookups
    __table_args__ = (
        Index('ix_checkpoint_pr_lookup', 'owner', 'repo', 'pr_number'),
    )


class ReviewSession(Base):
    """
    Represents a single code review session for a PR.
    
    Each time we run a review on a PR, we create a new ReviewSession.
    This allows tracking multiple reviews per PR (e.g., on each push).
    """
    __tablename__ = "review_sessions"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # Unique identifier for this review session
    session_id = Column(String(64), unique=True, index=True, nullable=False)
    
    # PR context
    org = Column(String(255), index=True, nullable=False)
    repo = Column(String(255), index=True, nullable=False)
    pr_number = Column(Integer, index=True, nullable=False)
    
    # Base branch (for diff comparison)
    base_branch = Column(String(255), default="main")
    head_sha = Column(String(64))  # Commit SHA being reviewed
    
    # Review metadata
    files_reviewed = Column(Integer, default=0)
    total_comments = Column(Integer, default=0)
    
    # Summary text (displayed at top of review)
    summary = Column(Text)
    
    # Status tracking
    status = Column(String(32), default=ReviewStatus.PENDING.value)
    
    # GitHub review ID (set after posting)
    github_review_id = Column(Integer)
    
    # Error tracking
    error_message = Column(Text)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    posted_at = Column(DateTime(timezone=True))
    
    # Relationship to comments
    comments = relationship("ReviewComment", back_populates="review_session", cascade="all, delete-orphan")
    
    # Composite index for lookups
    __table_args__ = (
        Index('ix_review_session_pr_lookup', 'org', 'repo', 'pr_number'),
    )


class ReviewComment(Base):
    """
    Individual review comment for a specific line in a file.
    
    Supports both single-line and multi-line comments.
    All comments are stored here before being posted to GitHub.
    """
    __tablename__ = "review_comments"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # Foreign key to review session
    review_session_id = Column(Integer, ForeignKey("review_sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # File location
    file_path = Column(String(512), nullable=False)
    
    # Line numbers (for multi-line comments, start_line < line)
    line = Column(Integer, nullable=False)  # End line (or single line)
    start_line = Column(Integer)  # Start line for multi-line comments (optional)
    
    # Side of the diff (LEFT = old code, RIGHT = new code)
    # For added lines, use RIGHT. For context lines in new file, use RIGHT.
    side = Column(String(8), default="RIGHT")
    start_side = Column(String(8))  # For multi-line comments
    
    # Comment content
    title = Column(String(512))  # Short title/summary
    body = Column(Text, nullable=False)  # Full comment body (markdown)
    
    # Classification
    severity = Column(String(32), default=CommentSeverity.MEDIUM.value)
    category = Column(String(32), default=CommentCategory.OTHER.value)
    
    # Suggestion (optional code suggestion)
    suggestion = Column(Text)  # Suggested code fix
    
    # GitHub comment ID (set after posting)
    github_comment_id = Column(Integer)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationship back to session
    review_session = relationship("ReviewSession", back_populates="comments")
    
    # Index for file lookups
    __table_args__ = (
        Index('ix_review_comment_file', 'review_session_id', 'file_path'),
    )