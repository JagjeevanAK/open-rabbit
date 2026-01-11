"""
Sandbox File Operations

File tools that operate on E2B sandbox filesystem.
These replace local filesystem operations when sandbox is active.

All file operations are performed through the SandboxManager which
communicates with the E2B sandbox instance.
"""

import logging
from typing import Optional, List, TYPE_CHECKING

if TYPE_CHECKING:
    from agent.services.sandbox_manager import SandboxManager

logger = logging.getLogger(__name__)


async def sandbox_read_file(
    sandbox_manager: "SandboxManager",
    session_id: str,
    file_path: str,
) -> str:
    """
    Read file content from sandbox.
    
    Args:
        sandbox_manager: The sandbox manager instance
        session_id: Current session ID
        file_path: Path to file inside sandbox
        
    Returns:
        Formatted file content with metadata
    """
    try:
        content = await sandbox_manager.read_file(session_id, file_path)
        lines = content.count('\n') + 1
        chars = len(content)
        
        return f"""File: {file_path}
Stats: {lines} lines, {chars} characters

{'='*60}
{content}
{'='*60}"""
    except Exception as e:
        return f"Error reading file '{file_path}': {type(e).__name__}: {str(e)}"


async def sandbox_read_file_raw(
    sandbox_manager: "SandboxManager",
    session_id: str,
    file_path: str,
) -> str:
    """
    Read raw file content from sandbox (no formatting).
    
    Args:
        sandbox_manager: The sandbox manager instance
        session_id: Current session ID
        file_path: Path to file inside sandbox
        
    Returns:
        Raw file content
        
    Raises:
        Exception: If file read fails
    """
    return await sandbox_manager.read_file(session_id, file_path)


async def sandbox_read_file_with_line_numbers(
    sandbox_manager: "SandboxManager",
    session_id: str,
    file_path: str,
    start_line: int = 1,
    end_line: Optional[int] = None,
) -> str:
    """
    Read file content with line numbers from sandbox.
    
    Args:
        sandbox_manager: The sandbox manager instance
        session_id: Current session ID
        file_path: Path to file inside sandbox
        start_line: Starting line number (1-indexed)
        end_line: Ending line number (1-indexed, None for end of file)
        
    Returns:
        File content with line numbers
    """
    try:
        content = await sandbox_manager.read_file(session_id, file_path)
        lines = content.splitlines()
        total_lines = len(lines)
        
        # Adjust indices
        start_idx = max(0, start_line - 1)
        end_idx = total_lines if end_line is None else min(end_line, total_lines)
        
        # Format with line numbers
        max_line_num = end_idx
        line_num_width = len(str(max_line_num))
        
        formatted_lines = []
        for i in range(start_idx, end_idx):
            line_num = i + 1
            formatted_lines.append(f"{line_num:>{line_num_width}} | {lines[i]}")
        
        return "\n".join(formatted_lines)
        
    except Exception as e:
        return f"Error reading file '{file_path}': {type(e).__name__}: {str(e)}"


async def sandbox_list_files(
    sandbox_manager: "SandboxManager",
    session_id: str,
    directory_path: str,
    pattern: Optional[str] = None,
    recursive: bool = True,
) -> str:
    """
    List files in sandbox directory.
    
    Args:
        sandbox_manager: The sandbox manager instance
        session_id: Current session ID
        directory_path: Path to directory inside sandbox
        pattern: Optional glob pattern to filter files
        recursive: Whether to search recursively (default True)
        
    Returns:
        Formatted list of files
    """
    try:
        files = await sandbox_manager.list_files(
            session_id, 
            directory_path, 
            pattern
        )
        
        if not files:
            msg = f"No files found in '{directory_path}'"
            if pattern:
                msg += f" matching '{pattern}'"
            return msg
        
        output = [f"Found {len(files)} file(s) in '{directory_path}'"]
        if pattern:
            output[0] += f" matching '{pattern}'"
        output.append("=" * 60)
        
        for f in files[:100]:  # Limit to 100 files
            # Make path relative to directory_path for cleaner output
            rel_path = f
            if f.startswith(directory_path):
                rel_path = f[len(directory_path):].lstrip('/')
            output.append(f"  {rel_path}")
        
        if len(files) > 100:
            output.append(f"\n  ... and {len(files) - 100} more files")
        
        return "\n".join(output)
        
    except Exception as e:
        return f"Error listing files in '{directory_path}': {type(e).__name__}: {str(e)}"


async def sandbox_list_files_raw(
    sandbox_manager: "SandboxManager",
    session_id: str,
    directory_path: str,
    pattern: Optional[str] = None,
) -> List[str]:
    """
    List files in sandbox directory (returns raw list).
    
    Args:
        sandbox_manager: The sandbox manager instance
        session_id: Current session ID
        directory_path: Path to directory inside sandbox
        pattern: Optional glob pattern to filter files
        
    Returns:
        List of file paths
    """
    return await sandbox_manager.list_files(session_id, directory_path, pattern)


async def sandbox_write_file(
    sandbox_manager: "SandboxManager",
    session_id: str,
    file_path: str,
    content: str,
) -> str:
    """
    Write content to file in sandbox.
    
    Args:
        sandbox_manager: The sandbox manager instance
        session_id: Current session ID
        file_path: Path to file inside sandbox
        content: Content to write
        
    Returns:
        Success or error message
    """
    try:
        await sandbox_manager.write_file(session_id, file_path, content)
        return f"Successfully wrote {len(content)} characters to {file_path}"
    except Exception as e:
        return f"Error writing file '{file_path}': {type(e).__name__}: {str(e)}"


