"""
Bot Webhook Routes

Thin HTTP handlers for the GitHub bot webhook endpoints.
All business logic is delegated to service classes.
"""
import os
import uuid

from fastapi import APIRouter, BackgroundTasks, HTTPException
from typing import Optional

from backend.schemas.api import (
    ReviewRequest,
    UnitTestRequest,
    PRUnitTestRequest,
    TaskResponse,
    TaskStatus,
    TaskListResponse,
    HealthResponse,
)
from agent.logging_config import get_logger, log_with_data, set_session_id
from backend.repositories.task_repository import task_repository
from backend.services.review_service import ReviewService
from backend.services.unit_test_service import UnitTestService

logger = get_logger(__name__)

router = APIRouter(prefix="/bot", tags=["bot"])

# Initialize services with repository
review_service = ReviewService(task_repository)
unit_test_service = UnitTestService(task_repository)


@router.get("/health", response_model=HealthResponse)
def health_check():
    """Health check endpoint for bot service."""
    e2b_configured = bool(os.getenv("E2B_API_KEY"))
    return HealthResponse(
        status="healthy",
        service="open-rabbit-backend",
        mock_llm=False,
    )


@router.post("/review", response_model=TaskResponse)
async def trigger_review(request: ReviewRequest, background_tasks: BackgroundTasks):
    """Trigger a code review for a PR."""
    task_id = str(uuid.uuid4())
    
    # Set session ID for log correlation
    set_session_id(task_id)
    
    log_with_data(logger, 20, "Review request received", {
        "task_id": task_id,
        "owner": request.owner,
        "repo": request.repo,
        "pr_number": request.pr_number,
        "branch": request.branch,
        "changed_files_count": len(request.changed_files) if request.changed_files else 0,
        "test_mode": request.test_mode,
        "dry_run": request.dry_run,
        "is_fork": request.head_owner != request.owner if request.head_owner else False,
    })
    
    # Create task record
    task_repository.create_review_task(
        task_id=task_id,
        owner=request.owner,
        repo=request.repo,
        pr_number=request.pr_number,
    )
    
    # Queue background task
    background_tasks.add_task(review_service.execute_review, task_id, request)
    
    log_with_data(logger, 20, "Review task queued for background execution", {
        "task_id": task_id,
    })
    
    return TaskResponse(
        task_id=task_id,
        status="pending",
        message=f"Review started for {request.owner}/{request.repo}#{request.pr_number}"
    )


@router.post("/create-unit-tests", response_model=TaskResponse)
async def create_unit_tests(request: UnitTestRequest, background_tasks: BackgroundTasks):
    """Generate unit tests for a repository."""
    task_id = str(uuid.uuid4())
    test_branch = f"openrabbit/tests-{request.issue_number}"
    
    # Create task record
    task_repository.create_unit_test_task(
        task_id=task_id,
        owner=request.owner,
        repo=request.repo,
        issue_number=request.issue_number,
        test_branch=test_branch,
    )
    
    # Queue background task
    background_tasks.add_task(
        unit_test_service.execute_unit_test_generation, 
        task_id, 
        request, 
        test_branch
    )
    
    logger.info(f"Unit test task {task_id} created for {request.owner}/{request.repo}")
    
    return TaskResponse(
        task_id=task_id,
        status="pending",
        message=f"Unit test generation started for {request.owner}/{request.repo}",
        test_branch=test_branch
    )


@router.post("/generate-pr-tests", response_model=TaskResponse)
async def generate_pr_tests(request: PRUnitTestRequest, background_tasks: BackgroundTasks):
    """
    Generate unit tests for PR changed files and commit directly to the branch.
    
    This endpoint is triggered by @openrabbit unit-test mentions on PRs.
    """
    task_id = str(uuid.uuid4())
    
    # Set session ID for log correlation
    set_session_id(task_id)
    
    log_with_data(logger, 20, "PR unit test request received", {
        "task_id": task_id,
        "owner": request.owner,
        "repo": request.repo,
        "pr_number": request.pr_number,
        "branch": request.branch,
        "target_files": request.target_files,
        "test_framework": request.test_framework,
        "requested_by": request.requested_by,
    })
    
    # Create task record
    task_repository.create_pr_test_task(
        task_id=task_id,
        owner=request.owner,
        repo=request.repo,
        pr_number=request.pr_number,
        branch=request.branch,
    )
    
    # Queue background task
    background_tasks.add_task(
        unit_test_service.execute_pr_unit_test_generation, 
        task_id, 
        request
    )
    
    log_with_data(logger, 20, "PR unit test task queued for background execution", {
        "task_id": task_id,
    })
    
    return TaskResponse(
        task_id=task_id,
        status="pending",
        message=f"Unit test generation started for {request.owner}/{request.repo}#{request.pr_number}"
    )


@router.get("/task-status/{task_id}", response_model=TaskStatus)
async def get_task_status(task_id: str):
    """Get the status of a bot task."""
    task = task_repository.get_task(task_id)
    
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    
    return TaskStatus(
        task_id=task_id,
        status=task["status"],
        owner=task["owner"],
        repo=task["repo"],
        created_at=task["created_at"],
        completed_at=task.get("completed_at"),
        result=task.get("result"),
        error=task.get("error")
    )


@router.get("/tasks", response_model=TaskListResponse)
async def list_tasks(status: Optional[str] = None, limit: int = 50):
    """List all bot tasks, optionally filtered by status."""
    tasks = task_repository.list_tasks(status=status, limit=limit)
    
    return TaskListResponse(total=len(tasks), tasks=tasks)


@router.delete("/task/{task_id}")
async def delete_task(task_id: str):
    """Delete a task from memory."""
    if not task_repository.delete_task(task_id):
        raise HTTPException(status_code=404, detail="Task not found")
    
    return {"message": f"Task {task_id} deleted"}
