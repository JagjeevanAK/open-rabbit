from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
import uuid

from agent.workflow import CodeReviewWorkflow

router = APIRouter(
    prefix="/feedback",
    tags=["feedback"]
)

workflow = CodeReviewWorkflow()
review_tasks: Dict[str, Dict[str, Any]] = {}


class ReviewRequest(BaseModel):
    """Request model for code review"""
    repo_url: str = Field(..., description="GitHub repository URL or shorthand (e.g., 'owner/repo')")
    pr_number: Optional[int] = Field(None, description="Pull request number")
    branch: Optional[str] = Field(None, description="Branch name to review")
    changed_files: Optional[List[str]] = Field(None, description="List of changed files")
    pr_description: Optional[str] = Field(None, description="Pull request description")


class FileReviewRequest(BaseModel):
    """Request model for reviewing specific files"""
    file_paths: List[str] = Field(..., description="List of file paths to review")
    repo_path: str = Field(..., description="Path to the repository")
    context: Optional[str] = Field(None, description="Additional context about the review")


class ReviewResponse(BaseModel):
    """Response model for review results"""
    task_id: str
    status: str
    message: str
    review_url: Optional[str] = None


class ReviewStatus(BaseModel):
    """Status model for review task"""
    task_id: str
    status: str
    created_at: str
    completed_at: Optional[str] = None
    result: Optional[Dict[str, Any]] = None


@router.post("/comment")
def comment():
    pass


@router.post("/accept")
def accept_commit():
    pass


@router.post("/review/pr", response_model=ReviewResponse)
async def review_pull_request(
    request: ReviewRequest,
    background_tasks: BackgroundTasks
):
    """
    Trigger AI-powered code review for a pull request.
    
    This endpoint starts the LangGraph workflow:
    1. Context Enrichment (clone repo, fetch learnings)
    2. Static Analysis (AST/CFG/PDG)
    3. Code Review (generate feedback)
    4. Format Output (structure as JSON)
    """
    task_id = str(uuid.uuid4())
    
    review_tasks[task_id] = {
        "status": "pending",
        "created_at": datetime.utcnow().isoformat(),
        "completed_at": None,
        "result": None
    }
    
    background_tasks.add_task(
        _execute_pr_review,
        task_id=task_id,
        request=request
    )
    
    return ReviewResponse(
        task_id=task_id,
        status="pending",
        message="Code review started. Use /feedback/review/status/{task_id} to check progress.",
        review_url=f"/feedback/review/status/{task_id}"
    )


# @router.post("/review/files", response_model=ReviewResponse)
# async def review_files(
#     request: FileReviewRequest,
#     background_tasks: BackgroundTasks
# ):
#     """
#     Review specific files without a PR context.
#     """
#     task_id = str(uuid.uuid4())
    
#     review_tasks[task_id] = {
#         "status": "pending",
#         "created_at": datetime.utcnow().isoformat(),
#         "completed_at": None,
#         "result": None
#     }
    
#     background_tasks.add_task(
#         _execute_file_review,
#         task_id=task_id,
#         request=request
#     )
    
#     return ReviewResponse(
#         task_id=task_id,
#         status="pending",
#         message="File review started. Use /feedback/review/status/{task_id} to check progress.",
#         review_url=f"/feedback/review/status/{task_id}"
#     )


@router.get("/review/status/{task_id}", response_model=ReviewStatus)
async def get_review_status(task_id: str):
    """
    Get the status of a review task.
    """
    if task_id not in review_tasks:
        raise HTTPException(status_code=404, detail="Task not found")
    
    task = review_tasks[task_id]
    
    return ReviewStatus(
        task_id=task_id,
        status=task["status"],
        created_at=task["created_at"],
        completed_at=task.get("completed_at"),
        result=task.get("result")
    )


@router.get("/review/result/{task_id}")
async def get_review_result(task_id: str):
    """
    Get the full result of a completed review.
    """
    if task_id not in review_tasks:
        raise HTTPException(status_code=404, detail="Task not found")
    
    task = review_tasks[task_id]
    
    if task["status"] == "pending" or task["status"] == "running":
        raise HTTPException(status_code=202, detail="Review still in progress")
    
    if task["status"] == "failed":
        raise HTTPException(
            status_code=500, 
            detail=f"Review failed: {task.get('error', 'Unknown error')}"
        )
    
    return task.get("result", {})


@router.delete("/review/{task_id}")
async def delete_review_task(task_id: str):
    """
    Delete a review task from memory.
    """
    if task_id not in review_tasks:
        raise HTTPException(status_code=404, detail="Task not found")
    
    del review_tasks[task_id]
    
    return {"message": f"Task {task_id} deleted"}


@router.get("/review/tasks")
async def list_review_tasks():
    """
    List all review tasks.
    """
    return {
        "total": len(review_tasks),
        "tasks": [
            {
                "task_id": task_id,
                "status": task["status"],
                "created_at": task["created_at"],
                "completed_at": task.get("completed_at")
            }
            for task_id, task in review_tasks.items()
        ]
    }


async def _execute_pr_review(task_id: str, request: ReviewRequest):
    """
    Background task to execute PR review workflow.
    """
    try:
        review_tasks[task_id]["status"] = "running"
        
        result = workflow.review_pull_request(
            repo_url=request.repo_url,
            pr_number=request.pr_number,
            branch=request.branch,
            changed_files=request.changed_files,
            pr_description=request.pr_description
        )
        
        review_tasks[task_id]["status"] = "completed"
        review_tasks[task_id]["completed_at"] = datetime.utcnow().isoformat()
        review_tasks[task_id]["result"] = result
        
    except Exception as e:
        review_tasks[task_id]["status"] = "failed"
        review_tasks[task_id]["completed_at"] = datetime.utcnow().isoformat()
        review_tasks[task_id]["error"] = str(e)


async def _execute_file_review(task_id: str, request: FileReviewRequest):
    """
    Background task to execute file review workflow.
    """
    try:
        review_tasks[task_id]["status"] = "running"
        
        result = workflow.review_files(
            file_paths=request.file_paths,
            repo_path=request.repo_path,
            context=request.context
        )
        
        review_tasks[task_id]["status"] = "completed"
        review_tasks[task_id]["completed_at"] = datetime.utcnow().isoformat()
        review_tasks[task_id]["result"] = result
        
    except Exception as e:
        review_tasks[task_id]["status"] = "failed"
        review_tasks[task_id]["completed_at"] = datetime.utcnow().isoformat()
        review_tasks[task_id]["error"] = str(e)
