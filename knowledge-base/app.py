from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from tasks import process_learning
from config import settings
from elasticsearch import Elasticsearch
from langchain_openai import OpenAIEmbeddings

app = FastAPI(
    title="Knowledge Base API",
    description="API for storing and retrieving code learnings",
    version="1.0.0"
)

es_client = Elasticsearch(settings.elasticsearch_url)
_embeddings = None

def get_embeddings():
    """Get embeddings instance (lazy loaded)."""
    global _embeddings
    if _embeddings is None:
        _embeddings = OpenAIEmbeddings(model=settings.openai_embedding_model)
    return _embeddings


class LearningRequest(BaseModel):
    """Request model for adding a new learning."""
    learning: str = Field(..., description="The learning or insight to store")
    learnt_from: Optional[str] = Field(None, description="Source or author of the learning")
    pr: Optional[str] = Field(None, description="Related PR reference (e.g., 'repo/project#123')")
    file: Optional[str] = Field(None, description="Related file reference (e.g., 'path/to/file.py:10-20')")
    timestamp: Optional[str] = Field(None, description="ISO format timestamp")
    
    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "learning": "The Zero project prefers to handle dependency updates through automated tools like Dependabot rather than manual updates.",
                    "learnt_from": "JagjeevanAK",
                    "pr": "Mail-0/Zero#1583",
                    "file": "apps/docs/package.json:1-0",
                    "timestamp": "2025-07-01T12:53:32.467Z"
                }
            ]
        }
    }


class LearningResponse(BaseModel):
    """Response model for learning submission."""
    status: str
    message: str
    task_id: str


class TaskStatusResponse(BaseModel):
    """Response model for task status."""
    task_id: str
    status: str
    result: Optional[dict] = None


class SearchResult(BaseModel):
    """A single search result."""
    learning_id: str
    learning: str
    learnt_from: Optional[str] = None
    pr: Optional[str] = None
    file: Optional[str] = None
    timestamp: Optional[str] = None
    score: float


class SearchResponse(BaseModel):
    """Response model for search queries."""
    query: str
    total: int
    learnings: List[SearchResult]


class PRContextRequest(BaseModel):
    """Request model for PR context learnings."""
    owner: str = Field(..., description="Repository owner")
    repo: str = Field(..., description="Repository name")
    pr_description: str = Field(..., description="PR title and description")
    changed_files: List[str] = Field(default=[], description="List of changed file paths")
    k: int = Field(default=10, description="Number of results to return")


def prepare_learning_data(learning: LearningRequest) -> dict:
    """Prepare learning data for processing."""
    learning_data = learning.model_dump()
    if not learning_data.get("timestamp"):
        learning_data["timestamp"] = datetime.utcnow().isoformat()
    return learning_data


@app.get("/")
async def root():
    """Health check endpoint."""
    return {
        "message": "Knowledge Base API is running",
        "version": "1.0.0",
        "docs": "/docs"
    }


@app.post("/learnings", response_model=LearningResponse)
async def add_learning(learning: LearningRequest):
    """
    Add a new learning to the knowledge base.
    
    The learning will be processed asynchronously:
    1. Embedded using OpenAI embeddings
    2. Stored in Elasticsearch
    
    Returns a task ID that can be used to check the processing status.
    """
    try:
        learning_data = prepare_learning_data(learning)
        task = process_learning.delay(learning_data)
        
        return LearningResponse(
            status="queued",
            message="Learning has been queued for processing",
            task_id=task.id
        )
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to queue learning: {str(e)}")


@app.get("/tasks/{task_id}", response_model=TaskStatusResponse)
async def get_task_status(task_id: str):
    """
    Get the status of a processing task.
    
    Returns:
        - PENDING: Task is waiting to be processed
        - STARTED: Task is being processed
        - SUCCESS: Task completed successfully
        - FAILURE: Task failed
    """
    from celery.result import AsyncResult
    
    task_result = AsyncResult(task_id)
    
    response = {
        "task_id": task_id,
        "status": task_result.status,
        "result": None
    }
    
    if task_result.ready():
        response["result"] = task_result.result
    
    return TaskStatusResponse(**response)


@app.post("/learnings/batch", response_model=list[LearningResponse])
async def add_learnings_batch(learnings: list[LearningRequest]):
    """
    Add multiple learnings to the knowledge base in batch.
    
    Each learning will be processed asynchronously.
    """
    responses = []
    
    for learning in learnings:
        try:
            learning_data = prepare_learning_data(learning)
            task = process_learning.delay(learning_data)
            
            responses.append(LearningResponse(
                status="queued",
                message="Learning has been queued for processing",
                task_id=task.id
            ))
        except Exception as e:
            responses.append(LearningResponse(
                status="error",
                message=f"Failed to queue learning: {str(e)}",
                task_id=""
            ))
    
    return responses


@app.get("/health")
async def health_check():
    """Health check endpoint for service discovery."""
    try:
        # Check Elasticsearch connection
        es_health = es_client.cluster.health()
        return {
            "status": "healthy",
            "elasticsearch": es_health.get("status", "unknown"),
            "version": "1.0.0"
        }
    except Exception as e:
        return {
            "status": "degraded",
            "error": str(e),
            "version": "1.0.0"
        }


