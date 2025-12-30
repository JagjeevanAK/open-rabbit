"""
Bot Webhook Routes

Endpoints for the GitHub bot to trigger code reviews and other operations.
Includes comprehensive production logging for tracking review workflows.
"""

from fastapi import APIRouter, BackgroundTasks, HTTPException
from typing import Optional, Dict, Any, List
from datetime import datetime
from pathlib import Path
import uuid
import logging
import shutil
import subprocess
import os
import time
import json

from agent import (
    SupervisorAgent,
    SupervisorConfig,
    ReviewRequest as AgentReviewRequest,
    FileInfo,
    LLMProvider,
)
from agent.logging_config import (
    get_logger,
    set_session_id,
    log_with_data,
    setup_logging,
    AsyncLogContext,
)
from models import (
    ReviewRequest,
    UnitTestRequest,
    TaskResponse,
    TaskStatus,
    TaskListResponse,
    HealthResponse
)
from services.github_comment_service import GitHubCommentService

# Initialize production logging
setup_logging()
logger = get_logger("routes.bot_webhook")

router = APIRouter(prefix="/bot", tags=["bot"])

# Task storage (in-memory for now, use Redis in production)
bot_tasks: Dict[str, Dict[str, Any]] = {}

# Temp directory in project root
PROJECT_ROOT = Path(__file__).parent.parent.parent  # open-rabbit/
TEMP_DIR = PROJECT_ROOT / "temp"


def _create_supervisor(use_mock: bool = False, task_id: str = "") -> SupervisorAgent:
    """Create a SupervisorAgent with configuration."""
    config = SupervisorConfig(
        llm_provider=LLMProvider.OPENAI,
        llm_model="gpt-4o-mini",  # Default model
        use_mock_agents=use_mock,
        kb_enabled=False,
        enable_checkpointing=True,  # Uses database checkpointing
    )
    
    log_with_data(logger, 20, "Created SupervisorAgent", {
        "task_id": task_id,
        "llm_provider": config.llm_provider.value,
        "llm_model": config.llm_model,
        "kb_enabled": config.kb_enabled,
        "checkpointing": config.enable_checkpointing,
    })
    
    return SupervisorAgent(config)


@router.get("/health", response_model=HealthResponse)
def health_check():
    """Health check endpoint for bot service"""
    return HealthResponse(
        status="healthy",
        service="open-rabbit-backend",
        mock_llm=False  # Real LLM is always used now
    )


@router.post("/review", response_model=TaskResponse)
async def trigger_review(request: ReviewRequest, background_tasks: BackgroundTasks):
    """Trigger a code review for a PR"""
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
    })
    
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


def _clone_repo(owner: str, repo: str, branch: str, dest_path: Path) -> bool:
    """
    Clone a GitHub repository to the specified path.
    
    Args:
        owner: Repository owner
        repo: Repository name
        branch: Branch to clone
        dest_path: Destination directory
        
    Returns:
        True if successful, False otherwise
    """
    repo_url = f"https://github.com/{owner}/{repo}.git"
    
    cmd = [
        "git", "clone",
        "--branch", branch,
        "--depth", "1",  # Shallow clone for speed
        repo_url,
        str(dest_path)
    ]
    
    try:
        start_time = time.perf_counter()
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=120  # 2 minute timeout
        )
        duration_ms = (time.perf_counter() - start_time) * 1000
        
        if result.returncode != 0:
            log_with_data(logger, 40, "Git clone failed", {
                "owner": owner,
                "repo": repo,
                "branch": branch,
                "returncode": result.returncode,
                "stderr": result.stderr[:500] if result.stderr else None,
                "duration_ms": round(duration_ms, 2),
            })
            return False
        
        log_with_data(logger, 20, "Git clone successful", {
            "owner": owner,
            "repo": repo,
            "branch": branch,
            "dest_path": str(dest_path),
            "duration_ms": round(duration_ms, 2),
        })
        return True
        
    except subprocess.TimeoutExpired:
        log_with_data(logger, 40, "Git clone timed out", {
            "owner": owner,
            "repo": repo,
            "branch": branch,
            "timeout_seconds": 120,
        })
        return False
    except Exception as e:
        log_with_data(logger, 40, f"Git clone error: {e}", {
            "owner": owner,
            "repo": repo,
            "branch": branch,
            "error": str(e),
            "error_type": type(e).__name__,
        })
        return False


