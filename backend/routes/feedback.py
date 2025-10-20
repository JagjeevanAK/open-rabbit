from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
import uuid
import logging

from agent.workflow import CodeReviewWorkflow
from services.github_comment_service import post_review_to_github

logger = logging.getLogger(__name__)

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
    generate_tests: bool = Field(False, description="Whether to generate unit tests for changed files")
    installation_id: Optional[int] = Field(None, description="GitHub App installation ID (required for auto-posting)")
    auto_post: bool = Field(True, description="Automatically post review comment to GitHub PR")


class FileReviewRequest(BaseModel):
    """Request model for reviewing specific files"""
    file_paths: List[str] = Field(..., description="List of file paths to review")
    repo_path: str = Field(..., description="Path to the repository")
    context: Optional[str] = Field(None, description="Additional context about the review")
    generate_tests: bool = Field(False, description="Whether to generate unit tests")


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
def post_review_comment(
    owner: str = Field(..., description="Repository owner"),
    repo: str = Field(..., description="Repository name"),
    pr_number: int = Field(..., description="Pull request number"),
    task_id: str = Field(..., description="Task ID of completed review"),
    installation_id: int = Field(..., description="GitHub App installation ID")
):
    """
    Manually post a completed review as a comment to GitHub PR.
    
    This is useful if auto_post was disabled or if you want to re-post a review.
    """
    if task_id not in review_tasks:
        raise HTTPException(status_code=404, detail="Task not found")
    
    task = review_tasks[task_id]
    
    if task["status"] != "completed":
        raise HTTPException(
            status_code=400, 
            detail=f"Task is not completed (status: {task['status']})"
        )
    
    try:
        from services.github_comment_service import post_review_to_github
        
        result = post_review_to_github(
            owner=owner,
            repo=repo,
            pull_number=pr_number,
            review_result=task["result"],
            installation_id=installation_id
        )
        
        if result.get("success"):
            return {
                "success": True,
                "message": f"Review posted to {owner}/{repo}#{pr_number}",
                "task_id": task_id
            }
        else:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to post comment: {result.get('error')}"
            )
            
    except Exception as e:
        logger.error(f"Error posting comment: {e}")
        raise HTTPException(status_code=500, detail=str(e))


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
            pr_description=request.pr_description,
            generate_tests=request.generate_tests
        )
        
        review_tasks[task_id]["status"] = "completed"
        review_tasks[task_id]["completed_at"] = datetime.utcnow().isoformat()
        review_tasks[task_id]["result"] = result
        
        # Auto-post comment to GitHub if enabled
        if request.auto_post and request.pr_number and request.installation_id:
            try:
                # Parse owner/repo from repo_url
                parts = request.repo_url.replace("https://github.com/", "").split("/")
                if len(parts) >= 2:
                    owner = parts[0]
                    repo = parts[1].replace(".git", "")
                    
                    logger.info(f"Auto-posting review to {owner}/{repo}#{request.pr_number}")
                    
                    comment_result = post_review_to_github(
                        owner=owner,
                        repo=repo,
                        pull_number=request.pr_number,
                        review_result=result,
                        installation_id=request.installation_id
                    )
                    
                    review_tasks[task_id]["comment_posted"] = comment_result
                    
                    if comment_result.get("success"):
                        logger.info(f"Review comment posted successfully to PR #{request.pr_number}")
                    else:
                        logger.error(f"Failed to post comment: {comment_result.get('error')}")
                else:
                    logger.warning(f"Could not parse owner/repo from: {request.repo_url}")
                    
            except Exception as e:
                logger.error(f"Error auto-posting comment: {e}")
                review_tasks[task_id]["comment_error"] = str(e)
        
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
            context=request.context,
            generate_tests=request.generate_tests
        )
        
        review_tasks[task_id]["status"] = "completed"
        review_tasks[task_id]["completed_at"] = datetime.utcnow().isoformat()
        review_tasks[task_id]["result"] = result
        
    except Exception as e:
        review_tasks[task_id]["status"] = "failed"
        review_tasks[task_id]["completed_at"] = datetime.utcnow().isoformat()
        review_tasks[task_id]["error"] = str(e)
        review_tasks[task_id]["error"] = str(e)
