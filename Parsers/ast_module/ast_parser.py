"""
AST Parser with CFG and PDG Pipeline Integration

This module provides AST parsing capabilities and integrates with 
Control Flow Graph (CFG) and Program Dependence Graph (PDG) builders.
"""

from typing import Union
from tree_sitter import Language, Parser
import tree_sitter_python as tspython
import tree_sitter_javascript as tsjavascript
import tree_sitter_typescript as tstypescript

# Load languages using the API
PY_LANGUAGE = Language(tspython.language())
JS_LANGUAGE = Language(tsjavascript.language())
TS_LANGUAGE = Language(tstypescript.language_typescript())
TSX_LANGUAGE = Language(tstypescript.language_tsx())

# Make a parser for each
parsers = {
    "python": Parser(PY_LANGUAGE),
    "javascript": Parser(JS_LANGUAGE),
    "typescript": Parser(TS_LANGUAGE),
    "tsx": Parser(TSX_LANGUAGE)
}

def parse_code(code: Union[str, bytes], language: str = "python"):
    """
    Parse source code and return AST
    
    Args:
        code: Source code as a string or bytes
        language: Programming language (python, javascript, typescript, tsx)
        language: Programming language (python, javascript, typescript, tsx)
    
    Returns:
        Tree-sitter AST tree object
    """
    if isinstance(code, str):
        code = code.encode('utf-8')
    
    if language not in parsers:
        raise ValueError(f"Unsupported language: {language}")
    
    return parsers[language].parse(code)


def parse_file(file_path: str, language: str = "python"):
    """
    Parse a source file and return AST
    
    Args:
        file_path: Path to source file
        language: Programming language
    
    Returns:
        Tree-sitter AST tree object
    """
    with open(file_path, 'r', encoding='utf-8') as f:
        code = f.read()
    
    return parse_code(code, language)


def print_ast(node, indent=0):
    """
    Pretty print AST tree
    
    Args:
        node: AST node
        indent: Indentation level
    """
    print("  " * indent + f"{node.type}", end="")
    if node.child_count == 0:
        text = node.text.decode('utf-8')
        if len(text) < 50:
            print(f": {text}", end="")
    print()
    
    for child in node.children:
        print_ast(child, indent + 1)  