async def sandbox_file_exists(
    sandbox_manager: "SandboxManager",
    session_id: str,
    file_path: str,
) -> bool:
    """
    Check if file exists in sandbox.
    
    Args:
        sandbox_manager: The sandbox manager instance
        session_id: Current session ID
        file_path: Path to file inside sandbox
        
    Returns:
        True if file exists, False otherwise
    """
    try:
        result = await sandbox_manager.run_command(
            session_id,
            f"test -f {file_path} && echo 'exists' || echo 'not found'"
        )
        return "exists" in result.get("stdout", "")
    except Exception:
        return False


async def sandbox_get_file_info(
    sandbox_manager: "SandboxManager",
    session_id: str,
    file_path: str,
) -> dict:
    """
    Get file metadata from sandbox.
    
    Args:
        sandbox_manager: The sandbox manager instance
        session_id: Current session ID
        file_path: Path to file inside sandbox
        
    Returns:
        Dict with file info (size, lines, etc.)
    """
    try:
        # Get file stats using stat command
        result = await sandbox_manager.run_command(
            session_id,
            f"stat -c '%s' {file_path} && wc -l < {file_path}"
        )
        
        if result.get("exit_code") != 0:
            return {"error": result.get("stderr", "File not found")}
        
        lines = result.get("stdout", "").strip().split('\n')
        size = int(lines[0]) if lines else 0
        line_count = int(lines[1]) if len(lines) > 1 else 0
        
        return {
            "path": file_path,
            "size_bytes": size,
            "line_count": line_count,
            "exists": True,
        }
        
    except Exception as e:
        return {"error": str(e), "exists": False}


async def sandbox_find_test_framework(
    sandbox_manager: "SandboxManager",
    session_id: str,
    directory_path: str,
) -> str:
    """
    Detect testing framework in sandbox repository.
    
    Args:
        sandbox_manager: The sandbox manager instance
        session_id: Current session ID
        directory_path: Path to repository root
        
    Returns:
        Formatted detection results
    """
    try:
        # Check for common config files
        configs = {
            "pytest": ["pytest.ini", "pyproject.toml", "setup.cfg"],
            "jest": ["jest.config.js", "jest.config.ts", "jest.config.mjs"],
            "vitest": ["vitest.config.ts", "vitest.config.js"],
            "mocha": [".mocharc.json", ".mocharc.js", ".mocharc.yml"],
        }
        
        detected_framework = "unknown"
        confidence = "low"
        config_files_found = []
        
        for framework, config_files in configs.items():
            for config in config_files:
                exists = await sandbox_file_exists(
                    sandbox_manager, 
                    session_id, 
                    f"{directory_path}/{config}"
                )
                if exists:
                    config_files_found.append(config)
                    if detected_framework == "unknown":
                        detected_framework = framework
                        confidence = "medium"
        
        # Check for test files
        test_files = await sandbox_manager.list_files(
            session_id,
            directory_path,
            "test_*.py"
        )
        test_files.extend(await sandbox_manager.list_files(
            session_id,
            directory_path,
            "*.test.ts"
        ))
        test_files.extend(await sandbox_manager.list_files(
            session_id,
            directory_path,
            "*.spec.ts"
        ))
        
        if len(test_files) > 0 and detected_framework != "unknown":
            confidence = "high"
        
        # Build output
        output = ["Testing Framework Detection Results", "=" * 60]
        output.append(f"\nFramework: {detected_framework.upper()}")
        output.append(f"Confidence: {confidence.upper()}")
        
        if config_files_found:
            output.append(f"\nConfiguration files found:")
            for f in config_files_found:
                output.append(f"  - {f}")
        
        if test_files:
            output.append(f"\nFound {len(test_files)} test file(s):")
            for f in test_files[:10]:
                output.append(f"  - {f}")
            if len(test_files) > 10:
                output.append(f"  ... and {len(test_files) - 10} more")
        
        return "\n".join(output)
        
    except Exception as e:
        return f"Error detecting test framework: {type(e).__name__}: {str(e)}"


class SandboxFileOperations:
    """
    Wrapper class for sandbox file operations.
    
    Provides a convenient interface for file operations with
    automatic session management.
    """
    
    def __init__(
        self, 
        sandbox_manager: "SandboxManager", 
        session_id: str
    ):
        """
        Initialize file operations for a session.
        
        Args:
            sandbox_manager: The sandbox manager instance
            session_id: Current session ID
        """
        self._manager = sandbox_manager
        self._session_id = session_id
    
    async def read(self, file_path: str) -> str:
        """Read file content."""
        return await sandbox_read_file_raw(
            self._manager, self._session_id, file_path
        )
    
    async def read_formatted(self, file_path: str) -> str:
        """Read file with formatting and metadata."""
        return await sandbox_read_file(
            self._manager, self._session_id, file_path
        )
    
    async def read_lines(
        self, 
        file_path: str, 
        start: int = 1, 
        end: Optional[int] = None
    ) -> str:
        """Read file lines with line numbers."""
        return await sandbox_read_file_with_line_numbers(
            self._manager, self._session_id, file_path, start, end
        )
    
    async def write(self, file_path: str, content: str) -> str:
        """Write content to file."""
        return await sandbox_write_file(
            self._manager, self._session_id, file_path, content
        )
    
    async def list(
        self, 
        directory: str, 
        pattern: Optional[str] = None
    ) -> List[str]:
        """List files in directory."""
        return await sandbox_list_files_raw(
            self._manager, self._session_id, directory, pattern
        )
    
    async def exists(self, file_path: str) -> bool:
        """Check if file exists."""
        return await sandbox_file_exists(
            self._manager, self._session_id, file_path
        )
    
    async def info(self, file_path: str) -> dict:
        """Get file info."""
        return await sandbox_get_file_info(
            self._manager, self._session_id, file_path
        )
