import subprocess
import os
import re
import shutil
import tempfile
import logging
from pathlib import Path
from typing import Optional, TYPE_CHECKING
from langchain_core.tools import tool

if TYPE_CHECKING:
    from agent.services.sandbox_manager import SandboxManager

logger = logging.getLogger(__name__)

def parse_github_url(repo_input: str) -> tuple[str, str]:
    """
    Parse various GitHub URL formats and return (full_url, repo_name).
    
    Supports:
    - username/repo
    - https://github.com/username/repo
    - https://github.com/username/repo.git
    - git@github.com:username/repo.git
    """
    repo_input = repo_input.strip().rstrip('/').rstrip('.git')
    
    if '/' in repo_input and not repo_input.startswith(('http://', 'https://', 'git@')):
        parts = repo_input.split('/')
        if len(parts) == 2:
            username, repo = parts
            full_url = f"https://github.com/{username}/{repo}.git"
            return full_url, repo
    
    if repo_input.startswith('https://github.com/'):
        match = re.search(r'github\.com/([^/]+)/([^/]+?)(?:\.git)?$', repo_input)
        if match:
            username, repo = match.groups()
            full_url = f"https://github.com/{username}/{repo}.git"
            return full_url, repo
    
    if repo_input.startswith('git@github.com:'):
        match = re.search(r'git@github\.com:([^/]+)/([^/]+?)(?:\.git)?$', repo_input)
        if match:
            username, repo = match.groups()
            full_url = f"https://github.com/{username}/{repo}.git"
            return full_url, repo
    
    repo_name = repo_input.split('/')[-1].replace('.git', '')
    return repo_input, repo_name


@tool
def git_clone_tool(
    repo_url: str,
    destination_path: Optional[str] = None,
    branch: Optional[str] = None,
    depth: int = 1
) -> str:
    """
    Clone a GitHub repository to the local filesystem with shallow clone (depth=1) for fast downloads.
    
    Args:
        repo_url: GitHub repository URL or shorthand (e.g., 'username/repo' or 'https://github.com/username/repo.git')
        destination_path: Path where to clone the repo. If not provided, uses repo name in current directory
        branch: Specific branch to clone (optional, defaults to default branch)
        depth: Create a shallow clone with history truncated to specified number of commits (default: 1)
    
    Returns:
        Success message with clone location or error message
    
    Supports multiple URL formats:
    - Short form: 'facebook/react'
    - HTTPS: 'https://github.com/facebook/react.git'
    - SSH: 'git@github.com:facebook/react.git'
    
    Always uses shallow clone (depth=1) to download only the latest commit for speed.
    
    Use this to:
    - Clone repositories to analyze code
    - Get test files from existing projects
    - Download source code for unit test generation
    """
    try:
        full_url, repo_name = parse_github_url(repo_url)
        
        if destination_path:
            dest = Path(destination_path)
        else:
            dest = Path.cwd() / repo_name
        
        if dest.exists():
            if any(dest.iterdir()):
                return f"Error: Destination '{dest}' already exists and is not empty. Please choose a different path or remove the existing directory."
        
        cmd = ["git", "clone"]
        
        if branch:
            cmd.extend(["--branch", branch])
        
        cmd.extend(["--depth", str(depth)])
        cmd.extend([full_url, str(dest)])
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300
        )
        
        if result.returncode != 0:
            error_msg = result.stderr.strip()
            
            if "Repository not found" in error_msg or "not found" in error_msg.lower():
                return f"Error: Repository '{repo_url}' not found. Please check:\n  - Repository exists\n  - URL is correct\n  - You have access (for private repos)"
            elif "already exists" in error_msg:
                return f"Error: Destination '{dest}' already exists"
            elif "Could not resolve host" in error_msg:
                return f"Error: Network error. Please check your internet connection"
            else:
                return f"Git clone failed:\n{error_msg}"
        
        return f"Successfully cloned repository '{repo_name}' to: {dest.absolute()}"
        
    except subprocess.TimeoutExpired:
        return f"Error: Clone operation timed out (>5 minutes). Repository might be too large."
    except FileNotFoundError:
        return f"Error: Git is not installed or not found in PATH. Please install Git first."
    except PermissionError:
        return f"Error: Permission denied. Cannot write to destination path."
    except Exception as e:
        return f"Error: {type(e).__name__}: {str(e)}"


