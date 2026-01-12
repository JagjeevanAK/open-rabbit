"""
Feedback Routes

Code review feedback endpoints using the SupervisorAgent workflow.
"""

from fastapi import APIRouter, BackgroundTasks, HTTPException
from typing import Dict, Any, List
from datetime import datetime
import uuid
import logging

from agent import (
    SupervisorAgent,
    SupervisorConfig,
    ReviewRequest as AgentReviewRequest,
    FileInfo,
    LLMProvider,
)
from ..services.github_comment_service import post_review_to_github
from ..schemas import PRReviewRequest, ReviewResponse, ReviewStatusModel as ReviewStatus

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/feedback", tags=["feedback"])

# Store for review tasks
review_tasks: Dict[str, Dict[str, Any]] = {}


def _create_supervisor() -> SupervisorAgent:
    """Create a SupervisorAgent with default configuration."""
    config = SupervisorConfig(
        llm_provider=LLMProvider.OPENAI,
        llm_model="gpt-4o-mini",  # Default model, can be overridden
        use_mock_agents=False,
        kb_enabled=False,  # Disable KB by default
        enable_checkpointing=True,
    )
    return SupervisorAgent(config)


@router.post("/review/pr", response_model=ReviewResponse)
async def review_pull_request(request: PRReviewRequest, background_tasks: BackgroundTasks):
    """
    Trigger AI-powered code review for a pull request.
    
    Workflow: Fetch files → Parse code → Generate review → Post to GitHub
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
    """Background task to execute PR review workflow using SupervisorAgent."""
    try:
        review_tasks[task_id]["status"] = "running"
        
        # Build file info list from changed files
        files: List[FileInfo] = []
        
        if request.changed_files:
            # If we have changed files with content, use them directly
            for file_path in request.changed_files:
                # Note: In a real implementation, you'd fetch file content from GitHub
                # For now, we'll create FileInfo with path only (content will be fetched)
                files.append(FileInfo(
                    path=file_path,
                    content="",  # Content would be fetched from GitHub
                    language=_detect_language(file_path),
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
        supervisor = _create_supervisor()
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
        
        review_tasks[task_id]["status"] = "completed"
        review_tasks[task_id]["completed_at"] = datetime.utcnow().isoformat()
        review_tasks[task_id]["result"] = result
        
        # Auto-post to GitHub if enabled
        if request.auto_post and request.pr_number and request.installation_id:
            await _auto_post_to_github(task_id, request, result)
        
    except Exception as e:
        logger.error(f"Review task {task_id} failed: {e}")
        review_tasks[task_id]["status"] = "failed"
        review_tasks[task_id]["completed_at"] = datetime.utcnow().isoformat()
        review_tasks[task_id]["error"] = str(e)


async def _auto_post_to_github(task_id: str, request: PRReviewRequest, result: Dict):
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


def _detect_language(file_path: str) -> str:
    """Detect programming language from file extension."""
    ext_map = {
        ".py": "python",
        ".js": "javascript",
        ".jsx": "javascript",
        ".ts": "typescript",
        ".tsx": "typescript",
        ".java": "java",
        ".go": "go",
        ".rs": "rust",
        ".rb": "ruby",
        ".php": "php",
        ".cs": "csharp",
        ".cpp": "cpp",
        ".c": "c",
        ".h": "c",
        ".hpp": "cpp",
    }
    
    for ext, lang in ext_map.items():
        if file_path.endswith(ext):
            return lang
    
    return "unknown"
