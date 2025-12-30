from sqlalchemy.orm import Session
from sqlalchemy import and_, or_
from typing import List, Optional
from datetime import datetime
from . import models, schemas


# ===== User CRUD =====

def get_user(db: Session, user_name: str):
    return db.query(models.User).filter(models.User.name == user_name).first()

def check_owner_exists(db: Session, owner_name: str):
    """Check if owner exists in either User or NewInstall table"""
    user_exists = db.query(models.User).filter(models.User.name == owner_name).first()
    if user_exists:
        return True
    install_exists = db.query(models.NewInstall).filter(models.NewInstall.name == owner_name).first()
    return install_exists is not None

# def get_users(db: Session, skip: int = 0, limit: int = 10):
#     return db.query(models.User).offset(skip).limit(limit).all()

def create_install(db:Session, user: schemas.UserCreate):
    new_user = models.NewInstall(name=user.name, org=user.org)
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user

def create_user(db: Session, user: schemas.UserCreate):
    db_user = models.User(name=user.name, email=user.email, org=user.org, sub=user.sub)
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user

def create_pr(db: Session, pr: schemas.PRBase):
    pr_data = models.PullRequest(org= pr.org, repo = pr.repo, pr_no=pr.pr_no, branch=pr.branch)
    db.add(pr_data)
    db.commit()
    db.refresh(pr_data)
    return pr_data
    
def update_pr(db: Session, pr_no: schemas.PRBase):
    pr_data = db.query(models.PullRequest).filter(models.PullRequest.pr_no == pr_no).first()

    if not pr_data:
        return None  
    
    setattr(pr_data, 'cnt', pr_data.cnt + 1)
    db.commit()
    db.refresh(pr_data)
    return pr_data

def insert_files(db: Session, payload: schemas.ChangedFileReq):
    files_data = db.query(models.PullRequest).filter(models.PullRequest.pr_no == payload.pr_no).first()
    
    if not files_data:
        return None  
    
    setattr(files_data, 'changed_files', payload.changedFiles)
    db.commit()
    db.refresh(files_data)


# ===== Feedback CRUD =====

def create_feedback(db: Session, feedback: schemas.FeedbackCreate) -> models.ReviewFeedback:
    """Create a new feedback record from user reaction/reply."""
    # Calculate reaction weight
    reaction_weight = 0.0
    if feedback.reaction_type:
        reaction_weight = schemas.REACTION_WEIGHTS.get(
            schemas.ReactionType(feedback.reaction_type), 0.0
        )
    
    db_feedback = models.ReviewFeedback(
        comment_id=feedback.comment_id,
        review_session_id=feedback.review_session_id,
        owner=feedback.owner,
        repo=feedback.repo,
        pr_number=feedback.pr_number,
        file_path=feedback.file_path,
        line_number=feedback.line_number,
        ai_comment=feedback.ai_comment,
        feedback_type=feedback.feedback_type,
        reaction_type=feedback.reaction_type,
        user_feedback=feedback.user_feedback,
        github_user=feedback.github_user,
        reaction_weight=reaction_weight,
        processed=False
    )
    
    db.add(db_feedback)
    db.commit()
    db.refresh(db_feedback)
    return db_feedback


def get_feedback_by_id(db: Session, feedback_id: int) -> Optional[models.ReviewFeedback]:
    """Get feedback by ID."""
    return db.query(models.ReviewFeedback).filter(
        models.ReviewFeedback.id == feedback_id
    ).first()


def get_feedback_by_comment_id(
    db: Session, 
    comment_id: str,
    github_user: Optional[str] = None
) -> Optional[models.ReviewFeedback]:
    """Get feedback by GitHub comment ID, optionally filtered by user."""
    query = db.query(models.ReviewFeedback).filter(
        models.ReviewFeedback.comment_id == comment_id
    )
    if github_user:
        query = query.filter(models.ReviewFeedback.github_user == github_user)
    return query.first()


def get_unprocessed_feedback(
    db: Session, 
    limit: int = 50,
    owner: Optional[str] = None,
    repo: Optional[str] = None
) -> List[models.ReviewFeedback]:
    """Get unprocessed feedback records for processing."""
    query = db.query(models.ReviewFeedback).filter(
        models.ReviewFeedback.processed == False
    )
    
    if owner:
        query = query.filter(models.ReviewFeedback.owner == owner)
    if repo:
        query = query.filter(models.ReviewFeedback.repo == repo)
    
    return query.order_by(models.ReviewFeedback.created_at.asc()).limit(limit).all()


def mark_feedback_processed(
    db: Session,
    feedback_id: int,
    learning_id: Optional[str] = None,
    extracted_learning: Optional[str] = None,
    learning_category: Optional[str] = None,
    learning_type: Optional[str] = None
) -> Optional[models.ReviewFeedback]:
    """Mark feedback as processed and store extracted learning info."""
    feedback = db.query(models.ReviewFeedback).filter(
        models.ReviewFeedback.id == feedback_id
    ).first()
    
    if not feedback:
        return None
    
    feedback.processed = True
    feedback.processed_at = datetime.utcnow()
    feedback.learning_id = learning_id
    feedback.extracted_learning = extracted_learning
    feedback.learning_category = learning_category
    feedback.learning_type = learning_type
    
    db.commit()
    db.refresh(feedback)
    return feedback


