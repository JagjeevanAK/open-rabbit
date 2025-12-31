"""
E2B Sandbox Manager

Manages E2B sandbox lifecycle for code review sessions.
One sandbox per review session, with automatic cleanup.

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
                
                # Create sandbox with E2B SDK
                sandbox_kwargs = {
                    "timeout": timeout // 1000,  # E2B uses seconds
                    "api_key": self._api_key,
                }
                
                if self._template_id:
                    sandbox_kwargs["template"] = self._template_id
                
                if metadata:
                    sandbox_kwargs["metadata"] = metadata
                
                # E2B Sandbox.create is synchronous, run in executor
                loop = asyncio.get_event_loop()
                sandbox = await loop.run_in_executor(
                    None,
                    lambda: Sandbox(**sandbox_kwargs)
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
        # E2B files.read returns string, we need to handle binary differently
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
