"""
Bot Webhook Routes

Endpoints for the GitHub bot to trigger code reviews and other operations.
Uses E2B sandbox for all repository operations (no local cloning).
"""

from fastapi import APIRouter, BackgroundTasks, HTTPException
from typing import Optional, Dict, Any, List
from datetime import datetime
import uuid
import os
import time
import httpx

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
)
from agent.services.sandbox_manager import (
    SandboxManager,
    SandboxOperationError,
    create_sandbox_manager,
)
from agent.subagents.comment_formatter_agent import CommentFormatterAgent
from agent.subagents.unit_test_agent import UnitTestAgent
from agent.subagents.parser_agent import ParserAgent
from agent.schemas.common import KBContext
from ..schemas import (
    ReviewRequest,
    UnitTestRequest,
    PRUnitTestRequest,
    TaskResponse,
    TaskStatus,
    TaskListResponse,
    HealthResponse
)
from ..services.github_comment_service import GitHubCommentService

# Initialize production logging
setup_logging()
logger = get_logger("routes.bot_webhook")

router = APIRouter(prefix="/bot", tags=["bot"])

# Task storage (in-memory for now, use Redis in production)
bot_tasks: Dict[str, Dict[str, Any]] = {}

# Global sandbox manager (lazy-initialized)
_sandbox_manager: Optional[SandboxManager] = None