def _read_file_content(file_path: Path) -> Optional[str]:
    """Read file content, returns None if file can't be read."""
    try:
        # Skip large files (>500KB)
        if file_path.stat().st_size > 500_000:
            logger.warning(f"Skipping large file: {file_path}")
            return None
            
        return file_path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        logger.warning(f"Cannot decode file (binary?): {file_path}")
        return None
    except Exception as e:
        logger.warning(f"Cannot read file {file_path}: {e}")
        return None


async def _execute_review(task_id: str, request: ReviewRequest):
    """Background task to execute code review using SupervisorAgent."""
    repo_path = None
    workflow_start = time.perf_counter()
    
    # Set session ID for log correlation
    set_session_id(task_id)
    
    log_with_data(logger, 20, "Starting review execution", {
        "task_id": task_id,
        "owner": request.owner,
        "repo": request.repo,
        "pr_number": request.pr_number,
        "branch": request.branch,
        "changed_files_count": len(request.changed_files) if request.changed_files else 0,
        "test_mode": request.test_mode,
        "dry_run": request.dry_run,
    })
    
    try:
        bot_tasks[task_id]["status"] = "running"
        
        # Create temp directory in project root if it doesn't exist
        TEMP_DIR.mkdir(parents=True, exist_ok=True)
        
        # Create unique directory for this repo clone
        clone_id = f"{request.owner}_{request.repo}_{task_id[:8]}"
        repo_path = TEMP_DIR / clone_id
        
        # Clean up if exists from previous failed run
        if repo_path.exists():
            shutil.rmtree(repo_path)
        
        # Clone the repository
        clone_start = time.perf_counter()
        log_with_data(logger, 20, "Cloning repository", {
            "task_id": task_id,
            "owner": request.owner,
            "repo": request.repo,
            "branch": request.branch,
            "dest_path": str(repo_path),
        })
        
        if not _clone_repo(request.owner, request.repo, request.branch, repo_path):
            raise Exception(f"Failed to clone repository {request.owner}/{request.repo}")
        
        clone_duration_ms = (time.perf_counter() - clone_start) * 1000
        log_with_data(logger, 20, "Repository cloned successfully", {
            "task_id": task_id,
            "duration_ms": round(clone_duration_ms, 2),
        })
        
        # Read only the changed files
        files: List[FileInfo] = []
        skipped_files = []
        if request.changed_files:
            for file_path in request.changed_files:
                full_path = repo_path / file_path
                
                if not full_path.exists():
                    skipped_files.append({"path": file_path, "reason": "not_found"})
                    continue
                
                content = _read_file_content(full_path)
                if content is None:
                    skipped_files.append({"path": file_path, "reason": "unreadable"})
                    continue
                    
                files.append(FileInfo(
                    path=file_path,
                    content=content,
                    language=_detect_language(file_path),
                ))
        
        log_with_data(logger, 20, "Files loaded for review", {
            "task_id": task_id,
            "files_loaded": len(files),
            "files_skipped": len(skipped_files),
            "skipped_details": skipped_files[:5] if skipped_files else [],  # Log first 5
            "languages": list(set(f.language for f in files)),
        })
        
        if not files:
            raise Exception("No reviewable files found")
        
        # Create agent request
        agent_request = AgentReviewRequest(
            files=files,
            user_request="Review this pull request for best practices, bugs, and security issues",
            repo_url=f"https://github.com/{request.owner}/{request.repo}",
            pr_number=request.pr_number,
            branch=request.branch,
        )
        
        # Run supervisor agent
        agent_start = time.perf_counter()
        log_with_data(logger, 20, "Invoking SupervisorAgent", {
            "task_id": task_id,
            "files_count": len(files),
        })
        
        supervisor = _create_supervisor(task_id=task_id)
        output = await supervisor.run(agent_request, session_id=task_id)
        
        agent_duration_ms = (time.perf_counter() - agent_start) * 1000
        log_with_data(logger, 20, "SupervisorAgent completed", {
            "task_id": task_id,
            "status": output.status.value if output.status else "unknown",
            "duration_ms": round(agent_duration_ms, 2),
            "session_id": output.session_id,
        })
        
        # Convert output to result format
        result = {
            "status": output.status.value if output.status else "completed",
            "repo_url": f"{request.owner}/{request.repo}",
            "pr_number": request.pr_number,
            "branch": request.branch,
            "files_reviewed": len(files),
            "session_id": output.session_id,
            "duration_seconds": output.duration_seconds,
            "formatted_review": output.to_github_review(),
            "review_output": output.review_output.to_dict() if output.review_output else None,
            "parser_output": output.parser_output.to_dict() if output.parser_output else None,
        }
        
        bot_tasks[task_id]["status"] = "completed"
        bot_tasks[task_id]["completed_at"] = datetime.utcnow().isoformat()
        bot_tasks[task_id]["result"] = result
        
        total_duration_ms = (time.perf_counter() - workflow_start) * 1000
        review_issues = output.review_output.total_issues if output.review_output else 0
        
        log_with_data(logger, 20, "Review task completed successfully", {
            "task_id": task_id,
            "status": "completed",
            "files_reviewed": len(files),
            "review_issues": review_issues,
            "total_duration_ms": round(total_duration_ms, 2),
            "clone_duration_ms": round(clone_duration_ms, 2),
            "agent_duration_ms": round(agent_duration_ms, 2),
        })
        
        # Post review results back to GitHub via bot
        await _post_review_to_github(request, result)
        
    except Exception as e:
        total_duration_ms = (time.perf_counter() - workflow_start) * 1000
        
        log_with_data(logger, 40, f"Review task failed: {e}", {
            "task_id": task_id,
            "status": "failed",
            "error": str(e),
            "error_type": type(e).__name__,
            "duration_ms": round(total_duration_ms, 2),
        })
        
        bot_tasks[task_id]["status"] = "failed"
        bot_tasks[task_id]["completed_at"] = datetime.utcnow().isoformat()
        bot_tasks[task_id]["error"] = str(e)
        
    finally:
        # Clean up cloned repo
        if repo_path and repo_path.exists():
            try:
                shutil.rmtree(repo_path)
                log_with_data(logger, 10, "Cleaned up repo directory", {
                    "task_id": task_id,
                    "path": str(repo_path),
                })
            except Exception as e:
                log_with_data(logger, 30, f"Failed to clean up repo directory: {e}", {
                    "task_id": task_id,
                    "path": str(repo_path),
                    "error": str(e),
                })


