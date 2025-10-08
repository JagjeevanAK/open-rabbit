from pathlib import Path
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

if __name__ == "__main__":
    print(file_delete_tool(
        file_path="example/test.py"
    ))
