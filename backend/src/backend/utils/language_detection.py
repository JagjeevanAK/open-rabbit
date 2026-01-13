
EXTENSION_TO_LANGUAGE = {
    ".py": "python",
    ".js": "javascript",
    ".jsx": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".java": "java",
    ".go": "go",
    ".rs": "rust",
    ".rb": "ruby",
    ".php": "php",
    ".cs": "csharp",
    ".cpp": "cpp",
    ".c": "c",
    ".h": "c",
    ".hpp": "cpp",
    ".swift": "swift",
    ".kt": "kotlin",
    ".scala": "scala",
    ".r": "r",
    ".R": "r",
    ".sql": "sql",
    ".sh": "bash",
    ".bash": "bash",
    ".zsh": "zsh",
    ".yaml": "yaml",
    ".yml": "yaml",
    ".json": "json",
    ".xml": "xml",
    ".html": "html",
    ".css": "css",
    ".scss": "scss",
    ".sass": "sass",
    ".less": "less",
    ".md": "markdown",
    ".vue": "vue",
    ".svelte": "svelte",
}


def detect_language(file_path: str) -> str:
    """
    Detect programming language from file extension.
    
    Args:
        file_path: Path to the file
        
    Returns:
        Language identifier string, or "unknown" if not recognized
    """
    for ext, lang in EXTENSION_TO_LANGUAGE.items():
        if file_path.endswith(ext):
            return lang
    
    return "unknown"


def is_code_file(file_path: str) -> bool:
    """
    Check if a file is a recognized code file.
    
    Args:
        file_path: Path to the file
        
    Returns:
        True if the file extension is recognized as code
    """
    return detect_language(file_path) != "unknown"


def is_test_file(file_path: str) -> bool:
    """
    Check if a file appears to be a test file.
    
    Args:
        file_path: Path to the file
        
    Returns:
        True if the file appears to be a test file
    """
    # Common test file patterns
    test_patterns = [
        "_test.",
        ".test.",
        "_spec.",
        ".spec.",
        "test_",
        "tests/",
        "__tests__/",
        "spec/",
    ]
    
    file_lower = file_path.lower()
    return any(pattern in file_lower for pattern in test_patterns)