def _get_sandbox_manager() -> SandboxManager:
    """Get or create the global sandbox manager."""
    global _sandbox_manager
    if _sandbox_manager is None:
        _sandbox_manager = create_sandbox_manager()
    return _sandbox_manager


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
    e2b_configured = bool(os.getenv("E2B_API_KEY"))
    return HealthResponse(
        status="healthy",
        service="open-rabbit-backend",
        mock_llm=False,  # Real LLM is always used now
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
        "is_fork": request.head_owner != request.owner if request.head_owner else False,
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


@router.post("/generate-pr-tests", response_model=TaskResponse)
async def generate_pr_tests(request: PRUnitTestRequest, background_tasks: BackgroundTasks):
    """
    Generate unit tests for PR changed files and commit directly to the branch.
    
    This endpoint is triggered by @openrabbit unit-test mentions on PRs.
    It generates tests for the specified files and commits them directly
    to the PR branch using the bot's /commit-files endpoint.
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
    
    bot_tasks[task_id] = {
        "status": "pending",
        "owner": request.owner,
        "repo": request.repo,
        "pr_number": request.pr_number,
        "branch": request.branch,
        "created_at": datetime.utcnow().isoformat(),
        "completed_at": None,
        "result": None,
        "error": None
    }
    
    background_tasks.add_task(_execute_pr_unit_test_generation, task_id, request)
    
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
    """
    Background task to execute code review using E2B Sandbox.
    
    Flow:
    1. Create E2B sandbox
    2. Clone repo (with fork/upstream support)
    3. Get diff and valid lines
    4. Read changed files
    5. Run SupervisorAgent for review
    6. Run CommentFormatterAgent for formatting
    7. Post to GitHub
    8. Cleanup sandbox
    """
    sandbox_manager = None
    workflow_start = time.perf_counter()
    
    # Set session ID for log correlation
    set_session_id(task_id)
    
    log_with_data(logger, 20, "Starting review execution with E2B sandbox", {
        "task_id": task_id,
        "owner": request.owner,
        "repo": request.repo,
        "pr_number": request.pr_number,
        "branch": request.branch,
        "base_branch": request.base_branch,
        "head_owner": request.head_owner,
        "head_repo": request.head_repo,
        "changed_files_count": len(request.changed_files) if request.changed_files else 0,
        "test_mode": request.test_mode,
        "dry_run": request.dry_run,
    })
    
    try:
        bot_tasks[task_id]["status"] = "running"
        
        # Initialize sandbox manager
        try:
            sandbox_manager = _get_sandbox_manager()
        except ValueError as e:
            log_with_data(logger, 40, "E2B not configured", {
                "task_id": task_id,
                "error": str(e),
            })
            raise Exception("E2B_API_KEY not configured. E2B sandbox is required for reviews.")
        
        # Create sandbox for this session
        sandbox_start = time.perf_counter()
        await sandbox_manager.create_sandbox(
            session_id=task_id,
            metadata={"pr": f"{request.owner}/{request.repo}#{request.pr_number}"}
        )
        sandbox_duration_ms = (time.perf_counter() - sandbox_start) * 1000
        
        log_with_data(logger, 20, "Sandbox created", {
            "task_id": task_id,
            "duration_ms": round(sandbox_duration_ms, 2),
        })
        
        # Determine clone parameters (fork vs same-repo)
        fork_owner = request.head_owner or request.owner
        fork_repo = request.head_repo or request.repo
        base_branch = request.base_branch or "main"
        is_fork = fork_owner != request.owner or fork_repo != request.repo
        
        # Clone repository in sandbox
        clone_start = time.perf_counter()
        log_with_data(logger, 20, "Cloning repository in sandbox", {
            "task_id": task_id,
            "fork_owner": fork_owner,
            "fork_repo": fork_repo,
            "branch": request.branch,
            "base_owner": request.owner,
            "base_repo": request.repo,
            "base_branch": base_branch,
            "is_fork": is_fork,
        })
        
        repo_path = await sandbox_manager.clone_fork_repo(
            session_id=task_id,
            fork_owner=fork_owner,
            fork_repo=fork_repo,
            branch=request.branch,
            base_owner=request.owner,
            base_repo=request.repo,
            base_branch=base_branch,
        )
        
        clone_duration_ms = (time.perf_counter() - clone_start) * 1000
        log_with_data(logger, 20, "Repository cloned in sandbox", {
            "task_id": task_id,
            "repo_path": repo_path,
            "duration_ms": round(clone_duration_ms, 2),
        })
        
        # Get valid lines and diff text from sandbox
        diff_start = time.perf_counter()
        valid_lines = await sandbox_manager.get_diff(
            session_id=task_id,
            base_branch=base_branch,
            changed_files=request.changed_files,
        )
        diff_text_per_file = await sandbox_manager.get_diff_text(
            session_id=task_id,
            base_branch=base_branch,
            changed_files=request.changed_files,
        )
        diff_duration_ms = (time.perf_counter() - diff_start) * 1000
        
        log_with_data(logger, 20, "Git diff parsed", {
            "task_id": task_id,
            "files_with_valid_lines": len(valid_lines),
            "total_valid_lines": sum(len(lines) for lines in valid_lines.values()),
            "duration_ms": round(diff_duration_ms, 2),
        })
        
        # Read changed files from sandbox
        files: List[FileInfo] = []
        skipped_files = []
        
        if request.changed_files:
            for file_path in request.changed_files:
                full_path = f"{repo_path}/{file_path}"
                
                try:
                    content = await sandbox_manager.read_file(task_id, full_path)
                    
                    # Skip large files (>500KB)
                    if len(content) > 500_000:
                        skipped_files.append({"path": file_path, "reason": "too_large"})
                        continue
                    
                    # Get diff text for this file
                    file_diff = diff_text_per_file.get(file_path)
                    
                    files.append(FileInfo(
                        path=file_path,
                        content=content,
                        diff=file_diff,
                        language=_detect_language(file_path),
                    ))
                    
                except SandboxOperationError as e:
                    skipped_files.append({"path": file_path, "reason": str(e)[:50]})
                    continue
        
        log_with_data(logger, 20, "Files loaded from sandbox", {
            "task_id": task_id,
            "files_loaded": len(files),
            "files_skipped": len(skipped_files),
            "skipped_details": skipped_files[:5],
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
            base_branch=base_branch,
            valid_lines=valid_lines if valid_lines else None,
        )
        
        # Run supervisor agent for review
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
            "issues_found": output.review_output.total_issues if output.review_output else 0,
            "duration_ms": round(agent_duration_ms, 2),
        })
        
        # Run Comment Formatter Agent
        formatter_start = time.perf_counter()
        formatter_result = None
        
        if output.review_output and output.review_output.issues:
            log_with_data(logger, 20, "Running CommentFormatterAgent", {
                "task_id": task_id,
                "raw_comments": len(output.review_output.issues),
            })
            
            # Create formatter input from review output
            formatter_input = CommentFormatterAgent.from_review_output(
                review_output=output.review_output,
                valid_lines=valid_lines,
                diff_text_per_file=diff_text_per_file,
                max_comments=20,
            )
            
            # Run formatter - returns AgentResult with output field containing FormatterOutput
            formatter_agent = CommentFormatterAgent()
            agent_result = await formatter_agent.run(formatter_input)
            formatter_result = agent_result.output  # Extract the actual FormatterOutput
            
            formatter_duration_ms = (time.perf_counter() - formatter_start) * 1000
            if formatter_result:
                log_with_data(logger, 20, "CommentFormatterAgent completed", {
                    "task_id": task_id,
                    "inline_comments": len(formatter_result.inline_comments),
                    "dropped_comments": len(formatter_result.dropped_comments),
                    "duration_ms": round(formatter_duration_ms, 2),
                })
        
        # Build result
        result = {
            "status": output.status.value if output.status else "completed",
            "repo_url": f"{request.owner}/{request.repo}",
            "pr_number": request.pr_number,
            "branch": request.branch,
            "files_reviewed": len(files),
            "session_id": output.session_id,
            "duration_seconds": output.duration_seconds,
            "review_output": output.review_output.to_dict() if output.review_output else None,
            "parser_output": output.parser_output.to_dict() if output.parser_output else None,
        }
        
        # Use formatted output if available, otherwise fallback
        if formatter_result:
            result["formatted_review"] = formatter_result.to_github_review()
            result["formatting_stats"] = {
                "total_raw_comments": formatter_result.total_raw_comments,
                "comments_on_valid_lines": formatter_result.comments_on_valid_lines,
                "inline_comments_posted": len(formatter_result.inline_comments),
                "comments_dropped": len(formatter_result.dropped_comments),
            }
        else:
            result["formatted_review"] = output.to_github_review()
        
        bot_tasks[task_id]["status"] = "completed"
        bot_tasks[task_id]["completed_at"] = datetime.utcnow().isoformat()
        bot_tasks[task_id]["result"] = result
        
        total_duration_ms = (time.perf_counter() - workflow_start) * 1000
        
        log_with_data(logger, 20, "Review task completed successfully", {
            "task_id": task_id,
            "status": "completed",
            "files_reviewed": len(files),
            "review_issues": output.review_output.total_issues if output.review_output else 0,
            "inline_comments": len(formatter_result.inline_comments) if formatter_result else 0,
            "total_duration_ms": round(total_duration_ms, 2),
        })
        
        # Post review results to GitHub
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
        # Clean up sandbox
        if sandbox_manager:
            try:
                await sandbox_manager.kill_sandbox(task_id)
                log_with_data(logger, 10, "Sandbox cleaned up", {
                    "task_id": task_id,
                })
            except Exception as e:
                log_with_data(logger, 30, f"Failed to cleanup sandbox: {e}", {
                    "task_id": task_id,
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
            "has_inline_comments": bool(result.get("formatted_review", {}).get("comments")),
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
                    "inline_comments": response.get("comments_posted", 0),
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
    """Background task to generate unit tests using E2B Sandbox."""
    sandbox_manager = None
    
    try:
        bot_tasks[task_id]["status"] = "running"
        
        # Initialize sandbox manager
        try:
            sandbox_manager = _get_sandbox_manager()
        except ValueError as e:
            raise Exception("E2B_API_KEY not configured. E2B sandbox is required.")
        
        # Create sandbox
        await sandbox_manager.create_sandbox(session_id=task_id)
        
        # Clone repository
        repo_path = await sandbox_manager.clone_fork_repo(
            session_id=task_id,
            fork_owner=request.owner,
            fork_repo=request.repo,
            branch=request.branch,
            base_owner=request.owner,
            base_repo=request.repo,
            base_branch="main",
        )
        
        logger.info(f"Cloned {request.owner}/{request.repo}@{request.branch} to sandbox")
        
        # For unit tests, we scan and read relevant source files
        # TODO: Implement smarter file selection based on the request
        files: List[FileInfo] = []
        
        # Create agent request with explicit test generation request
        agent_request = AgentReviewRequest(
            files=files,
            user_request="Generate unit tests for this code",
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
        # Clean up sandbox
        if sandbox_manager:
            try:
                await sandbox_manager.kill_sandbox(task_id)
            except Exception as e:
                logger.warning(f"Failed to cleanup sandbox: {e}")


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


# Bot endpoint URL for committing files
BOT_URL = os.getenv("BOT_URL", "http://localhost:3000")


async def _execute_pr_unit_test_generation(task_id: str, request: PRUnitTestRequest):
    """
    Background task to generate unit tests for PR files and commit them.
    
    Flow:
    1. Create E2B sandbox
    2. Clone repo at PR branch
    3. Read target files
    4. Parse files with ParserAgent
    5. Generate tests with UnitTestAgent
    6. Commit tests via bot's /commit-files endpoint
    7. Cleanup sandbox
    """
    sandbox_manager = None
    workflow_start = time.perf_counter()
    
    # Set session ID for log correlation
    set_session_id(task_id)
    
    log_with_data(logger, 20, "Starting PR unit test generation", {
        "task_id": task_id,
        "owner": request.owner,
        "repo": request.repo,
        "pr_number": request.pr_number,
        "branch": request.branch,
        "target_files": request.target_files,
        "test_framework": request.test_framework,
    })
    
    generated_files: List[Dict[str, Any]] = []
    failed_files: List[Dict[str, str]] = []
    
    try:
        bot_tasks[task_id]["status"] = "running"
        
        # Initialize sandbox manager
        try:
            sandbox_manager = _get_sandbox_manager()
        except ValueError as e:
            log_with_data(logger, 40, "E2B not configured", {
                "task_id": task_id,
                "error": str(e),
            })
            raise Exception("E2B_API_KEY not configured. E2B sandbox is required.")
        
        # Create sandbox
        sandbox_start = time.perf_counter()
        await sandbox_manager.create_sandbox(
            session_id=task_id,
            metadata={"pr": f"{request.owner}/{request.repo}#{request.pr_number}"}
        )
        sandbox_duration_ms = (time.perf_counter() - sandbox_start) * 1000
        
        log_with_data(logger, 20, "Sandbox created for test generation", {
            "task_id": task_id,
            "duration_ms": round(sandbox_duration_ms, 2),
        })
        
        # Determine clone parameters (fork vs same-repo)
        fork_owner = request.head_owner or request.owner
        fork_repo = request.head_repo or request.repo
        base_branch = request.base_branch or "main"
        
        # Clone repository in sandbox
        clone_start = time.perf_counter()
        repo_path = await sandbox_manager.clone_fork_repo(
            session_id=task_id,
            fork_owner=fork_owner,
            fork_repo=fork_repo,
            branch=request.branch,
            base_owner=request.owner,
            base_repo=request.repo,
            base_branch=base_branch,
        )
        clone_duration_ms = (time.perf_counter() - clone_start) * 1000
        
        log_with_data(logger, 20, "Repository cloned for test generation", {
            "task_id": task_id,
            "repo_path": repo_path,
            "duration_ms": round(clone_duration_ms, 2),
        })
        
        # Read target files from sandbox
        files: List[FileInfo] = []
        for file_path in request.target_files:
            full_path = f"{repo_path}/{file_path}"
            
            try:
                content = await sandbox_manager.read_file(task_id, full_path)
                
                # Skip large files (>100KB for test generation)
                if len(content) > 100_000:
                    failed_files.append({
                        "file": file_path,
                        "reason": "File too large (>100KB)"
                    })
                    continue
                
                files.append(FileInfo(
                    path=file_path,
                    content=content,
                    language=_detect_language(file_path),
                ))
                
            except SandboxOperationError as e:
                failed_files.append({
                    "file": file_path,
                    "reason": f"Could not read file: {str(e)[:50]}"
                })
                continue
        
        log_with_data(logger, 20, "Files loaded for test generation", {
            "task_id": task_id,
            "files_loaded": len(files),
            "files_failed": len(failed_files),
        })
        
        if not files:
            raise Exception("No testable files could be read from the repository")
        
        # Run Parser Agent to understand code structure
        parser_start = time.perf_counter()
        parser_agent = ParserAgent()
        parser_output = await parser_agent.run(files)
        parser_duration_ms = (time.perf_counter() - parser_start) * 1000
        
        log_with_data(logger, 20, "Parser completed", {
            "task_id": task_id,
            "files_parsed": len(parser_output.output.files) if parser_output.output else 0,
            "duration_ms": round(parser_duration_ms, 2),
        })
        
        # Run Unit Test Agent
        test_agent_start = time.perf_counter()
        unit_test_agent = UnitTestAgent()
        
        # Create empty KB context (could enhance later with project patterns)
        kb_context = KBContext()
        
        test_output = await unit_test_agent.run(
            parsed_metadata=parser_output.output,
            kb_context=kb_context,
            target_files=[f.path for f in files],
            repo_path=repo_path,
        )
        test_agent_duration_ms = (time.perf_counter() - test_agent_start) * 1000
        
        log_with_data(logger, 20, "Unit test generation completed", {
            "task_id": task_id,
            "tests_generated": test_output.output.total_tests if test_output.output else 0,
            "duration_ms": round(test_agent_duration_ms, 2),
        })
        
        # Group tests by test file path
        test_files_content: Dict[str, str] = {}
        if test_output.output and test_output.output.tests:
            for test in test_output.output.tests:
                if test.test_file not in test_files_content:
                    test_files_content[test.test_file] = ""
                # Use the helper to get combined content
                test_files_content[test.test_file] = test_output.output.get_test_code_for_file(test.test_file)
        
        if not test_files_content:
            log_with_data(logger, 30, "No tests were generated", {
                "task_id": task_id,
            })
            
            bot_tasks[task_id]["status"] = "completed"
            bot_tasks[task_id]["completed_at"] = datetime.utcnow().isoformat()
            bot_tasks[task_id]["result"] = {
                "generated_files": [],
                "failed_files": failed_files,
                "message": "No tests were generated",
            }
            return
        
        # Prepare files for commit
        files_to_commit = [
            {"path": path, "content": content}
            for path, content in test_files_content.items()
            if content.strip()  # Only commit non-empty files
        ]
        
        log_with_data(logger, 20, "Preparing to commit test files", {
            "task_id": task_id,
            "files_to_commit": len(files_to_commit),
            "file_paths": [f["path"] for f in files_to_commit],
        })
        
        # Commit tests via bot's /commit-files endpoint
        commit_message = _build_test_commit_message(
            [f["path"] for f in files_to_commit],
            request.target_files
        )
        
        commit_result = await _commit_files_to_branch(
            owner=request.owner,
            repo=request.repo,
            branch=request.branch,
            files=files_to_commit,
            message=commit_message,
            installation_id=request.installation_id,
        )
        
        if commit_result.get("success"):
            generated_files = [
                {"path": f["path"], "content_length": len(f["content"])}
                for f in files_to_commit
            ]
            
            log_with_data(logger, 20, "Tests committed successfully", {
                "task_id": task_id,
                "commit_sha": commit_result.get("sha"),
                "files_committed": len(generated_files),
            })
            
            bot_tasks[task_id]["status"] = "completed"
            bot_tasks[task_id]["completed_at"] = datetime.utcnow().isoformat()
            bot_tasks[task_id]["result"] = {
                "generated_files": [f["path"] for f in files_to_commit],
                "failed_files": failed_files,
                "commit_sha": commit_result.get("sha"),
                "commit_url": commit_result.get("commitUrl"),
                "tests_generated": test_output.output.total_tests if test_output.output else 0,
            }
        else:
            raise Exception(f"Failed to commit tests: {commit_result.get('error')}")
        
        total_duration_ms = (time.perf_counter() - workflow_start) * 1000
        log_with_data(logger, 20, "PR unit test generation completed", {
            "task_id": task_id,
            "total_duration_ms": round(total_duration_ms, 2),
            "files_generated": len(generated_files),
        })
        
    except Exception as e:
        total_duration_ms = (time.perf_counter() - workflow_start) * 1000
        
        log_with_data(logger, 40, f"PR unit test generation failed: {e}", {
            "task_id": task_id,
            "error": str(e),
            "error_type": type(e).__name__,
            "duration_ms": round(total_duration_ms, 2),
        })
        
        bot_tasks[task_id]["status"] = "failed"
        bot_tasks[task_id]["completed_at"] = datetime.utcnow().isoformat()
        bot_tasks[task_id]["error"] = str(e)
        
    finally:
        # Clean up sandbox
        if sandbox_manager:
            try:
                await sandbox_manager.kill_sandbox(task_id)
                log_with_data(logger, 10, "Sandbox cleaned up", {
                    "task_id": task_id,
                })
            except Exception as e:
                log_with_data(logger, 30, f"Failed to cleanup sandbox: {e}", {
                    "task_id": task_id,
                    "error": str(e),
                })


def _build_test_commit_message(test_files: List[str], source_files: List[str]) -> str:
    """Build a descriptive commit message for test files."""
    if len(source_files) == 1:
        source_name = source_files[0].split("/")[-1]
        return f"test: add unit tests for {source_name}"
    elif len(source_files) <= 3:
        source_names = [f.split("/")[-1] for f in source_files]
        return f"test: add unit tests for {', '.join(source_names)}"
    else:
        return f"test: add unit tests for {len(source_files)} files"


async def _commit_files_to_branch(
    owner: str,
    repo: str,
    branch: str,
    files: List[Dict[str, str]],
    message: str,
    installation_id: int,
) -> Dict[str, Any]:
    """
    Commit files to a branch via the bot's /commit-files endpoint.
    
    Returns:
        Dict with success, sha, commitUrl, or error
    """
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{BOT_URL}/commit-files",
                json={
                    "owner": owner,
                    "repo": repo,
                    "branch": branch,
                    "installation_id": installation_id,
                    "files": files,
                    "message": message,
                },
                timeout=60.0,
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                return {
                    "success": False,
                    "error": f"HTTP {response.status_code}: {response.text[:200]}",
                }
                
    except Exception as e:
        log_with_data(logger, 40, f"Failed to call bot /commit-files: {e}", {
            "owner": owner,
            "repo": repo,
            "branch": branch,
            "error": str(e),
        })
        return {
            "success": False,
            "error": str(e),
        }