async def clone_repo_for_pr(
    owner: str,
    repo: str,
    pr_number: int,
    branch: str,
    installation_id: int,
    base_dir: Optional[str] = None,
) -> Optional[str]:
    """
    Clone a repository for PR review.
    
    Args:
        owner: Repository owner
        repo: Repository name
        pr_number: Pull request number
        branch: Branch to clone
        installation_id: GitHub App installation ID (for authentication)
        base_dir: Base directory for clones (uses temp dir if None)
        
    Returns:
        Path to cloned repository, or None on failure
    """
    try:
        # Create a temp directory for the clone
        if base_dir:
            clone_base = Path(base_dir)
            clone_base.mkdir(parents=True, exist_ok=True)
        else:
            clone_base = Path(tempfile.gettempdir()) / "open-rabbit-clones"
            clone_base.mkdir(parents=True, exist_ok=True)
        
        # Create unique directory for this clone
        clone_dir = clone_base / f"{owner}-{repo}-{pr_number}-{os.getpid()}"
        
        # Clean up if exists
        if clone_dir.exists():
            shutil.rmtree(clone_dir)
        
        # Build clone URL
        # For GitHub App authentication, we'd need to get an installation token
        # For now, use public HTTPS URL (works for public repos)
        clone_url = f"https://github.com/{owner}/{repo}.git"
        
        # TODO: For private repos, get installation access token:
        # token = await get_installation_token(installation_id)
        # clone_url = f"https://x-access-token:{token}@github.com/{owner}/{repo}.git"
        
        logger.info(f"Cloning {owner}/{repo} branch {branch} to {clone_dir}")
        
        # Clone with shallow depth
        cmd = [
            "git", "clone",
            "--depth", "1",
            "--branch", branch,
            clone_url,
            str(clone_dir)
        ]
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300
        )
        
        if result.returncode != 0:
            logger.error(f"Git clone failed: {result.stderr}")
            return None
        
        logger.info(f"Successfully cloned to {clone_dir}")
        return str(clone_dir)
        
    except subprocess.TimeoutExpired:
        logger.error("Clone operation timed out")
        return None
    except Exception as e:
        logger.error(f"Clone failed: {e}")
        return None


def cleanup_repo(repo_path: str) -> bool:
    """
    Clean up a cloned repository.
    
    Args:
        repo_path: Path to the repository to clean up
        
    Returns:
        True if cleanup succeeded, False otherwise
    """
    try:
        path = Path(repo_path)
        if path.exists():
            shutil.rmtree(path)
            logger.info(f"Cleaned up repository at {repo_path}")
            return True
        return True
    except Exception as e:
        logger.error(f"Failed to cleanup repository: {e}")
        return False


def get_changed_files_from_diff(repo_path: str, base_branch: str = "main") -> list[str]:
    """
    Get list of changed files by comparing with base branch.
    
    Args:
        repo_path: Path to the repository
        base_branch: Base branch to compare against
        
    Returns:
        List of changed file paths
    """
    try:
        result = subprocess.run(
            ["git", "diff", "--name-only", f"origin/{base_branch}...HEAD"],
            capture_output=True,
            text=True,
            cwd=repo_path,
            timeout=60
        )
        
        if result.returncode != 0:
            logger.warning(f"Failed to get diff: {result.stderr}")
            return []
        
        files = [f.strip() for f in result.stdout.strip().split("\n") if f.strip()]
        return files
        
    except Exception as e:
        logger.error(f"Failed to get changed files: {e}")
        return []


# =============================================================================
# E2B Sandbox-based Repository Operations
# =============================================================================

