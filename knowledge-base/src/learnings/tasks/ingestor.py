"""
Celery-based asynchronous ingestion pipeline.

Handles the end-to-end processing of review comments into learnings:
1. Extract learning from raw comment
2. Generate embedding
3. Store in vector database

This runs as a background task to avoid blocking the API.
"""

import uuid
from datetime import datetime

from celery import Celery
from celery.utils.log import get_task_logger

from src.learnings.core.models import ReviewComment, Learning
from src.learnings.core.extractor import LearningExtractor
from src.learnings.core.storage import LearningStorage
from src.learnings.core.config import get_settings

# Initialize logger
logger = get_task_logger(__name__)

# Initialize settings
settings = get_settings()

# Initialize Celery app
celery_app = Celery(
    "learnings-worker",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend
)

# Configure Celery
celery_app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
    task_track_started=True,
    task_time_limit=300,  # 5 minutes max per task
    worker_prefetch_multiplier=4,
    worker_max_tasks_per_child=1000,
)


# Initialize dependencies (singleton pattern for workers)
_extractor = None
_storage = None


def get_extractor() -> LearningExtractor:
    """Lazy initialization of extractor."""
    global _extractor
    if _extractor is None:
        _extractor = LearningExtractor(settings)
    return _extractor


def get_storage() -> LearningStorage:
    """Lazy initialization of storage."""
    global _storage
    if _storage is None:
        _storage = LearningStorage(settings)
    return _storage


def _process_single_learning(comment_data: dict) -> dict:
    """
    Core logic for processing a single learning.
    
    This is a helper function that can be called directly (for batch processing)
    or via Celery task (for async processing).
    """
    logger.info(f"Processing comment {comment_data.get('comment_id')}")
    
    # Deserialize comment
    comment = ReviewComment(**comment_data)
    
    # Extract learning
    extractor = get_extractor()
    learning_text = extractor.extract_learning(
        raw_comment=comment.raw_comment,
        code_snippet=comment.code_snippet,
        language=comment.language
    )
    
    # Check if extraction yielded a valid learning
    if not learning_text:
        logger.info(f"No actionable learning extracted from comment {comment.comment_id}")
        return {
            "status": "skipped",
            "reason": "Comment not actionable or too trivial",
            "comment_id": comment.comment_id
        }
    
    # Create Learning object
    learning = Learning(
        learning_id=str(uuid.uuid4()),
        learning_text=learning_text,
        original_comment=comment.raw_comment,
        code_context=comment.code_snippet,
        language=comment.language,
        source=comment.source,
        feedback_type=comment.feedback_type,
        confidence_score=_calculate_confidence_score(comment),
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )
    
    # Store learning (embedding generated internally)
    storage = get_storage()
    learning_id = storage.store_learning(learning)
    
    logger.info(f"Successfully ingested learning {learning_id}")
    
    return {
        "status": "success",
        "learning_id": learning_id,
        "learning_text": learning_text,
        "comment_id": comment.comment_id
    }


@celery_app.task(name="ingest_learning", bind=True, max_retries=3)
def ingest_learning_task(self, comment_data: dict) -> dict:
    """
    Main ingestion task: processes a review comment into a learning.
    
    This is the core async pipeline that:
    1. Validates the comment payload
    2. Extracts a normalized learning using LLM
    3. Generates embedding
    4. Stores in vector database
    
    Args:
        comment_data: Serialized ReviewComment dict
    
    Returns:
        Dict with status and learning_id if successful
    
    Retry logic:
    - Retries up to 3 times on failure (network issues, LLM timeouts)
    - Uses exponential backoff
    """
    try:
        return _process_single_learning(comment_data)
    except Exception as exc:
        logger.error(f"Error ingesting learning: {exc}")
        # Retry with exponential backoff
        raise self.retry(exc=exc, countdown=2 ** self.request.retries)


@celery_app.task(name="batch_ingest_learnings")
def batch_ingest_learnings_task(comments_data: list[dict]) -> dict:
    """
    Batch ingestion task for processing multiple comments efficiently.
    
    This is more efficient than individual tasks for bulk imports
    (e.g., importing historical review data).
    
    Args:
        comments_data: List of serialized ReviewComment dicts
    
    Returns:
        Summary with counts and any errors
    """
    logger.info(f"Processing batch of {len(comments_data)} comments")
    
    results = {
        "total": len(comments_data),
        "successful": 0,
        "skipped": 0,
        "failed": 0,
        "errors": []
    }
    
    for comment_data in comments_data:
        try:
            result = _process_single_learning(comment_data)
            
            if result["status"] == "success":
                results["successful"] += 1
            elif result["status"] == "skipped":
                results["skipped"] += 1
                
        except Exception as e:
            results["failed"] += 1
            results["errors"].append({
                "comment_id": comment_data.get("comment_id"),
                "error": str(e)
            })
    
    logger.info(f"Batch processing complete: {results['successful']} successful, "
                f"{results['skipped']} skipped, {results['failed']} failed")
    
    return results


def _calculate_confidence_score(comment: ReviewComment) -> float:
    """
    Calculate confidence score based on comment metadata.
    
    Factors:
    - Feedback type (accepted > modified > debated > rejected)
    - Comment length (too short or too long = lower confidence)
    - Presence of code context
    - Author reputation (future enhancement)
    
    Returns:
        Score between 0.0 and 1.0
    """
    score = 0.7  # Base score
    
    # Boost for positive feedback
    if comment.feedback_type:
        feedback_boost = {
            "ACCEPTED": 0.2,
            "THANKED": 0.15,
            "MODIFIED": 0.1,
            "DEBATED": 0.0,
            "REJECTED": -0.3,
            "IGNORED": -0.1
        }
        score += feedback_boost.get(comment.feedback_type.value.upper(), 0.0)
    
    # Boost for having code context
    if comment.code_snippet and len(comment.code_snippet) > 20:
        score += 0.1
    
    # Penalize very short comments
    if len(comment.raw_comment) < 20:
        score -= 0.2
    
    # Clamp to [0, 1]
    return max(0.0, min(1.0, score))


# Health check task
@celery_app.task(name="health_check")
def health_check_task() -> dict:
    """
    Simple health check task to verify worker is running.
    """
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "worker": "learnings-worker"
    }
