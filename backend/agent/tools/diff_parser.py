"""
Diff Parser

Parses git diff output to extract line numbers that can receive inline comments.
Used to ensure we only generate review comments on lines that are in the PR diff.
"""

import re
import subprocess
from pathlib import Path
from typing import Dict, List, Tuple, Optional
import logging

logger = logging.getLogger(__name__)


def parse_diff_hunks(diff_text: str) -> List[Tuple[int, int]]:
    """
    Parse a single file's diff and extract line ranges that are in the diff.
    
    Args:
        diff_text: Git diff output for a single file
        
    Returns:
        List of (start_line, end_line) tuples representing lines in the diff
    """
    if not diff_text:
        return []
    
    line_ranges = []
    
    # Match hunk headers: @@ -old_start,old_count +new_start,new_count @@
    hunk_pattern = re.compile(r'@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@')
    
    lines = diff_text.split('\n')
    current_line = 0
    in_hunk = False
    hunk_start = 0
    hunk_lines = []
    
    for line in lines:
        # Check for hunk header
        match = hunk_pattern.match(line)
        if match:
            # Save previous hunk if exists
            if hunk_lines:
                line_ranges.extend(hunk_lines)
                hunk_lines = []
            
            # Parse new hunk
            new_start = int(match.group(1))
            new_count = int(match.group(2)) if match.group(2) else 1
            
            current_line = new_start
            in_hunk = True
            continue
        
        if not in_hunk:
            continue
        
        # Skip diff metadata lines
        if line.startswith('diff ') or line.startswith('index ') or \
           line.startswith('--- ') or line.startswith('+++ '):
            continue
        
        # Process diff content
        if line.startswith('-'):
            # Deleted line - doesn't affect new file line numbers
            continue
        elif line.startswith('+'):
            # Added line - this is a valid line for comments
            hunk_lines.append(current_line)
            current_line += 1
        else:
            # Context line (unchanged) - also valid for comments
            hunk_lines.append(current_line)
            current_line += 1
    
    # Save last hunk
    if hunk_lines:
        line_ranges.extend(hunk_lines)
    
    return line_ranges


def parse_unified_diff(diff_output: str) -> Dict[str, List[int]]:
    """
    Parse full git diff output and extract valid line numbers per file.
    
    Args:
        diff_output: Full git diff output (may contain multiple files)
        
    Returns:
        Dict mapping filename -> list of valid line numbers
    """
    result = {}
    
    if not diff_output:
        return result
    
    # Split by file
    # Each file section starts with "diff --git a/... b/..."
    file_pattern = re.compile(r'^diff --git a/(.+?) b/(.+?)$', re.MULTILINE)
    
    # Find all file boundaries
    matches = list(file_pattern.finditer(diff_output))
    
    for i, match in enumerate(matches):
        filename = match.group(2)  # Use the "b/" path (new file path)
        
        # Get the diff content for this file
        start = match.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(diff_output)
        
        file_diff = diff_output[start:end]
        
        # Parse this file's diff
        valid_lines = parse_diff_hunks(file_diff)
        
        if valid_lines:
            result[filename] = valid_lines
            logger.debug(f"File {filename}: {len(valid_lines)} valid lines for comments")
    
    return result


