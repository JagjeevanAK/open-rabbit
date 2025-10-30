"""
FastAPI routes for the Learnings API.

Provides REST endpoints for:
- Ingesting review comments (async via Celery)
- Searching for relevant learnings
- Health checks and monitoring
"""

from typing import Optional
from fastapi import FastAPI, HTTPException, Depends, Query
from fastapi.responses import JSONResponse

from src.learnings.core.models import (
    ReviewComment,
    IngestionRequest,
    IngestionResponse,
    LearningSearchRequest,
    LearningSearchResponse,
    Learning
)
from src.learnings.tasks.ingestor import (
    celery_app,
    ingest_learning_task,
    batch_ingest_learnings_task,
    health_check_task
)
from src.learnings.core.retriever import LearningRetriever
from src.learnings.core.storage import LearningStorage
from src.learnings.core.config import get_settings

# Initialize FastAPI app
settings = get_settings()

app = FastAPI(
    title=settings.api_title,
    description=settings.api_description,
    version=settings.api_version,
    docs_url="/docs",
    redoc_url="/redoc"
)

# Dependency injection for storage and retriever
def get_storage() -> LearningStorage:
    """Dependency: Storage instance."""
    return LearningStorage(settings)


def get_retriever(storage: LearningStorage = Depends(get_storage)) -> LearningRetriever:
    """Dependency: Retriever instance."""
    return LearningRetriever(storage, settings)


# ============================================================================
# INGESTION ENDPOINTS
# ============================================================================

