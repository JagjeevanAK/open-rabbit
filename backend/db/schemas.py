from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from enum import Enum


# ===== Enums =====

class FeedbackType(str, Enum):
    """Type of feedback from user"""
    REACTION = "reaction"
    REPLY = "reply"
    COMMAND = "command"


class ReactionType(str, Enum):
    """GitHub reaction types with their sentiment"""
    THUMBS_UP = "thumbs_up"      # +1 👍
    THUMBS_DOWN = "thumbs_down"  # -1 👎
    HEART = "heart"              # +1 ❤️
    HOORAY = "hooray"            # +1 🎉
    ROCKET = "rocket"            # +1 🚀
    CONFUSED = "confused"        # -1 😕
    EYES = "eyes"                # 0 👀
    LAUGH = "laugh"              # 0 😄


class LearningType(str, Enum):
    """Types of learnings extracted from feedback"""
    CORRECTION = "correction"           # User corrected our suggestion
    FALSE_POSITIVE = "false_positive"   # We flagged something that wasn't an issue
    STYLE_PREFERENCE = "style_preference"  # Team/org style preference
    BEST_PRACTICE = "best_practice"     # Established best practice
    CLARIFICATION = "clarification"     # Our comment was unclear
    APPRECIATION = "appreciation"       # Positive feedback worth noting


class LearningCategory(str, Enum):
    """Categories for learnings"""
    SECURITY = "security"
    PERFORMANCE = "performance"
    MAINTAINABILITY = "maintainability"
    STYLE = "style"
    TESTING = "testing"
    DOCUMENTATION = "documentation"
    ERROR_HANDLING = "error_handling"
    ARCHITECTURE = "architecture"
    NAMING = "naming"
    OTHER = "other"


class LearningScope(str, Enum):
    """Scope of a learning"""
    REPO = "repo"      # Applies to specific repo
    ORG = "org"        # Applies to entire org
    GLOBAL = "global"  # Applies globally


# ===== User Schemas =====

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


# ===== Feedback Schemas =====

# Reaction weight mapping
REACTION_WEIGHTS = {
    ReactionType.THUMBS_UP: 1.0,
    ReactionType.THUMBS_DOWN: -1.0,
    ReactionType.HEART: 1.0,
    ReactionType.HOORAY: 1.0,
    ReactionType.ROCKET: 1.0,
    ReactionType.CONFUSED: -1.0,
    ReactionType.EYES: 0.0,
    ReactionType.LAUGH: 0.0,
}


class FeedbackCreate(BaseModel):
    """Schema for creating feedback from webhook"""
    comment_id: str = Field(..., description="GitHub comment ID")
    review_session_id: Optional[str] = Field(None, description="Agent session ID")
    
    # Repository context
    owner: str = Field(..., description="Repository owner")
    repo: str = Field(..., description="Repository name")
    pr_number: int = Field(..., description="Pull request number")
    
    # Comment context
    file_path: Optional[str] = Field(None, description="File path for inline comments")
    line_number: Optional[int] = Field(None, description="Line number for inline comments")
    ai_comment: str = Field(..., description="The AI-generated comment")
    
    # Feedback data
    feedback_type: FeedbackType = Field(..., description="Type of feedback")
    reaction_type: Optional[ReactionType] = Field(None, description="Reaction emoji type")
    user_feedback: Optional[str] = Field(None, description="User's reply text")
    github_user: str = Field(..., description="GitHub username who gave feedback")
    
    class Config:
        use_enum_values = True


class FeedbackResponse(BaseModel):
    """Response schema for feedback"""
    id: int
    comment_id: str
    review_session_id: Optional[str]
    owner: str
    repo: str
    pr_number: int
    file_path: Optional[str]
    line_number: Optional[int]
    ai_comment: str
    feedback_type: str
    reaction_type: Optional[str]
    user_feedback: Optional[str]
    github_user: str
    reaction_weight: float
    processed: bool
    learning_id: Optional[str]
    extracted_learning: Optional[str]
    learning_category: Optional[str]
    learning_type: Optional[str]
    created_at: datetime
    processed_at: Optional[datetime]

    class Config:
        orm_mode = True


class FeedbackProcessResult(BaseModel):
    """Result of processing feedback through LLM"""
    learning: str = Field(..., description="Extracted learning statement")
    learning_type: LearningType = Field(..., description="Type of learning")
    category: LearningCategory = Field(..., description="Category of learning")
    confidence: float = Field(0.5, ge=0.0, le=1.0, description="Confidence score")
    language: Optional[str] = Field(None, description="Programming language if applicable")
    file_pattern: Optional[str] = Field(None, description="File pattern if applicable")
    
    class Config:
        use_enum_values = True


# ===== Learning Schemas =====

class LearningCreate(BaseModel):
    """Schema for creating a learning in KB"""
    kb_id: str = Field(..., description="ID from KB service")
    scope: LearningScope = Field(LearningScope.REPO, description="Scope of learning")
    owner: str = Field(..., description="Repository owner")
    repo: str = Field(..., description="Repository name")
    
    learning: str = Field(..., description="The learning statement")
    category: LearningCategory = Field(..., description="Category")
    learning_type: LearningType = Field(..., description="Type of learning")
    language: Optional[str] = Field(None, description="Programming language")
    file_pattern: Optional[str] = Field(None, description="File pattern")
    
    source_pr: str = Field(..., description="Source PR (owner/repo#number)")
    source_feedback_id: int = Field(..., description="ID of source feedback")
    learnt_from: str = Field(..., description="GitHub username")
    confidence: float = Field(0.5, ge=0.0, le=1.0)
    
    class Config:
        use_enum_values = True


class LearningResponse(BaseModel):
    """Response schema for learning"""
    id: int
    kb_id: str
    scope: str
    owner: str
    repo: str
    learning: str
    category: str
    learning_type: str
    language: Optional[str]
    file_pattern: Optional[str]
    source_pr: str
    source_feedback_id: int
    learnt_from: str
    confidence: float
    positive_reactions: int
    negative_reactions: int
    active: bool
    created_at: datetime
    updated_at: Optional[datetime]

    class Config:
        orm_mode = True


class LearningQuery(BaseModel):
    """Query parameters for searching learnings"""
    owner: str = Field(..., description="Repository owner")
    repo: str = Field(..., description="Repository name")
    category: Optional[LearningCategory] = Field(None, description="Filter by category")
    language: Optional[str] = Field(None, description="Filter by language")
    min_confidence: float = Field(0.3, ge=0.0, le=1.0)
    limit: int = Field(10, ge=1, le=100)
    include_org_learnings: bool = Field(True, description="Include org-level learnings")


class LearningListResponse(BaseModel):
    """Response for listing learnings"""
    learnings: List[LearningResponse]
    total: int
    query: LearningQuery