async def _post_review_to_github(request: ReviewRequest, result: Dict[str, Any]):
    """Post the review results to GitHub via the bot."""
    try:
        start_time = time.perf_counter()
        
        # Use test mode service if request is in test mode
        service = GitHubCommentService(test_mode=request.test_mode)
        
        log_with_data(logger, 20, "Posting review to GitHub", {
            "owner": request.owner,
            "repo": request.repo,
            "pr_number": request.pr_number,
            "test_mode": request.test_mode,
            "dry_run": request.dry_run,
        })
        
        response = service.post_review_from_result(
            owner=request.owner,
            repo=request.repo,
            pull_number=request.pr_number,
            review_result=result,
            installation_id=request.installation_id,
            dry_run=request.dry_run
        )
        
        duration_ms = (time.perf_counter() - start_time) * 1000
        
        if response.get("success"):
            mode_str = "[TEST MODE] " if request.test_mode else ""
            if response.get("dry_run"):
                log_with_data(logger, 20, f"{mode_str}Review saved to file", {
                    "owner": request.owner,
                    "repo": request.repo,
                    "pr_number": request.pr_number,
                    "output_file": response.get('output_file'),
                    "duration_ms": round(duration_ms, 2),
                })
            else:
                log_with_data(logger, 20, f"{mode_str}Review posted successfully", {
                    "owner": request.owner,
                    "repo": request.repo,
                    "pr_number": request.pr_number,
                    "comment_id": response.get("comment_id"),
                    "duration_ms": round(duration_ms, 2),
                })
        else:
            log_with_data(logger, 40, "Failed to post review", {
                "owner": request.owner,
                "repo": request.repo,
                "pr_number": request.pr_number,
                "error": response.get('error'),
                "duration_ms": round(duration_ms, 2),
            })
            
    except Exception as e:
        log_with_data(logger, 40, f"Error posting review to GitHub: {e}", {
            "owner": request.owner,
            "repo": request.repo,
            "pr_number": request.pr_number,
            "error": str(e),
            "error_type": type(e).__name__,
        })


