"""
Feedback Routes

Thin HTTP handlers for code review feedback endpoints.
Business logic is delegated to service classes.
"""

from fastapi import APIRouter, BackgroundTasks, HTTPException
from typing import Dict, List
import uuid
import logging

from agent import (
    ReviewRequest as AgentReviewRequest,
    FileInfo,
)
from backend.services.review_service import create_supervisor
from backend.services.github_comment_service import post_review_to_github
from backend.repositories.task_repository import task_repository
from backend.utils.language_detection import detect_language
from backend.schemas.api import PRReviewRequest, ReviewResponse, ReviewStatusModel as ReviewStatus

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/feedback", tags=["feedback"])


@router.post("/review/pr", response_model=ReviewResponse)
async def review_pull_request(request: PRReviewRequest, background_tasks: BackgroundTasks):
    """
    Trigger AI-powered code review for a pull request.
    
    Workflow: Fetch files → Parse code → Generate review → Post to GitHub
    """
    task_id = str(uuid.uuid4())
    
    # Create task in repository
    task_repository.create_review_task(
        task_id=task_id,
        owner=_extract_owner(request.repo_url),
        repo=_extract_repo(request.repo_url),
        pr_number=request.pr_number or 0,
    )
    
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
    task = task_repository.get_task(task_id)
    
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    
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
    task = task_repository.get_task(task_id)
    
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    
    if task["status"] in ("pending", "running"):
        raise HTTPException(status_code=202, detail="Review still in progress")
    
    if task["status"] == "failed":
        raise HTTPException(status_code=500, detail=f"Review failed: {task.get('error', 'Unknown')}")
    
    return task.get("result", {})


@router.delete("/review/{task_id}")
async def delete_review_task(task_id: str):
    """Delete a review task from memory."""
    if not task_repository.delete_task(task_id):
        raise HTTPException(status_code=404, detail="Task not found")
    
    return {"message": f"Task {task_id} deleted"}


@router.get("/review/tasks")
async def list_review_tasks():
    """List all review tasks."""
    tasks = task_repository.list_tasks()
    return {
        "total": len(tasks),
        "tasks": tasks
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
    task = task_repository.get_task(task_id)
    
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    
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


# ===== Helper Functions =====

def _extract_owner(repo_url: str) -> str:
    """Extract owner from GitHub repo URL."""
    parts = repo_url.replace("https://github.com/", "").split("/")
    return parts[0] if parts else ""


def _extract_repo(repo_url: str) -> str:
    """Extract repo name from GitHub repo URL."""
    parts = repo_url.replace("https://github.com/", "").split("/")
    return parts[1].replace(".git", "") if len(parts) >= 2 else ""


# ===== Background Tasks =====

async def _execute_pr_review(task_id: str, request: PRReviewRequest):
    """Background task to execute PR review workflow using SupervisorAgent."""
    try:
        task_repository.update_status(task_id, "running")
        
        # Build file info list from changed files
        files: List[FileInfo] = []
        
        if request.changed_files:
            for file_path in request.changed_files:
                files.append(FileInfo(
                    path=file_path,
                    content="",  # Content would be fetched from GitHub
                    language=detect_language(file_path),
                ))
        
        # Create the agent review request
        agent_request = AgentReviewRequest(
            files=files,
            user_request=request.pr_description or "Review this pull request for best practices, bugs, and security issues",
            repo_url=request.repo_url,
            pr_number=request.pr_number,
            branch=request.branch,
        )
        
        # Run the supervisor agent
        supervisor = create_supervisor(task_id=task_id)
        output = await supervisor.run(agent_request)
        
        # Convert to result format
        result = {
            "status": output.status.value if output.status else "completed",
            "repo_url": request.repo_url,
            "pr_number": request.pr_number,
            "branch": request.branch,
            "files_reviewed": len(files),
            "session_id": output.session_id,
            "duration_seconds": output.duration_seconds,
            "formatted_review": output.to_github_review(),
            "review_output": output.review_output.model_dump() if output.review_output else None,
            "parser_output": output.parser_output.model_dump() if output.parser_output else None,
            "unit_tests": output.test_output.model_dump() if output.test_output else None,
        }
        
        task_repository.complete_task(task_id, result)
        
        # Auto-post to GitHub if enabled
        if request.auto_post and request.pr_number and request.installation_id:
            await _auto_post_to_github(task_id, request, result)
        
    except Exception as e:
        logger.error(f"Review task {task_id} failed: {e}")
        task_repository.fail_task(task_id, str(e))


async def _auto_post_to_github(task_id: str, request: PRReviewRequest, result: Dict):
    """Auto-post review comment to GitHub."""
    try:
        owner = _extract_owner(request.repo_url)
        repo = _extract_repo(request.repo_url)
        
        if owner and repo:
            logger.info(f"Auto-posting review to {owner}/{repo}#{request.pr_number}")
            
            comment_result = post_review_to_github(
                owner=owner,
                repo=repo,
                pull_number=request.pr_number,
                review_result=result,
                installation_id=request.installation_id
            )
            
            if comment_result.get("success"):
                logger.info(f"Review posted to PR #{request.pr_number}")
            else:
                logger.error(f"Failed to post: {comment_result.get('error')}")
                
    except Exception as e:
        logger.error(f"Error auto-posting comment: {e}")
