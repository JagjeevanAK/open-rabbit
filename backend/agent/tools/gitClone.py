import subprocess
import os
import re
from pathlib import Path
from typing import Optional
from langchain_core.tools import tool


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


@tool
def get_repo_info_tool(repo_url: str) -> str:
    """
    Get information about a GitHub repository without cloning it.
    Uses GitHub API to fetch metadata.
    
    Args:
        repo_url: GitHub repository URL or shorthand (e.g., 'username/repo')
    
    Returns:
        Formatted repository information or error message
    """
    try:
        import requests
        
        full_url, repo_name = parse_github_url(repo_url)
        
        match = re.search(r'github\.com[:/]([^/]+)/([^/\.]+)', full_url)
        if not match:
            return f"Error: Could not parse repository URL"
        
        owner, repo = match.groups()
        
        api_url = f"https://api.github.com/repos/{owner}/{repo}"
        response = requests.get(api_url, timeout=10)
        
        if response.status_code == 404:
            return f"Error: Repository '{owner}/{repo}' not found"
        elif response.status_code != 200:
            return f"Error: GitHub API returned status {response.status_code}"
        
        data = response.json()
        
        output = [
            f"Repository Information",
            f"{'='*60}",
            f"",
            f"Name: {data['name']}",
            f"Owner: {data['owner']['login']}",
            f"Description: {data.get('description', 'N/A')}",
            f"",
            f"Stats:",
            f"  Stars: {data['stargazers_count']:,}",
            f"  Forks: {data['forks_count']:,}",
            f"  Watchers: {data['watchers_count']:,}",
            f"  Open Issues: {data['open_issues_count']:,}",
            f"",
            f"Details:",
            f"  Language: {data.get('language', 'N/A')}",
            f"  License: {data.get('license', {}).get('name', 'N/A')}",
            f"  Default Branch: {data['default_branch']}",
            f"  Created: {data['created_at'][:10]}",
            f"  Last Updated: {data['updated_at'][:10]}",
            f"",
            f"URL: {data['html_url']}"
        ]
        
        return "\n".join(output)
        
    except ImportError:
        return "Error: 'requests' library not installed. Run: pip install requests"
    except requests.Timeout:
        return "Error: Request timed out. Please check your internet connection"
    except Exception as e:
        return f"Error: {type(e).__name__}: {str(e)}"


if __name__ == "__main__":
    print("=== Git Clone Tool Examples ===\n")
    
    print("1. Clone using shorthand (username/repo):")
    print(git_clone_tool("facebook/react", destination_path="./repos/react"))
    
    print("\n2. Clone using full URL:")
    print(git_clone_tool("https://github.com/python/cpython", depth=1))
    
    print("\n3. Clone specific branch:")
    print(git_clone_tool("microsoft/typescript", branch="main", depth=1))
    
    print("\n4. Get repository information:")
    print(get_repo_info_tool("openai/whisper"))
