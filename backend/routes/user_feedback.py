"""
User Feedback Routes

API endpoints for handling user feedback on AI review comments.
This module receives feedback from the bot webhook and processes it
through the FeedbackProcessor agent.
"""

import os
import sys
import uuid
import logging
from typing import Optional, List, Any
from datetime import datetime

from fastapi import APIRouter, HTTPException, BackgroundTasks, Depends
from sqlalchemy.orm import Session

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db.database import get_db
from db import crud, schemas

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/user-feedback", tags=["user-feedback"])

# Lazy load feedback processor to avoid import issues at module level
_feedback_processor = None
_kb_client = None


def get_feedback_processor():
    """Get feedback processor instance (lazy loaded)"""
    global _feedback_processor
    if _feedback_processor is None:
        from agent.subagents.feedback_agent import FeedbackProcessor
        USE_MOCK_LLM = os.getenv("USE_MOCK_LLM", "true").lower() == "true"
        _feedback_processor = FeedbackProcessor(use_mock=USE_MOCK_LLM)
    return _feedback_processor


def get_kb_client_instance():
    """Get KB client instance (lazy loaded)"""
    global _kb_client
    if _kb_client is None:
        from agent.services.kb_client import get_kb_client
        _kb_client = get_kb_client()
    return _kb_client


# ===== Feedback Submission Endpoints =====