def get_pr_diff(repo_path: str, base_branch: str = "main", changed_files: Optional[List[str]] = None) -> Dict[str, List[int]]:
    """
    Get git diff between current HEAD and base branch, and extract valid line numbers.
    
    Args:
        repo_path: Path to cloned repository
        base_branch: Base branch of the PR (e.g., "main", "master")
        changed_files: Optional list of specific files to diff
        
    Returns:
        Dict mapping filename -> list of valid line numbers for comments
    """
    try:
        # Try multiple remote/branch combinations
        # For fork PRs, upstream/{base_branch} is set up
        # For same-repo PRs, origin/{base_branch} is used
        diff_refs = [
            f"upstream/{base_branch}...HEAD",  # Fork PRs (upstream remote)
            f"origin/{base_branch}...HEAD",    # Same-repo PRs
            f"{base_branch}...HEAD",           # Local branch
        ]
        
        diff_output = None
        used_ref = None
        
        for diff_ref in diff_refs:
            cmd = ["git", "diff", diff_ref]
            
            # Add specific files if provided
            if changed_files:
                cmd.append("--")
                cmd.extend(changed_files)
            
            logger.info(f"Trying git diff with ref: {diff_ref}")
            
            result = subprocess.run(
                cmd,
                cwd=repo_path,
                capture_output=True,
                text=True,
                timeout=60
            )
            
            if result.returncode == 0 and result.stdout.strip():
                diff_output = result.stdout
                used_ref = diff_ref
                logger.info(f"Git diff successful with ref: {diff_ref}")
                break
            else:
                logger.debug(f"Git diff with {diff_ref} failed or empty: {result.stderr[:100] if result.stderr else 'empty output'}")
        
        if not diff_output:
            # Last resort: diff against HEAD~1 (previous commit)
            logger.warning("All diff refs failed, falling back to HEAD~1")
            cmd = ["git", "diff", "HEAD~1"]
            if changed_files:
                cmd.append("--")
                cmd.extend(changed_files)
            
            result = subprocess.run(
                cmd,
                cwd=repo_path,
                capture_output=True,
                text=True,
                timeout=60
            )
            
            if result.returncode != 0:
                logger.error(f"All git diff attempts failed: {result.stderr}")
                return {}
            
            diff_output = result.stdout
            used_ref = "HEAD~1"
        
        # Parse the diff
        valid_lines = parse_unified_diff(diff_output)
        
        logger.info(f"Parsed diff using {used_ref} for {len(valid_lines)} files")
        for filename, lines in valid_lines.items():
            logger.debug(f"  {filename}: lines {min(lines) if lines else 0}-{max(lines) if lines else 0}")
        
        return valid_lines
        
    except subprocess.TimeoutExpired:
        logger.error("Git diff timed out")
        return {}
    except Exception as e:
        logger.error(f"Error getting PR diff: {e}")
        return {}


def get_diff_text_per_file(repo_path: str, base_branch: str = "main", changed_files: Optional[List[str]] = None) -> Dict[str, str]:
    """
    Get the actual diff text for each file (useful for including in review context).
    
    Args:
        repo_path: Path to cloned repository
        base_branch: Base branch of the PR
        changed_files: Optional list of specific files
        
    Returns:
        Dict mapping filename -> diff text
    """
    try:
        cmd = ["git", "diff", f"origin/{base_branch}...HEAD"]
        
        if changed_files:
            cmd.append("--")
            cmd.extend(changed_files)
        
        result = subprocess.run(
            cmd,
            cwd=repo_path,
            capture_output=True,
            text=True,
            timeout=60
        )
        
        if result.returncode != 0:
            # Fallback to HEAD~1
            cmd = ["git", "diff", "HEAD~1"]
            if changed_files:
                cmd.append("--")
                cmd.extend(changed_files)
            
            result = subprocess.run(
                cmd,
                cwd=repo_path,
                capture_output=True,
                text=True,
                timeout=60
            )
        
        if result.returncode != 0:
            return {}
        
        diff_output = result.stdout
        result_dict = {}
        
        # Split by file
        file_pattern = re.compile(r'^diff --git a/(.+?) b/(.+?)$', re.MULTILINE)
        matches = list(file_pattern.finditer(diff_output))
        
        for i, match in enumerate(matches):
            filename = match.group(2)
            start = match.start()
            end = matches[i + 1].start() if i + 1 < len(matches) else len(diff_output)
            
            result_dict[filename] = diff_output[start:end]
        
        return result_dict
        
    except Exception as e:
        logger.error(f"Error getting diff text: {e}")
        return {}
