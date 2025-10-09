from fastapi import APIRouter, BackgroundTasks, HTTPException, Header
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
from datetime import datetime
import uuid
import os

from agent.workflow import CodeReviewWorkflow

router = APIRouter(
    prefix="/bot",
    tags=["bot"]
)

workflow = CodeReviewWorkflow()
bot_tasks: Dict[str, Dict[str, Any]] = {}


class UnitTestRequest(BaseModel):
    """Request model from GitHub bot for unit test generation"""
    owner: str = Field(..., description="Repository owner")
    repo: str = Field(..., description="Repository name")
    issue_number: int = Field(..., description="Issue/PR number where comment was made")
    branch: Optional[str] = Field(None, description="Branch to generate tests for")
    installation_id: int = Field(..., description="GitHub App installation ID")
    comment_id: int = Field(..., description="Comment ID that triggered the command")


class CreatePRRequest(BaseModel):
    """Request model to create a PR after tests are generated"""
    owner: str = Field(..., description="Repository owner")
    repo: str = Field(..., description="Repository name")
    base_branch: str = Field(..., description="Base branch (e.g., 'main')")
    head_branch: str = Field(..., description="Head branch with tests")
    title: str = Field(..., description="PR title")
    body: str = Field(..., description="PR description")
    installation_id: int = Field(..., description="GitHub App installation ID")


class BotTaskResponse(BaseModel):
    """Response model for bot tasks"""
    task_id: str
    status: str
    message: str
    test_branch: Optional[str] = None


class BotTaskStatus(BaseModel):
    """Status model for bot task"""
    task_id: str
    status: str
    created_at: str
    completed_at: Optional[str] = None
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


def _execute_unit_test_generation(
    task_id: str,
    owner: str,
    repo: str,
    branch: Optional[str],
    issue_number: int,
    installation_id: int
):
    """Background task to generate unit tests"""
    try:
        repo_url = f"{owner}/{repo}"
        test_branch = f"open-rabbit/unit-tests-{issue_number}"
        
        bot_tasks[task_id]["status"] = "running"
        bot_tasks[task_id]["test_branch"] = test_branch
        
        result = workflow.review_pull_request(
            repo_url=repo_url,
            branch=branch or "main",
            generate_tests=True
        )
        
        bot_tasks[task_id]["status"] = "completed"
        bot_tasks[task_id]["completed_at"] = datetime.utcnow().isoformat()
        bot_tasks[task_id]["result"] = {
            "unit_tests": result.get("unit_tests", {}),
            "test_branch": test_branch,
            "pr_number": issue_number,
            "installation_id": installation_id
        }
        
    except Exception as e:
        bot_tasks[task_id]["status"] = "failed"
        bot_tasks[task_id]["completed_at"] = datetime.utcnow().isoformat()
        bot_tasks[task_id]["error"] = str(e)


@router.post("/create-unit-tests", response_model=BotTaskResponse)
async def create_unit_tests(
    request: UnitTestRequest,
    background_tasks: BackgroundTasks,
    x_github_event: Optional[str] = Header(None)
):
    """
    Endpoint triggered by GitHub bot when /create-unit-test command is used.
    
    This will:
    1. Generate unit tests for the repository
    2. Create a new branch with the tests
    3. Push the tests to the new branch
    4. Return task ID for status tracking
    """
    
    task_id = str(uuid.uuid4())
    bot_tasks[task_id] = {
        "status": "pending",
        "created_at": datetime.utcnow().isoformat(),
        "completed_at": None,
        "result": None,
        "error": None,
        "owner": request.owner,
        "repo": request.repo,
        "issue_number": request.issue_number
    }
    
    background_tasks.add_task(
        _execute_unit_test_generation,
        task_id,
        request.owner,
        request.repo,
        request.branch,
        request.issue_number,
        request.installation_id
    )
    
    test_branch = f"open-rabbit/unit-tests-{request.issue_number}"
    
    return BotTaskResponse(
        task_id=task_id,
        status="pending",
        message=f"Unit test generation started. Tests will be pushed to branch '{test_branch}'",
        test_branch=test_branch
    )


@router.get("/task-status/{task_id}", response_model=BotTaskStatus)
async def get_task_status(task_id: str):
    """
    Get the status of a unit test generation task.
    
    Bot can poll this endpoint to check when tests are ready.
    """
    
    if task_id not in bot_tasks:
        raise HTTPException(status_code=404, detail="Task not found")
    
    task = bot_tasks[task_id]
    return BotTaskStatus(
        task_id=task_id,
        status=task["status"],
        created_at=task["created_at"],
        completed_at=task.get("completed_at"),
        result=task.get("result"),
        error=task.get("error")
    )


@router.post("/trigger-pr-creation")
async def trigger_pr_creation(request: CreatePRRequest):
    """
    Endpoint for bot to notify backend that it should create a PR.
    
    This is called by the bot after it detects tests have been pushed
    to the new branch.
    """
    
    return {
        "status": "success",
        "message": f"PR creation triggered for {request.owner}/{request.repo}",
        "details": {
            "base": request.base_branch,
            "head": request.head_branch,
            "title": request.title
        }
    }


@router.get("/tasks")
async def list_bot_tasks():
    """List all bot tasks (for debugging)"""
    
    return {
        "total": len(bot_tasks),
        "tasks": [
            {
                "task_id": task_id,
                "status": task["status"],
                "owner": task.get("owner"),
                "repo": task.get("repo"),
                "created_at": task["created_at"]
            }
            for task_id, task in bot_tasks.items()
        ]
    }


@router.get("/health")
async def bot_health():
    """Health check endpoint for bot integration"""
    return {
        "status": "healthy",
        "service": "bot-webhook",
        "tasks_count": len(bot_tasks)
    }
