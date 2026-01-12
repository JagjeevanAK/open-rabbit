"""
Review Service - Handles code review business logic.

This service encapsulates all the business logic for executing code reviews,
including sandbox management, file reading, agent orchestration, and result formatting.
"""
import os
import time
from typing import Dict, Any, List, Optional

from agent import (
    SupervisorAgent,
    SupervisorConfig,
    ReviewRequest as AgentReviewRequest,
    FileInfo,
    LLMProvider,
)
from agent.logging_config import get_logger, log_with_data, set_session_id
from agent.services.sandbox_manager import SandboxManager, SandboxOperationError, create_sandbox_manager
from agent.subagents.comment_formatter_agent import CommentFormatterAgent
from backend.services.github_comment_service import GitHubCommentService
from backend.schemas.api import ReviewRequest
from backend.utils.language_detection import detect_language

logger = get_logger(__name__)

# Singleton sandbox manager
_sandbox_manager: Optional[SandboxManager] = None


def get_sandbox_manager() -> SandboxManager:
    """Get or create the singleton sandbox manager."""
    global _sandbox_manager
    
    if _sandbox_manager is None:
        _sandbox_manager = create_sandbox_manager()
    
    return _sandbox_manager


def create_supervisor(task_id: str = "") -> SupervisorAgent:
    """Create a SupervisorAgent with environment-based configuration."""
    llm_provider_str = os.getenv("LLM_PROVIDER", "anthropic")
    try:
        llm_provider = LLMProvider(llm_provider_str.lower())
    except ValueError:
        llm_provider = LLMProvider.ANTHROPIC
    
    config = SupervisorConfig(
        llm_provider=llm_provider,
        llm_model=os.getenv("LLM_MODEL"),
        kb_enabled=os.getenv("ENABLE_KB", "false").lower() == "true",
        enable_checkpointing=os.getenv("ENABLE_CHECKPOINTING", "true").lower() == "true",
    )
    
    log_with_data(logger, 20, "Created SupervisorAgent", {
        "task_id": task_id,
        "llm_provider": config.llm_provider.value,
        "llm_model": config.llm_model,
        "kb_enabled": config.kb_enabled,
        "checkpointing": config.enable_checkpointing,
    })
    
    return SupervisorAgent(config)


class ReviewService:
    """Service for executing code reviews."""
    
    def __init__(self, task_repository):
        """
        Initialize the review service.
        
        Args:
            task_repository: Repository for task state management
        """
        self.task_repository = task_repository
    
    async def execute_review(self, task_id: str, request: ReviewRequest) -> None:
        """
        Execute a code review using E2B Sandbox.
        
        Flow:
        1. Create E2B sandbox
        2. Clone repo (with fork/upstream support)
        3. Get diff and valid lines
        4. Read changed files
        5. Run SupervisorAgent for review
        6. Run CommentFormatterAgent for formatting
        7. Post to GitHub
        8. Cleanup sandbox
        
        Args:
            task_id: Unique identifier for this review task
            request: Review request parameters
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
            self.task_repository.update_status(task_id, "running")
            
            # Initialize sandbox manager
            try:
                sandbox_manager = get_sandbox_manager()
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
                            language=detect_language(file_path),
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
            
            supervisor = create_supervisor(task_id=task_id)
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
            
            self.task_repository.complete_task(task_id, result)
            
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
            await self._post_review_to_github(request, result)
            
        except Exception as e:
            total_duration_ms = (time.perf_counter() - workflow_start) * 1000
            
            log_with_data(logger, 40, f"Review task failed: {e}", {
                "task_id": task_id,
                "status": "failed",
                "error": str(e),
                "error_type": type(e).__name__,
                "duration_ms": round(total_duration_ms, 2),
            })
            
            self.task_repository.fail_task(task_id, str(e))
            
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
    
    async def _post_review_to_github(self, request: ReviewRequest, result: Dict[str, Any]) -> None:
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
