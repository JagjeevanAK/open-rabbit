"""
Bot Webhook Routes

Endpoints for the GitHub bot to trigger code reviews and other operations.
Uses the new multi-agent SupervisorAgent for code review.
Tasks are persisted to Redis for durability.
"""

from fastapi import APIRouter, BackgroundTasks, HTTPException
from typing import Optional, Dict, Any, List
from datetime import datetime
import uuid
import os
import logging

from agent import (
    SupervisorAgent,
    SupervisorConfig,
    ReviewRequest as AgentReviewRequest,
    SupervisorOutput,
    FileChange,
    AgentStatus,
)
from agent.tools.gitClone import clone_repo_for_pr, cleanup_repo
from services.task_store import get_task_store, TaskData
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

# Configuration from environment
USE_MOCK = os.getenv("USE_MOCK_LLM", "true").lower() == "true"
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "openai")
KB_ENABLED = os.getenv("KB_ENABLED", "false").lower() == "true"


def get_supervisor_config() -> SupervisorConfig:
    """Get supervisor configuration from environment."""
    return SupervisorConfig(
        use_mock=USE_MOCK,
        llm_provider=LLM_PROVIDER,
        kb_enabled=KB_ENABLED,
        enable_checkpointing=True,
        max_files=50,
        max_file_size=100_000,
        parallel_parsing=True,
    )


@router.get("/health", response_model=HealthResponse)
def health_check():
    """Health check endpoint for bot service"""
    task_store = get_task_store()
    redis_healthy = task_store.health_check()
    
    return HealthResponse(
        status="healthy" if redis_healthy else "degraded",
        service="open-rabbit-backend",
        mock_llm=USE_MOCK
    )


@router.post("/review", response_model=TaskResponse)
async def trigger_review(request: ReviewRequest, background_tasks: BackgroundTasks):
    """Trigger a code review for a PR using the multi-agent system"""
    task_id = str(uuid.uuid4())
    task_store = get_task_store()
    
    # Create task
    task = TaskData(
        task_id=task_id,
        status="pending",
        owner=request.owner,
        repo=request.repo,
        pr_number=request.pr_number,
    )
    task_store.save_task(task)
    
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
    task_store = get_task_store()
    
    # Create task
    task = TaskData(
        task_id=task_id,
        status="pending",
        owner=request.owner,
        repo=request.repo,
        issue_number=request.issue_number,
        test_branch=test_branch,
    )
    task_store.save_task(task)
    
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
    task_store = get_task_store()
    task = task_store.get_task(task_id)
    
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    return TaskStatus(
        task_id=task_id,
        status=task.status,
        owner=task.owner,
        repo=task.repo,
        created_at=task.created_at,
        completed_at=task.completed_at,
        result=task.result,
        error=task.error
    )


@router.get("/tasks", response_model=TaskListResponse)
async def list_tasks(status: Optional[str] = None, limit: int = 50):
    """List all bot tasks, optionally filtered by status"""
    task_store = get_task_store()
    tasks = task_store.list_tasks(status=status, limit=limit)
    
    task_dicts = [
        {
            "task_id": t.task_id,
            "status": t.status,
            "owner": t.owner,
            "repo": t.repo,
            "created_at": t.created_at,
            "completed_at": t.completed_at
        }
        for t in tasks
    ]
    
    return TaskListResponse(total=len(task_dicts), tasks=task_dicts)


@router.delete("/task/{task_id}")
async def delete_task(task_id: str):
    """Delete a task from storage"""
    task_store = get_task_store()
    
    if not task_store.get_task(task_id):
        raise HTTPException(status_code=404, detail="Task not found")
    
    task_store.delete_task(task_id)
    return {"message": f"Task {task_id} deleted"}


def _build_changed_files(
    changed_file_paths: Optional[List[str]],
    repo_path: str
) -> List[FileChange]:
    """Build FileChange objects from file paths."""
    if not changed_file_paths:
        return []
    
    file_changes = []
    for path in changed_file_paths:
        # Try to detect if file is new or modified
        full_path = os.path.join(repo_path, path)
        status = "added" if not os.path.exists(full_path) else "modified"
        
        file_changes.append(FileChange(
            path=path,
            status=status,
            additions=0,  # We don't have this info from the webhook
            deletions=0,
            patch=None,  # No patch available from simple file list
        ))
    
    return file_changes