@app.get("/learnings/search", response_model=SearchResponse)
async def search_learnings(
    q: str = Query(..., description="Search query"),
    k: int = Query(default=5, description="Number of results to return"),
    repo: Optional[str] = Query(default=None, description="Filter by repository (owner/repo)"),
    min_score: float = Query(default=0.5, description="Minimum similarity score (0-1)")
):
    """
    Search for relevant learnings using semantic similarity.
    
    Uses vector search with OpenAI embeddings to find the most relevant
    learnings based on the query text.
    """
    try:
        embeddings = get_embeddings()
        query_vector = embeddings.embed_query(q)
        
        search_query = {
            "knn": {
                "field": "embedding",
                "query_vector": query_vector,
                "k": k * 2,
                "num_candidates": 100
            },
            "_source": ["learning", "learnt_from", "pr", "file", "timestamp"]
        }
        
        # Add repo filter if specified
        if repo:
            search_query["knn"]["filter"] = {
                "wildcard": {
                    "pr": f"*{repo}*"
                }
            }
        
        # Execute search
        response = es_client.search(
            index=settings.index_name,
            body=search_query,
            size=k * 2
        )
        
        # Process results
        results = []
        for hit in response["hits"]["hits"]:
            score = hit["_score"]
            # Normalize score (kNN scores can vary)
            normalized_score = min(score, 1.0)
            
            if normalized_score >= min_score:
                source = hit["_source"]
                results.append(SearchResult(
                    learning_id=hit["_id"],
                    learning=source.get("learning", ""),
                    learnt_from=source.get("learnt_from"),
                    pr=source.get("pr"),
                    file=source.get("file"),
                    timestamp=source.get("timestamp"),
                    score=normalized_score
                ))
        
        # Limit to k results
        results = results[:k]
        
        return SearchResponse(
            query=q,
            total=len(results),
            learnings=results
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")


@app.post("/learnings/pr-context", response_model=SearchResponse)
async def get_pr_context_learnings(request: PRContextRequest):
    """
    Get learnings relevant to a PR context.
    
    Combines PR description and changed files to find the most relevant
    learnings for code review context.
    """
    try:
        # Build a context query from PR info
        context_parts = [request.pr_description]
        
        # Add file extensions and paths for context
        if request.changed_files:
            # Extract unique file extensions
            extensions = set()
            for f in request.changed_files[:10]:  # Limit files
                if "." in f:
                    ext = f.split(".")[-1]
                    extensions.add(ext)
            
            if extensions:
                context_parts.append(f"File types: {', '.join(extensions)}")
            
            # Add some file paths for context
            context_parts.append(f"Files: {', '.join(request.changed_files[:5])}")
        
        # Combine context
        query_text = " | ".join(context_parts)
        
        embeddings = get_embeddings()
        query_vector = embeddings.embed_query(query_text)
        
        # Build search with repo filter
        repo_pattern = f"*{request.owner}/{request.repo}*"
        
        search_query = {
            "knn": {
                "field": "embedding",
                "query_vector": query_vector,
                "k": request.k * 2,
                "num_candidates": 100,
                "filter": {
                    "bool": {
                        "should": [
                            {"wildcard": {"pr": repo_pattern}},
                            {"wildcard": {"pr": f"*{request.repo}*"}}
                        ]
                    }
                }
            },
            "_source": ["learning", "learnt_from", "pr", "file", "timestamp"]
        }
        
        # Execute search
        response = es_client.search(
            index=settings.index_name,
            body=search_query,
            size=request.k * 2
        )
        
        results = []
        for hit in response["hits"]["hits"]:
            source = hit["_source"]
            results.append(SearchResult(
                learning_id=hit["_id"],
                learning=source.get("learning", ""),
                learnt_from=source.get("learnt_from"),
                pr=source.get("pr"),
                file=source.get("file"),
                timestamp=source.get("timestamp"),
                score=min(hit["_score"], 1.0)
            ))
        
        results = results[:request.k]
        
        return SearchResponse(
            query=query_text[:100] + "..." if len(query_text) > 100 else query_text,
            total=len(results),
            learnings=results
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"PR context search failed: {str(e)}")


@app.get("/learnings/{learning_id}")
async def get_learning(learning_id: str):
    """Get a specific learning by ID."""
    try:
        result = es_client.get(index=settings.index_name, id=learning_id)
        source = result["_source"]
        
        return {
            "learning_id": learning_id,
            "learning": source.get("learning"),
            "learnt_from": source.get("learnt_from"),
            "pr": source.get("pr"),
            "file": source.get("file"),
            "timestamp": source.get("timestamp")
        }
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"Learning not found: {str(e)}")


@app.delete("/learnings/{learning_id}")
async def delete_learning(learning_id: str):
    """Delete (deactivate) a learning by ID."""
    try:
        es_client.delete(index=settings.index_name, id=learning_id)
        return {"message": f"Learning {learning_id} deleted", "status": "success"}
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"Failed to delete learning: {str(e)}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=settings.api_host, port=settings.api_port)
