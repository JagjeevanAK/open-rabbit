"""
E2B Sandbox Manager

Manages E2B sandbox lifecycle for code review sessions.

Features:
- Session-based sandbox management (one sandbox per session)
- Automatic timeout extension during active operations
- Retry logic with exponential backoff
- Cleanup on completion/failure
- Repository cloning and file operations
"""

import os
import asyncio
import logging
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum

from e2b_code_interpreter import Sandbox

logger = logging.getLogger(__name__)


class SandboxStatus(str, Enum):
    """Status of a sandbox session."""
    CREATING = "creating"
    RUNNING = "running"
    CLONING = "cloning"
    READY = "ready"
    ERROR = "error"
    KILLED = "killed"


@dataclass
class SandboxConfig:
    """Configuration for sandbox creation."""
    api_key: Optional[str] = None  # From env if not provided
    timeout_ms: int = 300_000      # 5 minutes default
    template_id: Optional[str] = None  # Custom template or use default
    max_retries: int = 3
    retry_delay_seconds: float = 5.0


@dataclass
class SandboxSession:
    """Tracks a sandbox session with metadata."""
    sandbox: Sandbox
    session_id: str
    status: SandboxStatus
    repo_path: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    last_activity: datetime = field(default_factory=datetime.utcnow)
    error_message: Optional[str] = None
    
    def update_activity(self):
        """Update last activity timestamp."""
        self.last_activity = datetime.utcnow()


class SandboxError(Exception):
    """Base exception for sandbox operations."""
    pass


class SandboxCreationError(SandboxError):
    """Error creating sandbox."""
    pass


class SandboxOperationError(SandboxError):
    """Error during sandbox operation."""
    pass


class SandboxNotFoundError(SandboxError):
    """Sandbox session not found."""
    pass