async def _execute_unit_test_generation(task_id: str, request: UnitTestRequest, test_branch: str):
    """Background task to generate unit tests using SupervisorAgent."""
    repo_path = None
    
    try:
        bot_tasks[task_id]["status"] = "running"
        
        # Create temp directory in project root if it doesn't exist
        TEMP_DIR.mkdir(parents=True, exist_ok=True)
        
        # Create unique directory for this repo clone
        clone_id = f"{request.owner}_{request.repo}_test_{task_id[:8]}"
        repo_path = TEMP_DIR / clone_id
        
        # Clean up if exists from previous failed run
        if repo_path.exists():
            shutil.rmtree(repo_path)
        
        logger.info(f"Cloning {request.owner}/{request.repo}@{request.branch} to {repo_path}")
        
        # Clone the repository
        if not _clone_repo(request.owner, request.repo, request.branch, repo_path):
            raise Exception(f"Failed to clone repository {request.owner}/{request.repo}")
        
        # For unit tests, we scan and read relevant source files
        # TODO: Implement smarter file selection based on the request
        files: List[FileInfo] = []
        
        # Create agent request with explicit test generation request
        agent_request = AgentReviewRequest(
            files=files,
            user_request="Generate unit tests for this code",  # This triggers test generation
            repo_url=f"https://github.com/{request.owner}/{request.repo}",
            branch=request.branch,
        )
        
        # Run supervisor agent
        supervisor = _create_supervisor()
        output = await supervisor.run(agent_request)
        
        # Convert output to result format
        result = {
            "status": output.status.value if output.status else "completed",
            "repo_url": f"{request.owner}/{request.repo}",
            "issue_number": request.issue_number,
            "branch": request.branch,
            "test_branch": test_branch,
            "session_id": output.session_id,
            "duration_seconds": output.duration_seconds,
            "unit_tests": output.test_output.model_dump() if output.test_output else None,
        }
        
        bot_tasks[task_id]["status"] = "completed"
        bot_tasks[task_id]["completed_at"] = datetime.utcnow().isoformat()
        bot_tasks[task_id]["result"] = result
        logger.info(f"Unit test task {task_id} completed successfully")
        
    except Exception as e:
        logger.error(f"Unit test task {task_id} failed: {e}")
        bot_tasks[task_id]["status"] = "failed"
        bot_tasks[task_id]["completed_at"] = datetime.utcnow().isoformat()
        bot_tasks[task_id]["error"] = str(e)
        
    finally:
        # Clean up cloned repo
        if repo_path and repo_path.exists():
            try:
                shutil.rmtree(repo_path)
                logger.info(f"Cleaned up repo directory: {repo_path}")
            except Exception as e:
                logger.warning(f"Failed to clean up repo directory: {e}")


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
