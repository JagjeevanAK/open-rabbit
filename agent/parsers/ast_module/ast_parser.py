"""
AST Parser with Tree-Sitter

Provides AST parsing capabilities for multiple languages:
- Python
- JavaScript
- TypeScript
- TSX
"""

from typing import Union, Optional
from tree_sitter import Language, Parser
import tree_sitter_python as tspython
import tree_sitter_javascript as tsjavascript
import tree_sitter_typescript as tstypescript

# Initialize language objects
PY_LANGUAGE = Language(tspython.language())
JS_LANGUAGE = Language(tsjavascript.language())
TS_LANGUAGE = Language(tstypescript.language_typescript())
TSX_LANGUAGE = Language(tstypescript.language_tsx())

# Pre-configured parsers for each language
parsers = {
    "python": Parser(PY_LANGUAGE),
    "javascript": Parser(JS_LANGUAGE),
    "typescript": Parser(TS_LANGUAGE),
    "tsx": Parser(TSX_LANGUAGE)
}

# Extension to language mapping
EXTENSION_MAP = {
    ".py": "python",
    ".js": "javascript",
    ".jsx": "javascript",
    ".ts": "typescript",
    ".tsx": "tsx",
    ".mjs": "javascript",
    ".cjs": "javascript",
}


def get_language_from_extension(file_path: str) -> Optional[str]:
    """
    Detect language from file extension.
    
    Args:
        file_path: Path to source file
        
    Returns:
        Language name or None if not supported
    """
    import os
    ext = os.path.splitext(file_path)[1].lower()
    return EXTENSION_MAP.get(ext)


def is_supported_language(file_path: str) -> bool:
    """Check if file extension is supported"""
    return get_language_from_extension(file_path) is not None


def parse_code(code: Union[str, bytes], language: str = "python"):
    """
    Parse source code and return AST.
    
    Args:
        code: Source code as a string or bytes
        language: Programming language (python, javascript, typescript, tsx)
    
    Returns:
        Tree-sitter AST tree object
    """
    if isinstance(code, str):
        code = code.encode('utf-8')
    
    if language not in parsers:
        raise ValueError(f"Unsupported language: {language}. Supported: {list(parsers.keys())}")
    
    return parsers[language].parse(code)


def parse_file(file_path: str, language: Optional[str] = None):
    """
    Parse a source file and return AST.
    
    Args:
        file_path: Path to source file
        language: Programming language (auto-detected if not provided)
    
    Returns:
        Tree-sitter AST tree object
    """
    if language is None:
        language = get_language_from_extension(file_path)
        if language is None:
            raise ValueError(f"Could not detect language for file: {file_path}")
    
    with open(file_path, 'r', encoding='utf-8') as f:
        code = f.read()
    
    return parse_code(code, language)


def print_ast(node, indent: int = 0, max_depth: int = 10):
    """
    Pretty print AST tree.
    
    Args:
        node: AST node
        indent: Indentation level
        max_depth: Maximum depth to print
    """
    if indent > max_depth:
        print("  " * indent + "...")
        return
    
    print("  " * indent + f"{node.type}", end="")
    if node.child_count == 0:
        text = node.text.decode('utf-8')
        if len(text) < 50:
            print(f": {text}", end="")
    print()
    
    for child in node.children:
        print_ast(child, indent + 1, max_depth)


def get_node_text(node, source_code: Optional[bytes] = None) -> str:
    """
    Get the text content of a node.
    
    Args:
        node: AST node
        source_code: Optional source code bytes
        
    Returns:
        Text content as string
    """
    if source_code is not None and hasattr(node, "start_byte") and hasattr(node, "end_byte"):
        try:
            return source_code[node.start_byte:node.end_byte].decode("utf-8", errors="replace")
        except Exception:
            pass
    
    raw = getattr(node, "text", None)
    if raw is None:
        return ""
    if isinstance(raw, bytes):
        return raw.decode("utf-8", errors="replace")
    return str(raw)


def get_node_lines(node) -> tuple:
    """
    Get 1-indexed start and end line numbers for a node.
    
    Args:
        node: AST node
        
    Returns:
        Tuple of (start_line, end_line), both 1-indexed
    """
    start = getattr(node, "start_point", None)
    end = getattr(node, "end_point", None)
    
    start_line = (start[0] + 1) if start else None
    end_line = (end[0] + 1) if end else None
    
    return start_line, end_line