class SandboxManager:
    """
    Manages E2B sandboxes for code review sessions.
    
    Features:
    - Session-based sandbox reuse
    - Automatic timeout extension during active operations
    - Cleanup on completion/failure
    - Retry logic for transient failures
    
    Usage:
        manager = SandboxManager()
        await manager.create_sandbox("session-123")
        repo_path = await manager.clone_repo("session-123", "https://github.com/user/repo.git", "main")
        content = await manager.read_file("session-123", f"{repo_path}/src/main.py")
        await manager.kill_sandbox("session-123")
    """
    
    # Default repos directory inside sandbox
    REPOS_DIR = "/home/user/repos"
    
    def __init__(self, config: Optional[SandboxConfig] = None):
        """
        Initialize the Sandbox Manager.
        
        Args:
            config: Sandbox configuration. Uses env vars if not provided.
        """
        self.config = config or SandboxConfig()
        self._sessions: Dict[str, SandboxSession] = {}
        self._api_key = self.config.api_key or os.getenv("E2B_API_KEY")
        self._template_id = self.config.template_id or os.getenv("E2B_TEMPLATE_ID")
        
        if not self._api_key:
            raise ValueError(
                "E2B_API_KEY not configured. "
                "Set it in environment or pass via SandboxConfig."
            )
        
        logger.info(
            f"SandboxManager initialized with timeout={self.config.timeout_ms}ms, "
            f"template={self._template_id or 'default'}"
        )
    
    async def create_sandbox(
        self,
        session_id: str,
        timeout_ms: Optional[int] = None,
        metadata: Optional[Dict[str, str]] = None,
    ) -> Sandbox:
        """
        Create a new sandbox for a session.
        
        Args:
            session_id: Unique session identifier
            timeout_ms: Custom timeout (uses config default if not provided)
            metadata: Optional metadata to attach to sandbox
            
        Returns:
            The created Sandbox instance
            
        Raises:
            SandboxCreationError: If sandbox creation fails after retries
        """
        if session_id in self._sessions:
            existing = self._sessions[session_id]
            if existing.status in (SandboxStatus.RUNNING, SandboxStatus.READY):
                logger.info(f"Reusing existing sandbox for session {session_id}")
                existing.update_activity()
                return existing.sandbox
            else:
                # Clean up failed/killed session
                del self._sessions[session_id]
        
        timeout = timeout_ms or self.config.timeout_ms
        last_error = None
        
        for attempt in range(1, self.config.max_retries + 1):
            try:
                logger.info(
                    f"Creating sandbox for session {session_id} "
                    f"(attempt {attempt}/{self.config.max_retries})"
                )
                
                # Build kwargs for Sandbox.create()
                create_kwargs = {
                    "timeout": timeout // 1000,  # E2B uses seconds
                    "api_key": self._api_key,
                }
                
                if self._template_id:
                    create_kwargs["template"] = self._template_id
                
                if metadata:
                    create_kwargs["metadata"] = metadata
                
                # E2B Sandbox.create() is the correct way to create a sandbox
                loop = asyncio.get_event_loop()
                sandbox = await loop.run_in_executor(
                    None,
                    lambda: Sandbox.create(**create_kwargs)
                )
                
                # Track the session
                session = SandboxSession(
                    sandbox=sandbox,
                    session_id=session_id,
                    status=SandboxStatus.RUNNING,
                )
                self._sessions[session_id] = session
                
                logger.info(
                    f"Sandbox created for session {session_id}: "
                    f"sandbox_id={sandbox.sandbox_id}"
                )
                
                return sandbox
                
            except Exception as e:
                last_error = e
                logger.warning(
                    f"Sandbox creation failed (attempt {attempt}): {e}"
                )
                
                if attempt < self.config.max_retries:
                    delay = self.config.retry_delay_seconds * (2 ** (attempt - 1))
                    logger.info(f"Retrying in {delay} seconds...")
                    await asyncio.sleep(delay)
        
        # All retries failed
        error_msg = f"Failed to create sandbox after {self.config.max_retries} attempts: {last_error}"
        logger.error(error_msg)
        raise SandboxCreationError(error_msg)
    
    async def get_sandbox(self, session_id: str) -> Sandbox:
        """
        Get existing sandbox for session.
        
        Args:
            session_id: Session identifier
            
        Returns:
            The Sandbox instance
            
        Raises:
            SandboxNotFoundError: If no sandbox exists for session
        """
        session = self._sessions.get(session_id)
        if not session:
            raise SandboxNotFoundError(f"No sandbox found for session: {session_id}")
        
        if session.status in (SandboxStatus.ERROR, SandboxStatus.KILLED):
            raise SandboxError(
                f"Sandbox for session {session_id} is in {session.status.value} state"
            )
        
        session.update_activity()
        return session.sandbox
    
    async def get_session(self, session_id: str) -> SandboxSession:
        """
        Get sandbox session with metadata.
        
        Args:
            session_id: Session identifier
            
        Returns:
            The SandboxSession object
            
        Raises:
            SandboxNotFoundError: If no session exists
        """
        session = self._sessions.get(session_id)
        if not session:
            raise SandboxNotFoundError(f"No sandbox session found: {session_id}")
        return session
    
    async def extend_timeout(
        self,
        session_id: str,
        additional_ms: int = 60_000,
    ) -> None:
        """
        Extend sandbox timeout during active operations.
        
        Call this before long-running operations to prevent timeout.
        
        Args:
            session_id: Session identifier
            additional_ms: Additional time in milliseconds
        """
        sandbox = await self.get_sandbox(session_id)
        session = self._sessions[session_id]
        
        try:
            # E2B set_timeout resets timeout from NOW
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None,
                lambda: sandbox.set_timeout(additional_ms // 1000)
            )
            
            session.update_activity()
            logger.debug(
                f"Extended timeout for session {session_id} by {additional_ms}ms"
            )
            
        except Exception as e:
            logger.warning(f"Failed to extend timeout for {session_id}: {e}")
    
    async def clone_repo(
        self,
        session_id: str,
        repo_url: str,
        branch: str,
        depth: int = 1,
        directory_name: Optional[str] = None,
    ) -> str:
        """
        Clone a repository inside the sandbox.
        
        Args:
            session_id: Session identifier
            repo_url: Git repository URL
            branch: Branch to clone
            depth: Clone depth (default: 1 for shallow clone)
            directory_name: Optional custom directory name
            
        Returns:
            Path to cloned repository inside sandbox
            
        Raises:
            SandboxOperationError: If cloning fails
        """
        sandbox = await self.get_sandbox(session_id)
        session = self._sessions[session_id]
        session.status = SandboxStatus.CLONING
        
        # Extract repo name from URL for directory name
        if directory_name is None:
            # Handle both https://github.com/owner/repo.git and owner/repo formats
            repo_name = repo_url.rstrip('/').rstrip('.git').split('/')[-1]
            owner = repo_url.rstrip('/').rstrip('.git').split('/')[-2]
            directory_name = f"{owner}-{repo_name}"
        
        clone_path = f"{self.REPOS_DIR}/{directory_name}"
        
        # Build git clone command
        clone_cmd = f"git clone --depth {depth} --branch {branch} {repo_url} {clone_path}"
        
        logger.info(
            f"Cloning {repo_url} (branch: {branch}) to {clone_path} "
            f"for session {session_id}"
        )
        
        try:
            # Extend timeout for clone operation
            await self.extend_timeout(session_id, 120_000)  # 2 minutes
            
            # Run clone command
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None,
                lambda: sandbox.commands.run(clone_cmd, timeout=120)
            )
            
            if result.exit_code != 0:
                error_msg = result.stderr or result.stdout or "Unknown error"
                raise SandboxOperationError(
                    f"Git clone failed with exit code {result.exit_code}: {error_msg}"
                )
            
            session.repo_path = clone_path
            session.status = SandboxStatus.READY
            session.update_activity()
            
            logger.info(f"Successfully cloned repository to {clone_path}")
            return clone_path
            
        except SandboxOperationError:
            session.status = SandboxStatus.ERROR
            raise
        except Exception as e:
            session.status = SandboxStatus.ERROR
            error_msg = f"Clone operation failed: {e}"
            logger.error(error_msg)
            raise SandboxOperationError(error_msg) from e
    
    async def read_file(
        self,
        session_id: str,
        file_path: str,
    ) -> str:
        """
        Read file content from sandbox.
        
        Args:
            session_id: Session identifier
            file_path: Path to file inside sandbox
            
        Returns:
            File content as string
            
        Raises:
            SandboxOperationError: If file read fails
        """
        sandbox = await self.get_sandbox(session_id)
        session = self._sessions[session_id]
        
        try:
            loop = asyncio.get_event_loop()
            content = await loop.run_in_executor(
                None,
                lambda: sandbox.files.read(file_path)
            )
            
            session.update_activity()
            return content
            
        except Exception as e:
            error_msg = f"Failed to read file {file_path}: {e}"
            logger.error(error_msg)
            raise SandboxOperationError(error_msg) from e
    
    async def read_file_binary(
        self,
        session_id: str,
        file_path: str,
    ) -> bytes:
        """
        Read file as binary from sandbox.
        
        Args:
            session_id: Session identifier
            file_path: Path to file inside sandbox
            
        Returns:
            File content as bytes
            
        Raises:
            SandboxOperationError: If file read fails
        """
        # E2B files.read returns string, and binary are handled differently
        content = await self.read_file(session_id, file_path)
        return content.encode('utf-8')
    
    async def write_file(
        self,
        session_id: str,
        file_path: str,
        content: str,
    ) -> None:
        """
        Write content to file in sandbox.
        
        Args:
            session_id: Session identifier
            file_path: Path to file inside sandbox
            content: Content to write
            
        Raises:
            SandboxOperationError: If file write fails
        """
        sandbox = await self.get_sandbox(session_id)
        session = self._sessions[session_id]
        
        try:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None,
                lambda: sandbox.files.write(file_path, content)
            )
            
            session.update_activity()
            logger.debug(f"Wrote {len(content)} chars to {file_path}")
            
        except Exception as e:
            error_msg = f"Failed to write file {file_path}: {e}"
            logger.error(error_msg)
            raise SandboxOperationError(error_msg) from e
    
    async def list_files(
        self,
        session_id: str,
        directory: str,
        pattern: Optional[str] = None,
    ) -> List[str]:
        """
        List files in sandbox directory.
        
        Args:
            session_id: Session identifier
            directory: Directory path inside sandbox
            pattern: Optional glob pattern to filter files
            
        Returns:
            List of file paths
            
        Raises:
            SandboxOperationError: If listing fails
        """
        sandbox = await self.get_sandbox(session_id)
        session = self._sessions[session_id]
        
        try:
            loop = asyncio.get_event_loop()
            
            if pattern:
                # Use find command with pattern
                cmd = f"find {directory} -name '{pattern}' -type f"
            else:
                # List directory
                cmd = f"find {directory} -type f"
            
            result = await loop.run_in_executor(
                None,
                lambda: sandbox.commands.run(cmd, timeout=30)
            )
            
            session.update_activity()
            
            if result.exit_code != 0:
                # Directory might not exist or be empty
                if "No such file or directory" in (result.stderr or ""):
                    return []
                raise SandboxOperationError(
                    f"List files failed: {result.stderr or result.stdout}"
                )
            
            # Parse output - one file per line
            files = [
                f.strip() for f in result.stdout.strip().split('\n')
                if f.strip()
            ]
            
            return files
            
        except SandboxOperationError:
            raise
        except Exception as e:
            error_msg = f"Failed to list files in {directory}: {e}"
            logger.error(error_msg)
            raise SandboxOperationError(error_msg) from e
    
    async def run_command(
        self,
        session_id: str,
        command: str,
        timeout: int = 60,
        workdir: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Run a command in the sandbox.
        
        Args:
            session_id: Session identifier
            command: Command to run
            timeout: Command timeout in seconds
            workdir: Optional working directory
            
        Returns:
            Dict with 'exit_code', 'stdout', 'stderr'
            
        Raises:
            SandboxOperationError: If command execution fails
        """
        sandbox = await self.get_sandbox(session_id)
        session = self._sessions[session_id]
        
        try:
            # Extend timeout for long commands
            if timeout > 30:
                await self.extend_timeout(session_id, (timeout + 30) * 1000)
            
            # Build command with optional workdir
            if workdir:
                full_cmd = f"cd {workdir} && {command}"
            else:
                full_cmd = command
            
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None,
                lambda: sandbox.commands.run(full_cmd, timeout=timeout)
            )
            
            session.update_activity()
            
            return {
                "exit_code": result.exit_code,
                "stdout": result.stdout or "",
                "stderr": result.stderr or "",
            }
            
        except Exception as e:
            error_msg = f"Command execution failed: {e}"
            logger.error(error_msg)
            raise SandboxOperationError(error_msg) from e
    
    async def clone_fork_repo(
        self,
        session_id: str,
        fork_owner: str,
        fork_repo: str,
        branch: str,
        base_owner: str,
        base_repo: str,
        base_branch: str = "main",
        depth: int = 1,
    ) -> str:
        """
        Clone a fork repository and set up upstream for diff comparison.
        
        This is the primary method for cloning PR repos:
        - Clones from fork (head) repository
        - Adds upstream remote pointing to base repository
        - Fetches base branch from upstream for diff comparison
        
        Args:
            session_id: Session identifier
            fork_owner: Fork repository owner (PR head owner)
            fork_repo: Fork repository name (PR head repo)
            branch: Branch to clone (PR head branch)
            base_owner: Base repository owner (PR base owner)
            base_repo: Base repository name (PR base repo)
            base_branch: Base branch for diff comparison (e.g., "main")
            depth: Clone depth (default: 1 for shallow clone)
            
        Returns:
            Path to cloned repository inside sandbox
            
        Raises:
            SandboxOperationError: If cloning fails
        """
        sandbox = await self.get_sandbox(session_id)
        session = self._sessions[session_id]
        session.status = SandboxStatus.CLONING
        
        # Build directory name and paths
        directory_name = f"{fork_owner}-{fork_repo}"
        clone_path = f"{self.REPOS_DIR}/{directory_name}"
        fork_url = f"https://github.com/{fork_owner}/{fork_repo}.git"
        base_url = f"https://github.com/{base_owner}/{base_repo}.git"
        
        is_fork = fork_owner != base_owner or fork_repo != base_repo
        
        logger.info(
            f"Cloning {'fork ' if is_fork else ''}{fork_owner}/{fork_repo} "
            f"(branch: {branch}) for session {session_id}"
        )
        
        try:
            # Extend timeout for clone operation
            await self.extend_timeout(session_id, 180_000)  # 3 minutes
            
            loop = asyncio.get_event_loop()
            
            # Step 1: Clone the fork/head repository
            clone_cmd = f"git clone --depth {depth} --branch {branch} {fork_url} {clone_path}"
            
            result = await loop.run_in_executor(
                None,
                lambda: sandbox.commands.run(clone_cmd, timeout=120)
            )
            
            if result.exit_code != 0:
                error_msg = result.stderr or result.stdout or "Unknown error"
                raise SandboxOperationError(
                    f"Git clone failed with exit code {result.exit_code}: {error_msg}"
                )
            
            logger.info(f"Successfully cloned repository to {clone_path}")
            
            # Step 2: For fork PRs, add upstream and fetch base branch
            if is_fork:
                logger.info(f"Setting up upstream remote: {base_owner}/{base_repo}")
                
                # Add upstream remote
                add_remote_cmd = f"cd {clone_path} && git remote add upstream {base_url}"
                await loop.run_in_executor(
                    None,
                    lambda: sandbox.commands.run(add_remote_cmd, timeout=30)
                )
                
                # Fetch base branch from upstream with enough history for merge-base
                # Using --unshallow or fetching with more depth to get merge base
                fetch_cmd = f"cd {clone_path} && git fetch --depth=100 upstream {base_branch}"
                fetch_result = await loop.run_in_executor(
                    None,
                    lambda: sandbox.commands.run(fetch_cmd, timeout=120)
                )
                
                if fetch_result.exit_code == 0:
                    logger.info(f"Fetched upstream/{base_branch} for diff comparison")
                else:
                    logger.warning(
                        f"Failed to fetch upstream base branch: "
                        f"{fetch_result.stderr or fetch_result.stdout}"
                    )
                
                # Deepen local history to find merge-base
                deepen_cmd = f"cd {clone_path} && git fetch --deepen=100 origin {branch}"
                await loop.run_in_executor(
                    None,
                    lambda: sandbox.commands.run(deepen_cmd, timeout=60)
                )
            else:
                # Same-repo PR: just fetch origin base branch if needed
                fetch_cmd = f"cd {clone_path} && git fetch --depth=1 origin {base_branch}"
                await loop.run_in_executor(
                    None,
                    lambda: sandbox.commands.run(fetch_cmd, timeout=60)
                )
            
            session.repo_path = clone_path
            session.status = SandboxStatus.READY
            session.update_activity()
            
            return clone_path
            
        except SandboxOperationError:
            session.status = SandboxStatus.ERROR
            raise
        except Exception as e:
            session.status = SandboxStatus.ERROR
            error_msg = f"Clone fork operation failed: {e}"
            logger.error(error_msg)
            raise SandboxOperationError(error_msg) from e
    
    async def get_diff(
        self,
        session_id: str,
        base_branch: str = "main",
        changed_files: Optional[List[str]] = None,
    ) -> Dict[str, List[int]]:
        """
        Get valid line numbers from git diff in sandbox.
        
        Tries multiple diff refs to handle both fork and same-repo PRs:
        1. upstream/{base_branch}...HEAD (for fork PRs)
        2. origin/{base_branch}...HEAD (for same-repo PRs)
        3. {base_branch}...HEAD (local branch)
        
        Args:
            session_id: Session identifier
            base_branch: Base branch for comparison
            changed_files: Optional list of specific files to diff
            
        Returns:
            Dict mapping filename -> list of valid line numbers
            
        Raises:
            SandboxOperationError: If diff fails
        """
        session = self._sessions.get(session_id)
        if not session or not session.repo_path:
            raise SandboxOperationError("No repository cloned for this session")
        
        repo_path = session.repo_path
        sandbox = await self.get_sandbox(session_id)
        loop = asyncio.get_event_loop()
        
        # Try multiple diff refs
        diff_refs = [
            f"upstream/{base_branch}...HEAD",  # Fork PRs with merge-base
            f"upstream/{base_branch}..HEAD",   # Fork PRs direct diff (no merge-base)
            f"origin/{base_branch}...HEAD",    # Same-repo PRs
            f"origin/{base_branch}..HEAD",     # Same-repo direct diff
            f"{base_branch}...HEAD",           # Local branch
        ]
        
        diff_output = None
        used_ref = None
        
        for diff_ref in diff_refs:
            cmd = f"cd {repo_path} && git diff {diff_ref}"
            
            if changed_files:
                files_str = " ".join(f'"{f}"' for f in changed_files)
                cmd += f" -- {files_str}"
            
            logger.debug(f"Trying diff with ref: {diff_ref}")
            
            result = await loop.run_in_executor(
                None,
                lambda cmd=cmd: sandbox.commands.run(cmd, timeout=60)
            )
            
            if result.exit_code == 0 and result.stdout and result.stdout.strip():
                diff_output = result.stdout
                used_ref = diff_ref
                logger.info(f"Git diff successful with ref: {diff_ref}")
                break
        
        if not diff_output:
            # Last resort: HEAD~1
            logger.warning("All diff refs failed, falling back to HEAD~1")
            cmd = f"cd {repo_path} && git diff HEAD~1"
            if changed_files:
                files_str = " ".join(f'"{f}"' for f in changed_files)
                cmd += f" -- {files_str}"
            
            result = await loop.run_in_executor(
                None,
                lambda: sandbox.commands.run(cmd, timeout=60)
            )
            
            if result.exit_code != 0 or not result.stdout:
                logger.error(f"All git diff attempts failed")
                return {}
            
            diff_output = result.stdout
            used_ref = "HEAD~1"
        
        # Parse diff to get valid lines
        valid_lines = self._parse_diff_output(diff_output)
        
        logger.info(
            f"Parsed diff using {used_ref}: {len(valid_lines)} files, "
            f"{sum(len(lines) for lines in valid_lines.values())} total valid lines"
        )
        
        return valid_lines
    
    async def get_diff_text(
        self,
        session_id: str,
        base_branch: str = "main",
        changed_files: Optional[List[str]] = None,
    ) -> Dict[str, str]:
        """
        Get raw diff text per file in sandbox.
        
        Args:
            session_id: Session identifier
            base_branch: Base branch for comparison
            changed_files: Optional list of specific files to diff
            
        Returns:
            Dict mapping filename -> diff text
        """
        session = self._sessions.get(session_id)
        if not session or not session.repo_path:
            raise SandboxOperationError("No repository cloned for this session")
        
        repo_path = session.repo_path
        sandbox = await self.get_sandbox(session_id)
        loop = asyncio.get_event_loop()
        
        # Try upstream first, then origin
        diff_refs = [
            f"upstream/{base_branch}...HEAD",
            f"upstream/{base_branch}..HEAD",   # Direct diff without merge-base
            f"origin/{base_branch}...HEAD",
            f"origin/{base_branch}..HEAD",     # Direct diff without merge-base
            "HEAD~1",
        ]
        
        diff_output = None
        
        for diff_ref in diff_refs:
            cmd = f"cd {repo_path} && git diff {diff_ref}"
            if changed_files:
                files_str = " ".join(f'"{f}"' for f in changed_files)
                cmd += f" -- {files_str}"
            
            result = await loop.run_in_executor(
                None,
                lambda cmd=cmd: sandbox.commands.run(cmd, timeout=60)
            )
            
            if result.exit_code == 0 and result.stdout:
                diff_output = result.stdout
                break
        
        if not diff_output:
            return {}
        
        # Parse into per-file diffs
        return self._parse_diff_per_file(diff_output)
    
    def _parse_diff_output(self, diff_output: str) -> Dict[str, List[int]]:
        """Parse git diff output to extract valid line numbers per file."""
        import re
        
        result = {}
        
        if not diff_output:
            return result
        
        # Match file headers
        file_pattern = re.compile(r'^diff --git a/(.+?) b/(.+?)$', re.MULTILINE)
        hunk_pattern = re.compile(r'@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@')
        
        # Find all file sections
        matches = list(file_pattern.finditer(diff_output))
        
        for i, match in enumerate(matches):
            filename = match.group(2)  # Use b/ path
            
            # Get content for this file
            start = match.end()
            end = matches[i + 1].start() if i + 1 < len(matches) else len(diff_output)
            file_diff = diff_output[start:end]
            
            # Parse hunks
            valid_lines = []
            current_line = 0
            in_hunk = False
            
            for line in file_diff.split('\n'):
                # Check for hunk header
                hunk_match = hunk_pattern.match(line)
                if hunk_match:
                    new_start = int(hunk_match.group(1))
                    current_line = new_start
                    in_hunk = True
                    continue
                
                if not in_hunk:
                    continue
                
                # Skip metadata
                if line.startswith('diff ') or line.startswith('index ') or \
                   line.startswith('--- ') or line.startswith('+++ '):
                    continue
                
                # Process content
                if line.startswith('-'):
                    # Deleted line - skip
                    continue
                elif line.startswith('+'):
                    # Added line - valid for comments
                    valid_lines.append(current_line)
                    current_line += 1
                else:
                    # Context line - also valid
                    valid_lines.append(current_line)
                    current_line += 1
            
            if valid_lines:
                result[filename] = valid_lines
        
        return result
    
    def _parse_diff_per_file(self, diff_output: str) -> Dict[str, str]:
        """Parse git diff output into per-file diff text."""
        import re
        
        result = {}
        
        if not diff_output:
            return result
        
        file_pattern = re.compile(r'^diff --git a/(.+?) b/(.+?)$', re.MULTILINE)
        matches = list(file_pattern.finditer(diff_output))
        
        for i, match in enumerate(matches):
            filename = match.group(2)
            start = match.start()
            end = matches[i + 1].start() if i + 1 < len(matches) else len(diff_output)
            result[filename] = diff_output[start:end]
        
        return result
    
    async def kill_sandbox(self, session_id: str) -> bool:
        """
        Kill and cleanup sandbox for session.
        
        Args:
            session_id: Session identifier
            
        Returns:
            True if sandbox was killed, False if not found
        """
        session = self._sessions.get(session_id)
        if not session:
            logger.debug(f"No sandbox to kill for session {session_id}")
            return False
        
        try:
            logger.info(f"Killing sandbox for session {session_id}")
            
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None,
                lambda: session.sandbox.kill()
            )
            
            session.status = SandboxStatus.KILLED
            del self._sessions[session_id]
            
            logger.info(f"Sandbox killed for session {session_id}")
            return True
            
        except Exception as e:
            logger.warning(f"Error killing sandbox for {session_id}: {e}")
            # Still remove from tracking
            session.status = SandboxStatus.KILLED
            if session_id in self._sessions:
                del self._sessions[session_id]
            return True
    
    async def cleanup_all(self) -> int:
        """
        Cleanup all sandboxes (for shutdown).
        
        Returns:
            Number of sandboxes cleaned up
        """
        session_ids = list(self._sessions.keys())
        cleaned = 0
        
        for session_id in session_ids:
            try:
                if await self.kill_sandbox(session_id):
                    cleaned += 1
            except Exception as e:
                logger.warning(f"Error cleaning up session {session_id}: {e}")
        
        logger.info(f"Cleaned up {cleaned} sandboxes")
        return cleaned
    
    def get_active_sessions(self) -> List[str]:
        """Get list of active session IDs."""
        return [
            sid for sid, session in self._sessions.items()
            if session.status in (SandboxStatus.RUNNING, SandboxStatus.READY)
        ]
    
    def get_session_status(self, session_id: str) -> Optional[SandboxStatus]:
        """Get status of a session."""
        session = self._sessions.get(session_id)
        return session.status if session else None


# Convenience function for creating manager with env config
def create_sandbox_manager() -> SandboxManager:
    """
    Create a SandboxManager with configuration from environment variables.
    
    Environment variables:
    - E2B_API_KEY: Required
    - E2B_SANDBOX_TIMEOUT_MS: Optional, default 300000 (5 min)
    - E2B_TEMPLATE_ID: Optional, uses default template if not set
    - E2B_MAX_RETRIES: Optional, default 3
    - E2B_RETRY_DELAY_SECONDS: Optional, default 5
    
    Returns:
        Configured SandboxManager instance
    """
    config = SandboxConfig(
        api_key=os.getenv("E2B_API_KEY"),
        timeout_ms=int(os.getenv("E2B_SANDBOX_TIMEOUT_MS", "300000")),
        template_id=os.getenv("E2B_TEMPLATE_ID") or None,
        max_retries=int(os.getenv("E2B_MAX_RETRIES", "3")),
        retry_delay_seconds=float(os.getenv("E2B_RETRY_DELAY_SECONDS", "5")),
    )
    
    return SandboxManager(config)
