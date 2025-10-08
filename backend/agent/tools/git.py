import subprocess
from pathlib import Path
from typing import Optional, List, Literal
from langchain_core.tools import tool
from pydantic import BaseModel, Field


class GitAddInput(BaseModel):
    """Input schema for git add."""
    files: List[str] = Field(
        description="List of file paths to stage. Use ['.'] to add all files"
    )
    repo_path: str = Field(
        default=".",
        description="Path to git repository (default: current directory)"
    )


class GitCommitInput(BaseModel):
    """Input schema for git commit."""
    message: str = Field(
        description="Commit message describing the changes"
    )
    repo_path: str = Field(
        default=".",
        description="Path to git repository (default: current directory)"
    )


class GitBranchInput(BaseModel):
    """Input schema for git branch operations."""
    branch_name: str = Field(
        description="Name of the branch to create or switch to"
    )
    action: Literal["create", "checkout", "create_and_checkout"] = Field(
        default="create_and_checkout",
        description="Action: 'create' (new branch), 'checkout' (switch), 'create_and_checkout' (both)"
    )
    repo_path: str = Field(
        default=".",
        description="Path to git repository (default: current directory)"
    )


class GitStatusInput(BaseModel):
    """Input schema for git status."""
    repo_path: str = Field(
        default=".",
        description="Path to git repository (default: current directory)"
    )


class GitLogInput(BaseModel):
    """Input schema for git log."""
    max_count: int = Field(
        default=10,
        description="Maximum number of commits to show"
    )
    repo_path: str = Field(
        default=".",
        description="Path to git repository (default: current directory)"
    )


class GitPushInput(BaseModel):
    """Input schema for git push."""
    remote: str = Field(
        default="origin",
        description="Remote name (default: origin)"
    )
    branch: Optional[str] = Field(
        default=None,
        description="Branch to push (default: current branch)"
    )
    set_upstream: bool = Field(
        default=True,
        description="Set upstream tracking (use for first push of new branch)"
    )
    repo_path: str = Field(
        default=".",
        description="Path to git repository (default: current directory)"
    )


class GitDiffInput(BaseModel):
    """Input schema for git diff."""
    staged: bool = Field(
        default=False,
        description="Show staged changes (default: show unstaged changes)"
    )
    file_path: Optional[str] = Field(
        default=None,
        description="Specific file to show diff for (default: all files)"
    )
    repo_path: str = Field(
        default=".",
        description="Path to git repository (default: current directory)"
    )


def run_git_command(cmd: List[str], repo_path: str = ".") -> tuple[bool, str]:
    """Helper function to run git commands."""
    try:
        result = subprocess.run(
            cmd,
            cwd=repo_path,
            capture_output=True,
            text=True,
            timeout=30
        )
        
        output = result.stdout.strip() if result.stdout else result.stderr.strip()
        return result.returncode == 0, output
        
    except subprocess.TimeoutExpired:
        return False, "Command timed out"
    except FileNotFoundError:
        return False, "Git is not installed or not found in PATH"
    except Exception as e:
        return False, f"{type(e).__name__}: {str(e)}"


@tool(args_schema=GitAddInput)
def git_add_tool(files: List[str], repo_path: str = ".") -> str:
    """
    Stage files for commit using 'git add'.
    
    Use this to:
    - Stage specific files: git_add_tool(["file1.py", "file2.js"])
    - Stage all changes: git_add_tool(["."])
    """
    
    cmd = ["git", "add"] + files
    success, output = run_git_command(cmd, repo_path)
    
    if success:
        return f"✅ Successfully staged files: {', '.join(files)}"
    else:
        return f"❌ Failed to stage files:\n{output}"


@tool(args_schema=GitCommitInput)
def git_commit_tool(message: str, repo_path: str = ".") -> str:
    """
    Create a git commit with the provided message.
    
    The message should be descriptive and follow conventional commit format:
    - feat: Add new feature
    - fix: Fix bug
    - test: Add tests
    - docs: Update documentation
    - refactor: Refactor code
    """
    
    cmd = ["git", "commit", "-m", message]
    success, output = run_git_command(cmd, repo_path)
    
    if success:
        return f"✅ Successfully created commit:\n{output}"
    else:
        if "nothing to commit" in output.lower():
            return "⚠️  Nothing to commit. Stage files first using git_add_tool."
        return f"❌ Failed to commit:\n{output}"


@tool(args_schema=GitBranchInput)
def git_branch_tool(
    branch_name: str,
    action: Literal["create", "checkout", "create_and_checkout"] = "create_and_checkout",
    repo_path: str = "."
) -> str:
    """
    Create or switch git branches.
    
    Actions:
    - create: Create new branch (stays on current branch)
    - checkout: Switch to existing branch
    - create_and_checkout: Create new branch and switch to it (default)
    """
    
    if action == "create":
        cmd = ["git", "branch", branch_name]
        success, output = run_git_command(cmd, repo_path)
        
        if success:
            return f"✅ Created branch '{branch_name}'"
        else:
            if "already exists" in output.lower():
                return f"⚠️  Branch '{branch_name}' already exists"
            return f"❌ Failed to create branch:\n{output}"
    
    elif action == "checkout":
        cmd = ["git", "checkout", branch_name]
        success, output = run_git_command(cmd, repo_path)
        
        if success:
            return f"✅ Switched to branch '{branch_name}'"
        else:
            return f"❌ Failed to checkout branch:\n{output}"
    
    else:  # create_and_checkout
        cmd = ["git", "checkout", "-b", branch_name]
        success, output = run_git_command(cmd, repo_path)
        
        if success:
            return f"✅ Created and switched to branch '{branch_name}'"
        else:
            if "already exists" in output.lower():
                return f"⚠️  Branch '{branch_name}' already exists. Use action='checkout' to switch to it."
            return f"❌ Failed to create branch:\n{output}"


