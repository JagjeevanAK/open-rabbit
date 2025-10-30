from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from tasks import process_learning
from config import settings

app = FastAPI(
    title="Knowledge Base API",
    description="API for storing and retrieving code learnings",
    version="1.0.0"
)


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


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=settings.api_host, port=settings.api_port)
