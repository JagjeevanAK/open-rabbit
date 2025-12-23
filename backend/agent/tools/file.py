import difflib
from pathlib import Path
from typing import Literal, Optional
from langchain_core.tools import tool

@tool
def file_delete_tool(
    file_path: str,
    missing_ok: bool = False,
) -> str:
    """
    Delete a file from the filesystem.
    
    Args:
        file_path: Path to the file to delete (relative or absolute)
        missing_ok: If True, no error is raised if file doesn't exist
    
    Returns:
        Success or error message describing the operation result
    """
    try:
        path = Path(file_path)
        
        if not path.exists():
            if missing_ok:
                return f"File '{file_path}' does not exist (ignored)"
            return f"Error: File '{file_path}' does not exist"
        
        if path.is_dir():
            return f"Error: '{file_path}' is a directory. Use directory deletion tool instead"
        
        file_size = path.stat().st_size
        path.unlink()
        
        return f"Successfully deleted file: {file_path} ({file_size} bytes)"
        
    except PermissionError:
        return f"Error: Permission denied to delete '{file_path}'"
    except Exception as e:
        return f"Error: {type(e).__name__}: {str(e)}"

@tool
def file_reader_tool(
    file_path: str,
    encoding: str = "utf-8"
) -> str:
    """
    Read and return the contents of a file.
    
    Args:
        file_path: Path to the file to read (relative or absolute)
        encoding: File encoding (default: utf-8)
    
    Returns:
        File contents with metadata or error message
    """
    try:
        path = Path(file_path)
        
        if not path.exists():
            return f"Error: File '{file_path}' does not exist"
        
        if not path.is_file():
            return f"Error: '{file_path}' is not a file (it's a directory)"
        
        file_size = path.stat().st_size
        if file_size > 1_000_000:
            return f"Error: File is too large ({file_size} bytes). Maximum size is 1MB"
        
        content = path.read_text(encoding=encoding)
        
        lines = content.count('\n') + 1
        chars = len(content)
        
        return f"""File: {file_path}
Stats: {lines} lines, {chars} characters

{'='*60}
{content}
{'='*60}"""
        
    except UnicodeDecodeError:
        return f"Error: Cannot decode file with {encoding} encoding. Try a different encoding or this might be a binary file."
    except PermissionError:
        return f"Error: Permission denied to read '{file_path}'"
    except Exception as e:
        return f"Error: {type(e).__name__}: {str(e)}"


@tool
def list_files_tool(
    directory_path: str = ".",
    pattern: Optional[str] = None,
    recursive: bool = False
) -> str:
    """
    List files in a directory, optionally filtering by pattern.
    
    Args:
        directory_path: Path to the directory to list (default: current directory)
        pattern: Glob pattern to filter files (e.g., '*.py', 'test_*.py', '*.test.ts')
        recursive: Whether to search recursively in subdirectories
    
    Returns:
        Formatted list of files or error message
    """
    try:
        path = Path(directory_path)
        
        if not path.exists():
            return f"Error: Directory '{directory_path}' does not exist"
        
        if not path.is_dir():
            return f"Error: '{directory_path}' is not a directory"
        
        if pattern:
            if recursive:
                files = list(path.rglob(pattern))
            else:
                files = list(path.glob(pattern))
        else:
            if recursive:
                files = [f for f in path.rglob("*") if f.is_file()]
            else:
                files = [f for f in path.glob("*") if f.is_file()]
        
        if not files:
            return f"No files found in '{directory_path}'" + (f" matching '{pattern}'" if pattern else "")
        
        files = sorted(files)
        output = [f"Found {len(files)} file(s) in '{directory_path}'" + (f" matching '{pattern}'" if pattern else "")]
        output.append("=" * 60)
        
        for f in files[:50]:
            rel_path = f.relative_to(path) if f.is_relative_to(path) else f
            size = f.stat().st_size
            size_str = f"{size:,} bytes" if size < 1024 else f"{size/1024:.1f} KB"
            output.append(f"  {rel_path} ({size_str})")
        
        if len(files) > 50:
            output.append(f"\n  ... and {len(files) - 50} more files")
        
        return "\n".join(output)
        
    except PermissionError:
        return f"Error: Permission denied to access '{directory_path}'"
    except Exception as e:
        return f"Error: {type(e).__name__}: {str(e)}"