@app.post("/learnings/ingest", response_model=IngestionResponse, tags=["Ingestion"])
async def ingest_learning(request: IngestionRequest):
    """
    Ingest a review comment for learning extraction.
    
    This endpoint receives a review comment payload and either:
    - Queues it for async processing via Celery (default)
    - Processes it synchronously (if async_processing=False)
    
    Example payload:
    ```json
    {
        "comment": {
            "comment_id": "c123",
            "raw_comment": "Use const instead of let for immutable variables.",
            "code_snippet": "let x = 10;",
            "language": "javascript",
            "source": {
                "repo_name": "acme/web-app",
                "pr_number": 1234,
                "file_path": "src/app.js",
                "author": "coderabbit-bot"
            }
        },
        "async_processing": true
    }
    ```
    
    Returns:
    - task_id if async
    - learning_id if sync and successful
    """
    try:
        # Serialize comment for Celery
        comment_data = request.comment.model_dump()
        
        if request.async_processing:
            # Queue for async processing
            task = ingest_learning_task.apply_async(args=[comment_data])  # type: ignore
            
            return IngestionResponse(
                task_id=task.id,
                status="queued",
                learning_id=None
            )
        else:
            # Process synchronously (blocking)
            # Call the task function directly (bypassing Celery)
            from src.learnings.tasks.ingestor import get_extractor, get_storage
            from src.learnings.core.models import ReviewComment, Learning, FeedbackType
            import uuid
            from datetime import datetime
            
            comment = ReviewComment(**comment_data)
            extractor = get_extractor()
            learning_text = extractor.extract_learning(
                raw_comment=comment.raw_comment,
                code_snippet=comment.code_snippet,
                language=comment.language
            )
            
            if not learning_text:
                return IngestionResponse(
                    task_id=None,
                    status="skipped",
                    learning_id=None
                )
            
            learning = Learning(
                learning_id=str(uuid.uuid4()),
                learning_text=learning_text,
                original_comment=comment.raw_comment,
                code_context=comment.code_snippet,
                language=comment.language,
                source=comment.source,
                feedback_type=comment.feedback_type,
                confidence_score=0.8,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
            
            storage_instance = get_storage()
            learning_id = storage_instance.store_learning(learning)
            
            if learning_id:
                return IngestionResponse(
                    task_id=None,
                    status="success",
                    learning_id=learning_id
                )
            else:
                return IngestionResponse(
                    task_id=None,
                    status="skipped",
                    learning_id=None
                )
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ingestion failed: {str(e)}")


@app.get("/learnings/ingest/{task_id}", tags=["Ingestion"])
async def get_ingestion_status(task_id: str):
    """
    Check the status of an async ingestion task.
    
    Returns:
    - Task state (PENDING, SUCCESS, FAILURE, etc.)
    - Result if completed
    """
    task = celery_app.AsyncResult(task_id)
    
    response = {
        "task_id": task_id,
        "state": task.state,
        "result": task.result if task.ready() else None
    }
    
    if task.failed():
        response["error"] = str(task.info)
    
    return response


@app.post("/learnings/ingest/batch", tags=["Ingestion"])
async def batch_ingest_learnings(comments: list[ReviewComment]):
    """
    Batch ingest multiple review comments.
    
    Useful for importing historical review data or processing
    multiple comments from a single PR review session.
    """
    try:
        comments_data = [c.model_dump() for c in comments]
        
        # Queue batch task
        task = batch_ingest_learnings_task.apply_async(args=[comments_data])  # type: ignore
        
        return {
            "task_id": task.id,
            "status": "queued",
            "total_comments": len(comments)
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Batch ingestion failed: {str(e)}")


# ============================================================================
# RETRIEVAL ENDPOINTS
# ============================================================================

@app.get("/learnings/search", response_model=LearningSearchResponse, tags=["Retrieval"])
async def search_learnings(
    q: str = Query(..., description="Search query text"),
    k: int = Query(5, ge=1, le=50, description="Number of results"),
    repo: Optional[str] = Query(None, description="Filter by repository"),
    language: Optional[str] = Query(None, description="Filter by language"),
    min_confidence: float = Query(0.0, ge=0.0, le=1.0, description="Minimum confidence score"),
    retriever: LearningRetriever = Depends(get_retriever)
):
    """
    Search for relevant learnings using semantic similarity.
    
    Example:
    ```
    GET /learnings/search?q=dependency%20updates&k=3&repo=acme/web-app
    ```
    
    Returns:
    - List of semantically similar learnings
    - Ranked by relevance
    - Filtered by metadata
    """
    try:
        request = LearningSearchRequest(
            query=q,
            k=k,
            repo_filter=repo,
            language_filter=language,
            min_confidence=min_confidence
        )
        
        response = retriever.search(request)
        
        return response
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")


@app.post("/learnings/pr-context", response_model=list[Learning], tags=["Retrieval"])
async def get_pr_context_learnings(
    pr_description: str,
    changed_files: list[str],
    repo_name: str,
    k: int = 5,
    retriever: LearningRetriever = Depends(get_retriever)
):
    """
    Retrieve learnings relevant to a specific PR context.
    
    This is the primary endpoint used by the review agent to inject
    context-aware learnings into review prompts.
    
    Example payload:
    ```json
    {
        "pr_description": "Add dependency update automation",
        "changed_files": ["package.json", "src/update.js"],
        "repo_name": "acme/web-app",
        "k": 5
    }
    ```
    
    Returns:
    - Learnings ranked by relevance to the PR
    - Prioritizes learnings from similar files
    """
    try:
        learnings = retriever.get_learnings_for_pr_context(
            pr_description=pr_description,
            changed_files=changed_files,
            repo_name=repo_name,
            k=k
        )
        
        return learnings
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"PR context retrieval failed: {str(e)}")


@app.get("/learnings/{learning_id}", response_model=Learning, tags=["Retrieval"])
async def get_learning_by_id(
    learning_id: str,
    storage: LearningStorage = Depends(get_storage)
):
    """
    Retrieve a specific learning by ID.
    """
    learning = storage.get_learning_by_id(learning_id)
    
    if not learning:
        raise HTTPException(status_code=404, detail=f"Learning {learning_id} not found")
    
    return learning


@app.delete("/learnings/{learning_id}", tags=["Management"])
async def delete_learning(
    learning_id: str,
    storage: LearningStorage = Depends(get_storage)
):
    """
    Delete a learning by ID.
    
    Use with caution - this is permanent.
    """
    success = storage.delete_learning(learning_id)
    
    if not success:
        raise HTTPException(status_code=404, detail=f"Learning {learning_id} not found")
    
    return {"status": "deleted", "learning_id": learning_id}


# ============================================================================
# MONITORING & HEALTH ENDPOINTS
# ============================================================================

@app.get("/health", tags=["Health"])
async def health_check():
    """
    Health check endpoint for load balancers and monitoring.
    """
    return {
        "status": "healthy",
        "service": "learnings-api",
        "version": settings.api_version
    }


@app.get("/stats", tags=["Health"])
async def get_stats(storage: LearningStorage = Depends(get_storage)):
    """
    Get statistics about the learnings collection.
    """
    try:
        stats = storage.get_collection_stats()
        
        return {
            "status": "ok",
            "stats": stats
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get stats: {str(e)}")


@app.get("/worker-health", tags=["Health"])
async def worker_health_check():
    """
    Check if Celery workers are running.
    """
    try:
        task = health_check_task.apply_async()  # type: ignore
        result = task.get(timeout=5)
        
        return {
            "status": "healthy",
            "workers": "online",
            "result": result
        }
    
    except Exception as e:
        return JSONResponse(
            status_code=503,
            content={
                "status": "unhealthy",
                "workers": "offline",
                "error": str(e)
            }
        )


# ============================================================================
# CONTEXT FORMATTING ENDPOINT (for LangGraph integration)
# ============================================================================

@app.post("/learnings/format-context", tags=["Integration"])
async def format_learnings_context(
    query: str,
    k: int = 5,
    repo: Optional[str] = None,
    retriever: LearningRetriever = Depends(get_retriever)
):
    """
    Retrieve and format learnings for LLM context injection.
    
    This endpoint is designed for LangGraph nodes that need to
    inject learnings into review prompts.
    
    Returns:
    - Formatted string ready to be inserted into LLM prompt
    
    Example response:
    ```
    ## Relevant Project Learnings:
    
    1. [JavaScript | package.json] 
       The project requires regular dependency updates with security audits.
       
    2. [Python | config.py] 
       The project enforces type hints on all function signatures.
    ```
    """
    try:
        request = LearningSearchRequest(
            query=query,
            k=k,
            repo_filter=repo,
            language_filter=None,
            min_confidence=0.5
        )
        
        response = retriever.search(request)
        formatted_context = retriever.format_for_context(response.results, max_learnings=k)
        
        return {
            "formatted_context": formatted_context,
            "total_learnings": len(response.results),
            "query": query
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Context formatting failed: {str(e)}")
