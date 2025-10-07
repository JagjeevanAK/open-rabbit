import os

EXCLUDE_DIRS = {"node_modules", "__pycache__", ".git", ".venv", "dist", "build"}
INCLUDE_EXTS = {".py", ".ts", ".js", ".tsx", ".jsx", ".java", ".cpp", ".h"}

def read_project_files(base_dir: str, max_file_size: int = 100_000):
    """
    Reads all relevant source files from the project directory.
    Returns a list of dicts with file_path and content.
    """
    project_files = []

    for root, dirs, files in os.walk(base_dir):
        dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]

        for file in files:
            ext = os.path.splitext(file)[1]
            if ext not in INCLUDE_EXTS:
                continue

            file_path = os.path.join(root, file)
            try:
                if os.path.getsize(file_path) > max_file_size:
                    print(f"Skipping large file: {file_path}")
                    continue
                with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()
                project_files.append({"path": file_path, "content": content})
            except Exception as e:
                print(f"Error reading {file_path}: {e}")

    return project_files
