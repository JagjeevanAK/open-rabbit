"""
Unit Test Service - Handles unit test generation business logic.

This service encapsulates all the business logic for generating unit tests,
including PR-specific test generation and committing tests to branches.
"""
import os
import time
from typing import Dict, Any, List

import httpx

from agent import FileInfo
from agent.logging_config import get_logger, log_with_data, set_session_id
from agent.services.sandbox_manager import SandboxOperationError
from agent.subagents.parser_agent import ParserAgent
from agent.subagents.unit_test_agent import UnitTestAgent
from agent.schemas.common import KBContext
from backend.schemas.api import UnitTestRequest, PRUnitTestRequest
from backend.services.review_service import get_sandbox_manager, create_supervisor
from backend.utils.language_detection import detect_language

logger = get_logger(__name__)

# Bot endpoint URL for committing files
BOT_URL = os.getenv("BOT_URL", "http://localhost:3000")


class UnitTestService:
    """Service for generating unit tests."""
    
    def __init__(self, task_repository):
        """
        Initialize the unit test service.
        
        Args:
            task_repository: Repository for task state management
        """
        self.task_repository = task_repository
    
    async def execute_unit_test_generation(
        self, 
        task_id: str, 
        request: UnitTestRequest, 
        test_branch: str
    ) -> None:
        """
        Generate unit tests for a repository using E2B Sandbox.
        
        Args:
            task_id: Unique identifier for this task
            request: Unit test request parameters
            test_branch: Branch name for the tests
        """
        sandbox_manager = None
        
        try:
            self.task_repository.update_status(task_id, "running")
            
            # Initialize sandbox manager
            try:
                sandbox_manager = get_sandbox_manager()
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
            from agent.types import ReviewRequest as AgentReviewRequest
            agent_request = AgentReviewRequest(
                files=files,
                user_request="Generate unit tests for this code",
                repo_url=f"https://github.com/{request.owner}/{request.repo}",
                branch=request.branch,
            )
            
            # Run supervisor agent
            supervisor = create_supervisor()
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
            
            self.task_repository.complete_task(task_id, result)
            logger.info(f"Unit test task {task_id} completed successfully")
            
        except Exception as e:
            logger.error(f"Unit test task {task_id} failed: {e}")
            self.task_repository.fail_task(task_id, str(e))
            
        finally:
            # Clean up sandbox
            if sandbox_manager:
                try:
                    await sandbox_manager.kill_sandbox(task_id)
                except Exception as e:
                    logger.warning(f"Failed to cleanup sandbox: {e}")
    
    async def execute_pr_unit_test_generation(
        self, 
        task_id: str, 
        request: PRUnitTestRequest
    ) -> None:
        """
        Generate unit tests for PR files and commit them.
        
        Flow:
        1. Create E2B sandbox
        2. Clone repo at PR branch
        3. Read target files
        4. Parse files with ParserAgent
        5. Generate tests with UnitTestAgent
        6. Commit tests via bot's /commit-files endpoint
        7. Cleanup sandbox
        
        Args:
            task_id: Unique identifier for this task
            request: PR unit test request parameters
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
            self.task_repository.update_status(task_id, "running")
            
            # Initialize sandbox manager
            try:
                sandbox_manager = get_sandbox_manager()
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
                        language=detect_language(file_path),
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
                
                self.task_repository.complete_task(task_id, {
                    "generated_files": [],
                    "failed_files": failed_files,
                    "message": "No tests were generated",
                })
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
            commit_message = self._build_test_commit_message(
                [f["path"] for f in files_to_commit],
                request.target_files
            )
            
            commit_result = await self._commit_files_to_branch(
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
                
                self.task_repository.complete_task(task_id, {
                    "generated_files": [f["path"] for f in files_to_commit],
                    "failed_files": failed_files,
                    "commit_sha": commit_result.get("sha"),
                    "commit_url": commit_result.get("commitUrl"),
                    "tests_generated": test_output.output.total_tests if test_output.output else 0,
                })
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
    
    def _build_test_commit_message(
        self, 
        test_files: List[str], 
        source_files: List[str]
    ) -> str:
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
        self,
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
