from sqlalchemy import Column, Boolean, Integer, String, ARRAY, Text, DateTime, Float
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
    changed_files = Column(ARRAY(String), default=None)


class ReviewFeedback(Base):
    """
    Stores user feedback on AI-generated review comments.
    
    Feedback types:
    - reaction: User reacted with emoji (👍, 👎, etc.)
    - reply: User replied with correction/suggestion
    - command: User used @open-rabbit command
    
    This data is processed by FeedbackProcessor agent and 
    converted to learnings stored in the Knowledge Base.
    """
    __tablename__ = "review_feedback"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # GitHub identifiers
    comment_id = Column(String(64), index=True, nullable=False)  # GitHub comment ID
    review_session_id = Column(String(64), index=True)  # Links to agent checkpoint
    
    # Repository context
    owner = Column(String(255), index=True, nullable=False)
    repo = Column(String(255), index=True, nullable=False)
    pr_number = Column(Integer, index=True, nullable=False)
    
    # Comment context
    file_path = Column(String(512))  # File the comment was on
    line_number = Column(Integer)  # Line number
    ai_comment = Column(Text, nullable=False)  # The AI-generated comment
    
    # Feedback data
    feedback_type = Column(String(32), index=True, nullable=False)  # reaction, reply, command
    reaction_type = Column(String(32))  # thumbs_up, thumbs_down, etc.
    user_feedback = Column(Text)  # User's reply text or command
    github_user = Column(String(255), index=True)  # Who gave feedback
    
    # Reaction weighting
    # Positive: 👍, ❤️, 🎉, 🚀 = +1.0
    # Negative: 👎, 😕 = -1.0
    # Neutral: 👀, ❓ = 0
    reaction_weight = Column(Float, default=0.0)
    
    # Processing status
    processed = Column(Boolean, default=False, index=True)  # Converted to KB learning
    learning_id = Column(String(64))  # ID of created learning in KB
    
    # Extracted learning (filled by FeedbackProcessor)
    extracted_learning = Column(Text)  # The learning statement
    learning_category = Column(String(64))  # security, style, performance, etc.
    learning_type = Column(String(64))  # correction, false_positive, style_preference, etc.
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    processed_at = Column(DateTime(timezone=True))


class KBLearning(Base):
    """
    Local cache/tracking of learnings sent to Knowledge Base.
    The actual learning content is stored in Elasticsearch via KB service.
    This table tracks what we've sent and allows for local queries.
    """
    __tablename__ = "kb_learnings"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # KB identifiers
    kb_id = Column(String(64), unique=True, index=True)  # ID from KB service
    
    # Scope
    scope = Column(String(32), default="repo", index=True)  # repo, org, global
    owner = Column(String(255), index=True)
    repo = Column(String(255), index=True)
    
    # Learning content
    learning = Column(Text, nullable=False)
    category = Column(String(64), index=True)  # security, style, performance, etc.
    learning_type = Column(String(64), index=True)  # correction, false_positive, etc.
    language = Column(String(64), index=True)  # python, typescript, etc.
    file_pattern = Column(String(255))  # *.test.ts, etc.
    
    # Source
    source_pr = Column(String(255))  # owner/repo#123
    source_feedback_id = Column(Integer)  # Links to ReviewFeedback.id
    learnt_from = Column(String(255))  # GitHub username
    
    # Confidence (updated based on feedback)
    confidence = Column(Float, default=0.5)
    positive_reactions = Column(Integer, default=0)
    negative_reactions = Column(Integer, default=0)
    
    # Status
    active = Column(Boolean, default=True, index=True)  # Can be disabled
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())