async def clone_repo_in_sandbox(
    sandbox_manager: "SandboxManager",
    session_id: str,
    owner: str,
    repo: str,
    branch: str,
    depth: int = 1,
) -> str:
    """
    Clone a repository inside E2B sandbox.
    
    This is the preferred method for cloning repositories as it provides
    isolation and doesn't use local filesystem resources.
    
    Args:
        sandbox_manager: The sandbox manager instance
        session_id: Current session ID
        owner: Repository owner
        repo: Repository name
        branch: Branch to clone
        depth: Clone depth (default: 1 for shallow clone)
        
    Returns:
        Path to cloned repository inside sandbox
        
    Raises:
        SandboxOperationError: If cloning fails
    """
    clone_url = f"https://github.com/{owner}/{repo}.git"
    directory_name = f"{owner}-{repo}"
    
    logger.info(f"Cloning {owner}/{repo} (branch: {branch}) in sandbox for session {session_id}")
    
    return await sandbox_manager.clone_repo(
        session_id=session_id,
        repo_url=clone_url,
        branch=branch,
        depth=depth,
        directory_name=directory_name,
    )


async def clone_repo_for_pr_sandbox(
    sandbox_manager: "SandboxManager",
    session_id: str,
    owner: str,
    repo: str,
    pr_number: int,
    branch: str,
    installation_id: Optional[int] = None,
) -> str:
    """
    Clone a repository for PR review using E2B sandbox.
    
    This replaces the local clone_repo_for_pr function when sandbox is available.
    
    Args:
        sandbox_manager: The sandbox manager instance
        session_id: Current session ID
        owner: Repository owner
        repo: Repository name
        pr_number: Pull request number (for logging/tracking)
        branch: Branch to clone
        installation_id: GitHub App installation ID (for future auth support)
        
    Returns:
        Path to cloned repository inside sandbox
    """
    logger.info(f"Cloning {owner}/{repo} PR #{pr_number} (branch: {branch}) in sandbox")
    
    # TODO: For private repos, we'll need to handle authentication
    # This could involve:
    # 1. Getting an installation access token
    # 2. Passing it to sandbox via environment variable
    # 3. Using authenticated URL: https://x-access-token:{token}@github.com/{owner}/{repo}.git
    
    return await clone_repo_in_sandbox(
        sandbox_manager=sandbox_manager,
        session_id=session_id,
        owner=owner,
        repo=repo,
        branch=branch,
    )


async def get_changed_files_in_sandbox(
    sandbox_manager: "SandboxManager",
    session_id: str,
    repo_path: str,
    base_branch: str = "main",
) -> list[str]:
    """
    Get list of changed files in sandbox repository.
    
    Args:
        sandbox_manager: The sandbox manager instance
        session_id: Current session ID
        repo_path: Path to repository inside sandbox
        base_branch: Base branch to compare against
        
    Returns:
        List of changed file paths (relative to repo root)
    """
    try:
        # First, fetch the base branch for comparison
        fetch_result = await sandbox_manager.run_command(
            session_id,
            f"cd {repo_path} && git fetch origin {base_branch} --depth=1",
            timeout=60
        )
        
        if fetch_result.get("exit_code") != 0:
            logger.warning(f"Failed to fetch base branch: {fetch_result.get('stderr')}")
            # Continue anyway, might work if we have enough history
        
        # Get the diff
        result = await sandbox_manager.run_command(
            session_id,
            f"cd {repo_path} && git diff --name-only origin/{base_branch}...HEAD",
            timeout=30
        )
        
        if result.get("exit_code") != 0:
            logger.warning(f"Failed to get diff: {result.get('stderr')}")
            return []
        
        stdout = result.get("stdout", "")
        files = [f.strip() for f in stdout.strip().split("\n") if f.strip()]
        
        logger.info(f"Found {len(files)} changed files in {repo_path}")
        return files
        
    except Exception as e:
        logger.error(f"Failed to get changed files in sandbox: {e}")
        return []


async def get_file_content_from_sandbox(
    sandbox_manager: "SandboxManager",
    session_id: str,
    file_path: str,
) -> Optional[str]:
    """
    Read file content from sandbox.
    
    Convenience wrapper for sandbox_manager.read_file().
    
    Args:
        sandbox_manager: The sandbox manager instance
        session_id: Current session ID
        file_path: Path to file inside sandbox
        
    Returns:
        File content or None if read fails
    """
    try:
        return await sandbox_manager.read_file(session_id, file_path)
    except Exception as e:
        logger.error(f"Failed to read file {file_path} from sandbox: {e}")
        return None
