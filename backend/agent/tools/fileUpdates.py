import difflib
from pathlib import Path
from typing import Literal, Optional
from langchain_core.tools import tool

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


if __name__ == "__main__":
    print(file_writer_tool(
        action="create",
        file_path="example/test.py",
        content="def hello():\n    print('Hello, World!')\n"
    ))
    
    print(file_writer_tool(
        action="patch",
        file_path="example/test.py",
        old_content="def hello():\n    print('Hello, World!')",
        content="def hello(name='World'):\n    print(f'Hello, {name}!')"
    ))
    
    print(file_writer_tool(
        action="overwrite",
        file_path="example/test.py",
        content="# Completely new content\nprint('Fresh start!')\n"
    ))