@router.post("/submit", response_model=schemas.FeedbackResponse)
async def submit_feedback(
    feedback: schemas.FeedbackCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """
    Submit user feedback on an AI review comment.
    
    This endpoint is called by the bot when a user:
    - Reacts to a review comment (thumbs up/down, etc.)
    - Replies to a review comment
    - Uses a command like @open-rabbit learn
    
    The feedback is stored and processed in the background.
    """
    logger.info(
        f"Received feedback: type={feedback.feedback_type}, "
        f"repo={feedback.owner}/{feedback.repo}, "
        f"user={feedback.github_user}"
    )
    
    # Check if feedback already exists for this comment/user combo
    existing = crud.get_feedback_by_comment_id(
        db, 
        feedback.comment_id, 
        feedback.github_user
    )
    
    if existing:
        # Update existing feedback instead of creating duplicate
        logger.info(f"Updating existing feedback {existing.id}")
        # For now, just return existing - could implement update logic
        return existing
    
    # Create new feedback record
    db_feedback = crud.create_feedback(db, feedback)
    
    # Process feedback in background
    feedback_id: int = int(db_feedback.id)  # type: ignore
    background_tasks.add_task(
        process_feedback_background,
        feedback_id,
        feedback.dict()
    )
    
    return db_feedback


@router.post("/batch", response_model=dict)
async def submit_batch_feedback(
    feedbacks: List[schemas.FeedbackCreate],
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """
    Submit multiple feedback items in a batch.
    
    Useful for syncing historical feedback or bulk operations.
    """
    created: List[int] = []
    skipped: List[str] = []
    
    for feedback in feedbacks:
        existing = crud.get_feedback_by_comment_id(
            db,
            feedback.comment_id,
            feedback.github_user
        )
        
        if existing:
            skipped.append(feedback.comment_id)
            continue
        
        db_feedback = crud.create_feedback(db, feedback)
        feedback_id: int = int(db_feedback.id)  # type: ignore
        created.append(feedback_id)
        
        # Queue for processing
        background_tasks.add_task(
            process_feedback_background,
            feedback_id,
            feedback.dict()
        )
    
    return {
        "created": len(created),
        "skipped": len(skipped),
        "feedback_ids": created
    }


# ===== Feedback Query Endpoints =====

@router.get("/unprocessed")
async def get_unprocessed_feedback(
    owner: Optional[str] = None,
    repo: Optional[str] = None,
    limit: int = 50,
    db: Session = Depends(get_db)
):
    """Get unprocessed feedback items."""
    items = crud.get_unprocessed_feedback(db, limit, owner, repo)
    return {
        "count": len(items),
        "items": [schemas.FeedbackResponse.from_orm(item) for item in items]
    }


@router.get("/stats/{owner}/{repo}")
async def get_feedback_stats(
    owner: str,
    repo: str,
    db: Session = Depends(get_db)
):
    """Get feedback statistics for a repository."""
    feedback_stats = crud.get_feedback_stats(db, owner, repo)
    learning_stats = crud.get_learning_stats(db, owner, repo)
    
    return {
        "repository": f"{owner}/{repo}",
        "feedback": feedback_stats,
        "learnings": learning_stats
    }


@router.get("/{feedback_id}", response_model=schemas.FeedbackResponse)
async def get_feedback(
    feedback_id: int,
    db: Session = Depends(get_db)
):
    """Get a specific feedback item by ID."""
    feedback = crud.get_feedback_by_id(db, feedback_id)
    if not feedback:
        raise HTTPException(status_code=404, detail="Feedback not found")
    return feedback


# ===== Learning Endpoints =====

@router.get("/learnings/{owner}/{repo}")
async def get_repo_learnings(
    owner: str,
    repo: str,
    category: Optional[str] = None,
    language: Optional[str] = None,
    min_confidence: float = 0.3,
    limit: int = 20,
    db: Session = Depends(get_db)
):
    """Get learnings for a repository."""
    learnings = crud.get_learnings_for_repo(
        db,
        owner=owner,
        repo=repo,
        category=category,
        language=language,
        min_confidence=min_confidence,
        limit=limit
    )
    
    return {
        "repository": f"{owner}/{repo}",
        "count": len(learnings),
        "learnings": [schemas.LearningResponse.from_orm(l) for l in learnings]
    }


@router.post("/learnings/{kb_id}/feedback")
async def update_learning_feedback_endpoint(
    kb_id: str,
    positive: bool,
    db: Session = Depends(get_db)
):
    """Update a learning based on additional feedback."""
    # Update local cache
    updated = crud.update_learning_confidence(
        db,
        kb_id,
        positive_delta=1 if positive else 0,
        negative_delta=0 if positive else 1
    )
    
    if not updated:
        raise HTTPException(status_code=404, detail="Learning not found")
    
    # Update KB service
    kb_client = get_kb_client_instance()
    kb_client.update_learning_feedback(kb_id, positive)
    
    return {
        "kb_id": kb_id,
        "new_confidence": updated.confidence,
        "active": updated.active
    }


@router.delete("/learnings/{kb_id}")
async def deactivate_learning_endpoint(
    kb_id: str,
    db: Session = Depends(get_db)
):
    """Deactivate a learning (soft delete)."""
    # Deactivate locally
    learning = crud.deactivate_learning(db, kb_id)
    
    if not learning:
        raise HTTPException(status_code=404, detail="Learning not found")
    
    # Deactivate in KB
    kb_client = get_kb_client_instance()
    kb_client.deactivate_learning(kb_id)
    
    return {"message": f"Learning {kb_id} deactivated"}


# ===== Processing Endpoints =====

@router.post("/process/{feedback_id}")
async def process_single_feedback(
    feedback_id: int,
    db: Session = Depends(get_db)
):
    """Manually trigger processing of a feedback item."""
    feedback = crud.get_feedback_by_id(db, feedback_id)
    
    if not feedback:
        raise HTTPException(status_code=404, detail="Feedback not found")
    
    # Check if already processed
    if bool(feedback.processed):  # type: ignore
        return {
            "message": "Already processed",
            "learning_id": feedback.learning_id,
            "learning": feedback.extracted_learning
        }
    
    # Process synchronously
    result = await process_feedback_sync(db, feedback)
    
    return result


@router.post("/process-batch")
async def process_batch_feedback(
    background_tasks: BackgroundTasks,
    owner: Optional[str] = None,
    repo: Optional[str] = None,
    limit: int = 20,
    db: Session = Depends(get_db)
):
    """
    Process a batch of unprocessed feedback items.
    
    Can filter by owner/repo and limit number processed.
    """
    items = crud.get_unprocessed_feedback(db, limit, owner, repo)
    
    if not items:
        return {"message": "No unprocessed feedback", "processed": 0}
    
    processed_ids: List[int] = []
    for item in items:
        item_id: int = int(item.id)  # type: ignore
        background_tasks.add_task(
            process_feedback_background,
            item_id,
            {
                "comment_id": item.comment_id,
                "ai_comment": item.ai_comment,
                "feedback_type": item.feedback_type,
                "reaction_type": item.reaction_type,
                "user_feedback": item.user_feedback,
                "file_path": item.file_path,
                "owner": item.owner,
                "repo": item.repo,
                "pr_number": item.pr_number,
                "github_user": item.github_user
            }
        )
        processed_ids.append(item_id)
    
    return {
        "message": f"Processing {len(processed_ids)} feedback items",
        "feedback_ids": processed_ids
    }


# ===== Background Processing =====

async def process_feedback_background(feedback_id: int, feedback_data: dict):
    """Background task to process feedback and store learning."""
    from db.database import SessionLocal
    
    db = SessionLocal()
    try:
        feedback = crud.get_feedback_by_id(db, feedback_id)
        if not feedback:
            return
        
        # Check if already processed
        if bool(feedback.processed):  # type: ignore
            return
        
        await process_feedback_sync(db, feedback)
        
    except Exception as e:
        logger.error(f"Error processing feedback {feedback_id}: {e}")
    finally:
        db.close()


async def process_feedback_sync(db: Session, feedback: Any) -> dict:
    """
    Process a single feedback item synchronously.
    
    1. Use FeedbackProcessor to extract learning
    2. Store learning in KB if applicable
    3. Update local database
    """
    feedback_id: int = int(feedback.id)  # type: ignore
    logger.info(f"Processing feedback {feedback_id}: {feedback.feedback_type}")
    
    # Extract learning using LLM
    processor = get_feedback_processor()
    result = processor.process_feedback(
        ai_comment=str(feedback.ai_comment),
        feedback_type=str(feedback.feedback_type),
        user_feedback=str(feedback.user_feedback) if feedback.user_feedback else None,
        reaction_type=str(feedback.reaction_type) if feedback.reaction_type else None,
        file_path=str(feedback.file_path) if feedback.file_path else None,
        owner=str(feedback.owner),
        repo=str(feedback.repo)
    )
    
    learning_id: Optional[str] = None
    
    # Store in KB if learning should be created
    if result.get("should_create_learning") and result.get("learning"):
        kb_client = get_kb_client_instance()
        
        pr_number: int = int(feedback.pr_number)  # type: ignore
        kb_result = kb_client.store_learning(
            learning=result["learning"],
            category=result.get("category", "other"),
            learning_type=result.get("learning_type", "clarification"),
            owner=str(feedback.owner),
            repo=str(feedback.repo),
            source_pr=f"{feedback.owner}/{feedback.repo}#{pr_number}",
            learnt_from=str(feedback.github_user),
            confidence=result.get("confidence", 0.5),
            language=result.get("language"),
            file_pattern=result.get("file_pattern"),
            scope="repo"
        )
        
        if kb_result:
            learning_id = kb_result.get("learning_id")
            
            # Store local cache of learning
            learning_create = schemas.LearningCreate(
                kb_id=learning_id or str(uuid.uuid4()),
                scope=schemas.LearningScope.REPO,
                owner=str(feedback.owner),
                repo=str(feedback.repo),
                learning=result["learning"],
                category=schemas.LearningCategory(result.get("category", "other")),
                learning_type=schemas.LearningType(result.get("learning_type", "clarification")),
                language=result.get("language"),
                file_pattern=result.get("file_pattern"),
                source_pr=f"{feedback.owner}/{feedback.repo}#{pr_number}",
                source_feedback_id=feedback_id,
                learnt_from=str(feedback.github_user),
                confidence=result.get("confidence", 0.5)
            )
            
            try:
                crud.create_learning(db, learning_create)
            except Exception as e:
                logger.error(f"Failed to create local learning record: {e}")
    
    # Mark feedback as processed
    crud.mark_feedback_processed(
        db,
        feedback_id,
        learning_id=learning_id,
        extracted_learning=result.get("learning"),
        learning_category=result.get("category"),
        learning_type=result.get("learning_type")
    )
    
    logger.info(
        f"Processed feedback {feedback_id}: "
        f"learning_created={result.get('should_create_learning')}, "
        f"learning_id={learning_id}"
    )
    
    return {
        "feedback_id": feedback_id,
        "processed": True,
        "should_create_learning": result.get("should_create_learning"),
        "learning_id": learning_id,
        "learning": result.get("learning"),
        "learning_type": result.get("learning_type"),
        "category": result.get("category"),
        "confidence": result.get("confidence"),
        "reasoning": result.get("reasoning")
    }