def get_feedback_stats(
    db: Session,
    owner: str,
    repo: str
) -> dict:
    """Get feedback statistics for a repo."""
    total = db.query(models.ReviewFeedback).filter(
        and_(
            models.ReviewFeedback.owner == owner,
            models.ReviewFeedback.repo == repo
        )
    ).count()
    
    processed = db.query(models.ReviewFeedback).filter(
        and_(
            models.ReviewFeedback.owner == owner,
            models.ReviewFeedback.repo == repo,
            models.ReviewFeedback.processed == True
        )
    ).count()
    
    # Sum of positive and negative reactions
    positive = db.query(models.ReviewFeedback).filter(
        and_(
            models.ReviewFeedback.owner == owner,
            models.ReviewFeedback.repo == repo,
            models.ReviewFeedback.reaction_weight > 0
        )
    ).count()
    
    negative = db.query(models.ReviewFeedback).filter(
        and_(
            models.ReviewFeedback.owner == owner,
            models.ReviewFeedback.repo == repo,
            models.ReviewFeedback.reaction_weight < 0
        )
    ).count()
    
    return {
        "total": total,
        "processed": processed,
        "pending": total - processed,
        "positive_reactions": positive,
        "negative_reactions": negative
    }


# ===== Learning CRUD =====

def create_learning(db: Session, learning: schemas.LearningCreate) -> models.KBLearning:
    """Create a new learning record (local cache of KB entry)."""
    db_learning = models.KBLearning(
        kb_id=learning.kb_id,
        scope=learning.scope,
        owner=learning.owner,
        repo=learning.repo,
        learning=learning.learning,
        category=learning.category,
        learning_type=learning.learning_type,
        language=learning.language,
        file_pattern=learning.file_pattern,
        source_pr=learning.source_pr,
        source_feedback_id=learning.source_feedback_id,
        learnt_from=learning.learnt_from,
        confidence=learning.confidence,
        positive_reactions=0,
        negative_reactions=0,
        active=True
    )
    
    db.add(db_learning)
    db.commit()
    db.refresh(db_learning)
    return db_learning


def get_learning_by_kb_id(db: Session, kb_id: str) -> Optional[models.KBLearning]:
    """Get learning by KB ID."""
    return db.query(models.KBLearning).filter(
        models.KBLearning.kb_id == kb_id
    ).first()


def get_learnings_for_repo(
    db: Session,
    owner: str,
    repo: str,
    category: Optional[str] = None,
    language: Optional[str] = None,
    min_confidence: float = 0.3,
    limit: int = 10,
    include_org_learnings: bool = True
) -> List[models.KBLearning]:
    """Get active learnings for a repo, optionally including org-level learnings."""
    # Build scope filter
    scope_conditions = [
        and_(
            models.KBLearning.scope == "repo",
            models.KBLearning.owner == owner,
            models.KBLearning.repo == repo
        )
    ]
    
    if include_org_learnings:
        scope_conditions.append(
            and_(
                models.KBLearning.scope == "org",
                models.KBLearning.owner == owner
            )
        )
        # Also include global learnings
        scope_conditions.append(models.KBLearning.scope == "global")
    
    query = db.query(models.KBLearning).filter(
        and_(
            models.KBLearning.active == True,
            models.KBLearning.confidence >= min_confidence,
            or_(*scope_conditions)
        )
    )
    
    if category:
        query = query.filter(models.KBLearning.category == category)
    if language:
        query = query.filter(models.KBLearning.language == language)
    
    return query.order_by(
        models.KBLearning.confidence.desc(),
        models.KBLearning.created_at.desc()
    ).limit(limit).all()


def update_learning_confidence(
    db: Session,
    kb_id: str,
    positive_delta: int = 0,
    negative_delta: int = 0
) -> Optional[models.KBLearning]:
    """Update learning confidence based on new reactions."""
    learning = db.query(models.KBLearning).filter(
        models.KBLearning.kb_id == kb_id
    ).first()
    
    if not learning:
        return None
    
    learning.positive_reactions += positive_delta
    learning.negative_reactions += negative_delta
    
    # Recalculate confidence (simple formula: positive / total with smoothing)
    total = learning.positive_reactions + learning.negative_reactions
    if total > 0:
        # Bayesian average with prior of 0.5
        learning.confidence = (learning.positive_reactions + 1) / (total + 2)
    
    # Deactivate if too many negative reactions
    if learning.negative_reactions >= 5 and learning.confidence < 0.3:
        learning.active = False
    
    db.commit()
    db.refresh(learning)
    return learning


def deactivate_learning(db: Session, kb_id: str) -> Optional[models.KBLearning]:
    """Deactivate a learning (soft delete)."""
    learning = db.query(models.KBLearning).filter(
        models.KBLearning.kb_id == kb_id
    ).first()
    
    if not learning:
        return None
    
    learning.active = False
    db.commit()
    db.refresh(learning)
    return learning


def get_learning_stats(db: Session, owner: str, repo: str) -> dict:
    """Get learning statistics for a repo."""
    total = db.query(models.KBLearning).filter(
        and_(
            models.KBLearning.owner == owner,
            models.KBLearning.repo == repo
        )
    ).count()
    
    active = db.query(models.KBLearning).filter(
        and_(
            models.KBLearning.owner == owner,
            models.KBLearning.repo == repo,
            models.KBLearning.active == True
        )
    ).count()
    
    # Count by category
    from sqlalchemy import func
    categories = db.query(
        models.KBLearning.category,
        func.count(models.KBLearning.id)
    ).filter(
        and_(
            models.KBLearning.owner == owner,
            models.KBLearning.repo == repo,
            models.KBLearning.active == True
        )
    ).group_by(models.KBLearning.category).all()
    
    return {
        "total": total,
        "active": active,
        "inactive": total - active,
        "by_category": {cat: count for cat, count in categories}
    }