@tool(args_schema=GitStatusInput)
def git_status_tool(repo_path: str = ".") -> str:
    """
    Show the working tree status.
    
    Use this to:
    - Check what files are modified
    - See what's staged for commit
    - Check current branch
    """
    
    cmd = ["git", "status"]
    success, output = run_git_command(cmd, repo_path)
    
    if success:
        return f"📊 Git Status:\n\n{output}"
    else:
        return f"❌ Failed to get status:\n{output}"


@tool(args_schema=GitLogInput)
def git_log_tool(max_count: int = 10, repo_path: str = ".") -> str:
    """
    Show commit logs.
    
    Displays recent commits with hash, author, date, and message.
    """
    
    cmd = ["git", "log", f"-{max_count}", "--oneline", "--decorate"]
    success, output = run_git_command(cmd, repo_path)
    
    if success:
        if not output:
            return "📜 No commits yet"
        return f"📜 Recent Commits (last {max_count}):\n\n{output}"
    else:
        return f"❌ Failed to get log:\n{output}"


@tool(args_schema=GitPushInput)
def git_push_tool(
    remote: str = "origin",
    branch: Optional[str] = None,
    set_upstream: bool = True,
    repo_path: str = "."
) -> str:
    """
    Push commits to remote repository.
    
    Use this to:
    - Push current branch: git_push_tool()
    - Push specific branch: git_push_tool(branch="feature-branch")
    - First push of new branch: git_push_tool(set_upstream=True)
    """
    
    # Get current branch if not specified
    if branch is None:
        success, branch_output = run_git_command(
            ["git", "branch", "--show-current"],
            repo_path
        )
        if not success:
            return f"❌ Failed to determine current branch:\n{branch_output}"
        branch = branch_output.strip()
    
    # Build push command
    cmd = ["git", "push"]
    if set_upstream:
        cmd.extend(["-u", remote, branch])
    else:
        cmd.extend([remote, branch])
    
    success, output = run_git_command(cmd, repo_path)
    
    if success:
        return f"✅ Successfully pushed branch '{branch}' to {remote}"
    else:
        if "no upstream branch" in output.lower():
            return f"⚠️  No upstream set. Try with set_upstream=True"
        return f"❌ Failed to push:\n{output}"


@tool(args_schema=GitDiffInput)
def git_diff_tool(
    staged: bool = False,
    file_path: Optional[str] = None,
    repo_path: str = "."
) -> str:
    """
    Show changes between commits, working tree, etc.
    
    Use this to:
    - See unstaged changes: git_diff_tool()
    - See staged changes: git_diff_tool(staged=True)
    - Diff specific file: git_diff_tool(file_path="src/app.py")
    """
    
    cmd = ["git", "diff"]
    
    if staged:
        cmd.append("--staged")
    
    if file_path:
        cmd.append(file_path)
    
    success, output = run_git_command(cmd, repo_path)
    
    if success:
        if not output:
            return "✨ No changes to show"
        return f"📝 Changes:\n\n{output}"
    else:
        return f"❌ Failed to get diff:\n{output}"


@tool
def git_current_branch_tool(repo_path: str = ".") -> str:
    """
    Get the current branch name.
    
    Useful before committing or pushing to know which branch you're on.
    """
    
    cmd = ["git", "branch", "--show-current"]
    success, output = run_git_command(cmd, repo_path)
    
    if success:
        return f"🌿 Current branch: {output}"
    else:
        return f"❌ Failed to get current branch:\n{output}"


@tool
def git_list_branches_tool(repo_path: str = ".") -> str:
    """
    List all branches in the repository.
    
    Shows local branches with an asterisk (*) next to the current branch.
    """
    
    cmd = ["git", "branch", "-a"]
    success, output = run_git_command(cmd, repo_path)
    
    if success:
        return f"🌿 Branches:\n\n{output}"
    else:
        return f"❌ Failed to list branches:\n{output}"


@tool
def git_init_tool(repo_path: str = ".") -> str:
    """
    Initialize a new git repository.
    
    Use this to create a new git repository in a directory.
    """
    
    cmd = ["git", "init"]
    success, output = run_git_command(cmd, repo_path)
    
    if success:
        return f"✅ Initialized git repository in {Path(repo_path).absolute()}"
    else:
        return f"❌ Failed to initialize repository:\n{output}"


# Example workflow for creating a PR
if __name__ == "__main__":
    print("=== Git Tools Suite - Example PR Workflow ===\n")
    
    # Step 1: Check current status
    print("1. Check status:")
    print(git_status_tool())
    
    # Step 2: Create new branch
    print("\n2. Create feature branch:")
    print(git_branch_tool("feature/add-tests"))
    
    # Step 3: Stage files
    print("\n3. Stage test files:")
    print(git_add_tool(["tests/test_calculator.py"]))
    
    # Step 4: Commit changes
    print("\n4. Commit changes:")
    print(git_commit_tool("test: Add unit tests for calculator module"))
    
    # Step 5: Push to remote
    print("\n5. Push to remote:")
    print(git_push_tool())
    
    print("\n✅ Ready to open Pull Request on GitHub!")
    print("   The agent has:")
    print("   - Created a feature branch")
    print("   - Committed the changes")
    print("   - Pushed to remote")
    print("   - You can now open a PR via GitHub UI")


# List of all tools for easy import
GIT_TOOLS = [
    git_add_tool,
    git_commit_tool,
    git_branch_tool,
    git_status_tool,
    git_log_tool,
    git_push_tool,
    git_diff_tool,
    git_current_branch_tool,
    git_list_branches_tool,
    git_init_tool,
]