@tool
def find_test_framework_tool(directory_path: str = ".") -> str:
    """
    Automatically detect the testing framework used in a project.
    
    Args:
        directory_path: Path to the project directory (default: current directory)
    
    Returns:
        Detection results with framework name, confidence, and found files
    """
    try:
        path = Path(directory_path)
        
        if not path.exists():
            return f"Error: Directory '{directory_path}' does not exist"
        
        findings = {
            "test_files": [],
            "config_files": [],
            "framework": "unknown",
            "confidence": "low"
        }
        
        test_patterns = [
            "test_*.py", "*_test.py",
            "*.test.js", "*.test.ts", "*.spec.js", "*.spec.ts"
        ]
        
        for pattern in test_patterns:
            files = list(path.rglob(pattern))
            findings["test_files"].extend(files)
        
        config_files = [
            "pytest.ini", "pyproject.toml", "setup.cfg",
            "jest.config.js", "jest.config.ts", "vitest.config.ts", 
            "package.json"
        ]
        
        for config in config_files:
            config_path = path / config
            if config_path.exists():
                findings["config_files"].append(config_path)
        
        framework_indicators = {
            "pytest": ["import pytest", "@pytest.", "pytest."],
            "unittest": ["import unittest", "unittest.TestCase"],
            "jest": ["describe(", "test(", "expect(", "jest."],
            "vitest": ["import { test", "import { describe", "vi.mock"],
            "mocha": ["describe(", "it(", "expect(", "chai"]
        }
        
        framework_scores = {fw: 0 for fw in framework_indicators.keys()}
        
        for test_file in findings["test_files"][:5]:
            try:
                content = test_file.read_text(encoding="utf-8")
                for framework, indicators in framework_indicators.items():
                    for indicator in indicators:
                        if indicator in content:
                            framework_scores[framework] += 1
            except:
                continue
        
        if framework_scores:
            detected_framework = max(framework_scores, key=framework_scores.get)
            if framework_scores[detected_framework] > 0:
                findings["framework"] = detected_framework
                findings["confidence"] = "high" if framework_scores[detected_framework] >= 3 else "medium"
        
        output = ["Testing Framework Detection Results", "=" * 60]
        
        output.append(f"\nFramework: {findings['framework'].upper()}")
        output.append(f"Confidence: {findings['confidence'].upper()}")
        
        if findings["test_files"]:
            output.append(f"\nFound {len(findings['test_files'])} test file(s):")
            for f in findings["test_files"][:10]:
                output.append(f"  - {f.relative_to(path)}")
            if len(findings["test_files"]) > 10:
                output.append(f"  ... and {len(findings['test_files']) - 10} more")
        else:
            output.append("\nNo test files found")
        
        if findings["config_files"]:
            output.append(f"\nConfiguration files:")
            for f in findings["config_files"]:
                output.append(f"  - {f.name}")
        
        return "\n".join(output)
        
    except Exception as e:
        return f"Error: {type(e).__name__}: {str(e)}"


@tool
def file_writer_tool(
    action: Literal["create", "patch", "overwrite"],
    file_path: str,
    content: str,
    old_content: Optional[str] = None,
    create_directories: bool = True,
) -> str:
    """
    Write, create, or patch files on the filesystem.
    
    Args:
        action: 'create' for new files, 'patch' to apply changes, 'overwrite' to replace entire file
        file_path: Path to the file (relative or absolute)
        content: For 'create'/'overwrite': full file content. For 'patch': the new version of the code section
        old_content: For 'patch' only: the exact old content to replace (must match precisely)
        create_directories: Whether to create parent directories if they don't exist
    
    Returns:
        Success or error message describing the operation result
    """
    try:
        path = Path(file_path)
        
        if create_directories and not path.parent.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            
        if action == "create":
            if path.exists():
                return f"Error: File '{file_path}' already exists. Use 'overwrite' or 'patch' to modify it."
            
            path.write_text(content, encoding="utf-8")
            return f"Successfully created file: {file_path} ({len(content)} chars)"
            
        elif action == "overwrite":
            path.write_text(content, encoding="utf-8")
            existed = "Updated" if path.exists() else "Created"
            return f"{existed} file: {file_path} ({len(content)} chars)"
            
        elif action == "patch":
            if not path.exists():
                return f"Error: File '{file_path}' does not exist. Use 'create' action first."
            
            if old_content is None:
                return "Error: 'old_content' is required for patch action"
            
            current_content = path.read_text(encoding="utf-8")
            
            if old_content not in current_content:
                diff = list(difflib.unified_diff(
                    old_content.splitlines(keepends=True),
                    current_content.splitlines(keepends=True),
                    fromfile="expected",
                    tofile="actual",
                    lineterm=""
                ))
                diff_str = "".join(diff[:20])
                
                return f"Error: Could not find old_content in file.\n\nDiff preview:\n{diff_str}\n\nMake sure old_content matches exactly (including whitespace)."
            
            new_content = current_content.replace(old_content, content, 1)
            path.write_text(new_content, encoding="utf-8")
            
            lines_changed = len(content.splitlines()) - len(old_content.splitlines())
            return f"Successfully patched file: {file_path} ({lines_changed:+d} lines)"
            
    except PermissionError:
        return f"Error: Permission denied to write to '{file_path}'"
    except Exception as e:
        return f"Error: {type(e).__name__}: {str(e)}"
