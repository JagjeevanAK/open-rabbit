from sqlalchemy import Column, Boolean, Integer, String, Text, DateTime, Index
from sqlalchemy.sql import func
from .database import Base

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