async def _execute_review(task_id: str, request: ReviewRequest):
    """Background task to execute code review using SupervisorAgent"""
    repo_path = None
    task_store = get_task_store()
    
    try:
        # Update status to running
        task_store.update_task(task_id, {"status": "running"})
        
        # Clone the repository
        logger.info(f"Cloning repository for review: {request.owner}/{request.repo}")
        repo_path = await clone_repo_for_pr(
            owner=request.owner,
            repo=request.repo,
            pr_number=request.pr_number,
            branch=request.branch,
            installation_id=request.installation_id,
        )
        
        if not repo_path:
            raise RuntimeError("Failed to clone repository")
        
        logger.info(f"Repository cloned to: {repo_path}")
        
        # Build file changes
        changed_files = _build_changed_files(request.changed_files, repo_path)
        
        if not changed_files:
            # If no files specified, this is an error for now
            # In future, we could fetch changed files from GitHub API
            raise ValueError("No changed files provided for review")
        
        # Create agent review request
        agent_request = AgentReviewRequest(
            owner=request.owner,
            repo=request.repo,
            pr_number=request.pr_number,
            branch=request.branch,
            changed_files=changed_files,
            pr_title=f"PR #{request.pr_number}",  # Could fetch from GitHub API
            pr_description=None,  # Could fetch from GitHub API
            repo_path=repo_path,
            generate_tests=False,
        )
        
        # Create and run supervisor
        config = get_supervisor_config()
        supervisor = SupervisorAgent(config=config)
        
        logger.info(f"Running supervisor agent for {request.owner}/{request.repo}#{request.pr_number}")
        output, checkpoint = supervisor.run(agent_request)
        
        # Convert output to dict for storage
        result = _format_review_result(output)
        
        # Update task with success
        task_store.update_task(task_id, {
            "status": "completed",
            "completed_at": datetime.utcnow().isoformat(),
            "result": result,
        })
        
        logger.info(f"Review task {task_id} completed successfully with {len(output.issues)} issues")
        
    except Exception as e:
        logger.error(f"Review task {task_id} failed: {e}", exc_info=True)
        
        # Update task with failure
        task_store.update_task(task_id, {
            "status": "failed",
            "completed_at": datetime.utcnow().isoformat(),
            "error": str(e),
        })
    
    finally:
        # Cleanup cloned repository
        if repo_path:
            try:
                cleanup_repo(repo_path)
                logger.info(f"Cleaned up repository at {repo_path}")
            except Exception as e:
                logger.warning(f"Failed to cleanup repository: {e}")


def _format_review_result(output: SupervisorOutput) -> Dict[str, Any]:
    """Format SupervisorOutput to a serializable dict."""
    return {
        "status": output.status.value,
        "summary": output.summary,
        "files_analyzed": output.files_analyzed,
        "issues_count": len(output.issues),
        "kb_learnings_applied": output.kb_learnings_applied,
        "suggestions_filtered": output.suggestions_filtered,
        "duration_seconds": output.duration_seconds,
        "issues": [
            {
                "file_path": issue.file_path,
                "line_start": issue.line_start,
                "line_end": issue.line_end,
                "severity": issue.severity.value,
                "category": issue.category.value,
                "title": issue.title,
                "message": issue.message,
                "suggestion": issue.suggestion,
                "confidence": issue.confidence,
                "source": issue.source,
            }
            for issue in output.issues
        ],
        "github_review": output.to_github_review(),
        "parser_summary": output.parser_summary,
        "review_summary": output.review_summary,
        "errors": output.errors,
    }


async def _execute_unit_test_generation(task_id: str, request: UnitTestRequest, test_branch: str):
    """Background task to generate unit tests (placeholder)"""
    repo_path = None
    task_store = get_task_store()
    
    try:
        # Update status to running
        task_store.update_task(task_id, {"status": "running"})
        
        # Clone the repository
        logger.info(f"Cloning repository for test generation: {request.owner}/{request.repo}")
        repo_path = await clone_repo_for_pr(
            owner=request.owner,
            repo=request.repo,
            pr_number=request.issue_number,
            branch=request.branch,
            installation_id=request.installation_id,
        )
        
        if not repo_path:
            raise RuntimeError("Failed to clone repository")
        
        # For now, unit test generation is not fully implemented
        # This would need a dedicated UnitTestAgent
        result = {
            "status": "not_implemented",
            "message": "Unit test generation is not yet fully implemented",
            "test_branch": test_branch,
        }
        
        # Update task with success
        task_store.update_task(task_id, {
            "status": "completed",
            "completed_at": datetime.utcnow().isoformat(),
            "result": result,
        })
        
        logger.info(f"Unit test task {task_id} completed")
        
    except Exception as e:
        logger.error(f"Unit test task {task_id} failed: {e}", exc_info=True)
        
        # Update task with failure
        task_store.update_task(task_id, {
            "status": "failed",
            "completed_at": datetime.utcnow().isoformat(),
            "error": str(e),
        })
    
    finally:
        # Cleanup cloned repository
        if repo_path:
            try:
                cleanup_repo(repo_path)
            except Exception as e:
                logger.warning(f"Failed to cleanup repository: {e}")
