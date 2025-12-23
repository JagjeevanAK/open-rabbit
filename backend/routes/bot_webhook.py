"""
Bot Webhook Routes

Endpoints for the GitHub bot to trigger code reviews and other operations.
"""

from fastapi import APIRouter, BackgroundTasks, HTTPException
from typing import Optional, Dict, Any
from datetime import datetime
import uuid
import logging

from agent.workflow import CodeReviewWorkflow
from models import (
    ReviewRequest,
    UnitTestRequest,
    TaskResponse,
    TaskStatus,
    TaskListResponse,
    HealthResponse
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/bot", tags=["bot"])

# Initialize workflow with mock LLM for testing
workflow = CodeReviewWorkflow(use_mock_llm=True)

# Task storage (in-memory for now, use Redis in production)
bot_tasks: Dict[str, Dict[str, Any]] = {}


@router.get("/health", response_model=HealthResponse)
def health_check():
    """Health check endpoint for bot service"""
    return HealthResponse(
        status="healthy",
        service="open-rabbit-backend",
        mock_llm=workflow.use_mock_llm
    )


@router.post("/review", response_model=TaskResponse)
async def trigger_review(request: ReviewRequest, background_tasks: BackgroundTasks):
    """Trigger a code review for a PR"""
    task_id = str(uuid.uuid4())
    
    bot_tasks[task_id] = {
        "status": "pending",
        "owner": request.owner,
        "repo": request.repo,
        "pr_number": request.pr_number,
        "created_at": datetime.utcnow().isoformat(),
        "completed_at": None,
        "result": None,
        "error": None
    }
    
    background_tasks.add_task(_execute_review, task_id, request)
    logger.info(f"Review task {task_id} created for {request.owner}/{request.repo}#{request.pr_number}")
    
    return TaskResponse(
        task_id=task_id,
        status="pending",
        message=f"Review started for {request.owner}/{request.repo}#{request.pr_number}"
    )


@router.post("/create-unit-tests", response_model=TaskResponse)
async def create_unit_tests(request: UnitTestRequest, background_tasks: BackgroundTasks):
    """Generate unit tests for a repository"""
    task_id = str(uuid.uuid4())
    test_branch = f"openrabbit/tests-{request.issue_number}"
    
    bot_tasks[task_id] = {
        "status": "pending",
        "owner": request.owner,
        "repo": request.repo,
        "issue_number": request.issue_number,
        "test_branch": test_branch,
        "created_at": datetime.utcnow().isoformat(),
        "completed_at": None,
        "result": None,
        "error": None
    }
    
    background_tasks.add_task(_execute_unit_test_generation, task_id, request, test_branch)
    logger.info(f"Unit test task {task_id} created for {request.owner}/{request.repo}")
    
    return TaskResponse(
        task_id=task_id,
        status="pending",
        message=f"Unit test generation started for {request.owner}/{request.repo}",
        test_branch=test_branch
    )


@router.get("/task-status/{task_id}", response_model=TaskStatus)
async def get_task_status(task_id: str):
    """Get the status of a bot task"""
    if task_id not in bot_tasks:
        raise HTTPException(status_code=404, detail="Task not found")
    
    task = bot_tasks[task_id]
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
    """List all bot tasks, optionally filtered by status"""
    tasks = []
    
    for task_id, task in list(bot_tasks.items())[-limit:]:
        if status is None or task["status"] == status:
            tasks.append({
                "task_id": task_id,
                "status": task["status"],
                "owner": task["owner"],
                "repo": task["repo"],
                "created_at": task["created_at"],
                "completed_at": task.get("completed_at")
            })
    
    return TaskListResponse(total=len(tasks), tasks=tasks)


@router.delete("/task/{task_id}")
async def delete_task(task_id: str):
    """Delete a task from memory"""
    if task_id not in bot_tasks:
        raise HTTPException(status_code=404, detail="Task not found")
    
    del bot_tasks[task_id]
    return {"message": f"Task {task_id} deleted"}


async def _execute_review(task_id: str, request: ReviewRequest):
    """Background task to execute code review"""
    try:
        bot_tasks[task_id]["status"] = "running"
        
        result = workflow.review_pull_request(
            repo_url=f"{request.owner}/{request.repo}",
            pr_number=request.pr_number,
            branch=request.branch,
            changed_files=request.changed_files,
            generate_tests=False
        )
        
        bot_tasks[task_id]["status"] = "completed"
        bot_tasks[task_id]["completed_at"] = datetime.utcnow().isoformat()
        bot_tasks[task_id]["result"] = result
        logger.info(f"Review task {task_id} completed successfully")
        
    except Exception as e:
        logger.error(f"Review task {task_id} failed: {e}")
        bot_tasks[task_id]["status"] = "failed"
        bot_tasks[task_id]["completed_at"] = datetime.utcnow().isoformat()
        bot_tasks[task_id]["error"] = str(e)


async def _execute_unit_test_generation(task_id: str, request: UnitTestRequest, test_branch: str):
    """Background task to generate unit tests"""
    try:
        bot_tasks[task_id]["status"] = "running"
        
        result = workflow.review_pull_request(
            repo_url=f"{request.owner}/{request.repo}",
            pr_number=request.issue_number,
            branch=request.branch,
            generate_tests=True
        )
        
        bot_tasks[task_id]["status"] = "completed"
        bot_tasks[task_id]["completed_at"] = datetime.utcnow().isoformat()
        bot_tasks[task_id]["result"] = result
        logger.info(f"Unit test task {task_id} completed successfully")
        
    except Exception as e:
        logger.error(f"Unit test task {task_id} failed: {e}")
        bot_tasks[task_id]["status"] = "failed"
        bot_tasks[task_id]["completed_at"] = datetime.utcnow().isoformat()
        bot_tasks[task_id]["error"] = str(e)
