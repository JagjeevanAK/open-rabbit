"""
Feedback Routes

Code review feedback endpoints using the backend agent workflow.
"""

from fastapi import APIRouter, BackgroundTasks, HTTPException
from typing import Dict, Any
from datetime import datetime
import uuid
import logging

from agent.workflow import CodeReviewWorkflow
from services.github_comment_service import post_review_to_github
from models import PRReviewRequest, ReviewResponse, ReviewStatus

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/feedback", tags=["feedback"])

workflow = CodeReviewWorkflow()
review_tasks: Dict[str, Dict[str, Any]] = {}


@router.post("/review/pr", response_model=ReviewResponse)
async def review_pull_request(request: PRReviewRequest, background_tasks: BackgroundTasks):
    """
    Trigger AI-powered code review for a pull request.
    
    Workflow: Clone repo → AST/Semantic analysis → Generate review → Post to GitHub
    """
    task_id = str(uuid.uuid4())
    
    review_tasks[task_id] = {
        "status": "pending",
        "created_at": datetime.utcnow().isoformat(),
        "completed_at": None,
        "result": None
    }
    
    background_tasks.add_task(_execute_pr_review, task_id, request)
    
    return ReviewResponse(
        task_id=task_id,
        status="pending",
        message="Code review started. Use /feedback/review/status/{task_id} to check progress.",
        review_url=f"/feedback/review/status/{task_id}"
    )


@router.get("/review/status/{task_id}", response_model=ReviewStatus)
async def get_review_status(task_id: str):
    """Get the status of a review task."""
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
    """Get the full result of a completed review."""
    if task_id not in review_tasks:
        raise HTTPException(status_code=404, detail="Task not found")
    
    task = review_tasks[task_id]
    
    if task["status"] in ("pending", "running"):
        raise HTTPException(status_code=202, detail="Review still in progress")
    
    if task["status"] == "failed":
        raise HTTPException(status_code=500, detail=f"Review failed: {task.get('error', 'Unknown')}")
    
    return task.get("result", {})


@router.delete("/review/{task_id}")
async def delete_review_task(task_id: str):
    """Delete a review task from memory."""
    if task_id not in review_tasks:
        raise HTTPException(status_code=404, detail="Task not found")
    
    del review_tasks[task_id]
    return {"message": f"Task {task_id} deleted"}


@router.get("/review/tasks")
async def list_review_tasks():
    """List all review tasks."""
    return {
        "total": len(review_tasks),
        "tasks": [
            {
                "task_id": tid,
                "status": t["status"],
                "created_at": t["created_at"],
                "completed_at": t.get("completed_at")
            }
            for tid, t in review_tasks.items()
        ]
    }


@router.post("/comment")
def post_review_comment(
    owner: str,
    repo: str,
    pr_number: int,
    task_id: str,
    installation_id: int
):
    """Manually post a completed review as a comment to GitHub PR."""
    if task_id not in review_tasks:
        raise HTTPException(status_code=404, detail="Task not found")
    
    task = review_tasks[task_id]
    
    if task["status"] != "completed":
        raise HTTPException(status_code=400, detail=f"Task not completed (status: {task['status']})")
    
    try:
        result = post_review_to_github(
            owner=owner,
            repo=repo,
            pull_number=pr_number,
            review_result=task["result"],
            installation_id=installation_id
        )
        
        if result.get("success"):
            return {"success": True, "message": f"Review posted to {owner}/{repo}#{pr_number}", "task_id": task_id}
        else:
            raise HTTPException(status_code=500, detail=f"Failed to post comment: {result.get('error')}")
            
    except Exception as e:
        logger.error(f"Error posting comment: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ===== Background Tasks =====

async def _execute_pr_review(task_id: str, request: PRReviewRequest):
    """Background task to execute PR review workflow."""
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
        
        # Auto-post to GitHub if enabled
        if request.auto_post and request.pr_number and request.installation_id:
            _auto_post_to_github(task_id, request, result)
        
    except Exception as e:
        review_tasks[task_id]["status"] = "failed"
        review_tasks[task_id]["completed_at"] = datetime.utcnow().isoformat()
        review_tasks[task_id]["error"] = str(e)


def _auto_post_to_github(task_id: str, request: PRReviewRequest, result: Dict):
    """Auto-post review comment to GitHub."""
    try:
        parts = request.repo_url.replace("https://github.com/", "").split("/")
        if len(parts) >= 2:
            owner, repo = parts[0], parts[1].replace(".git", "")
            
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
                logger.info(f"Review posted to PR #{request.pr_number}")
            else:
                logger.error(f"Failed to post: {comment_result.get('error')}")
                
    except Exception as e:
        logger.error(f"Error auto-posting comment: {e}")
        review_tasks[task_id]["comment_error"] = str(e)
