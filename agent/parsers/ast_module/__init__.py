"""
AST Module - Tree-sitter based AST parsing for multiple languages
"""

from .ast_parser import (
    parse_code,
    parse_file,
    print_ast,
    parsers,
    get_language_from_extension,
    is_supported_language,
    get_node_text,
    get_node_lines,
    EXTENSION_MAP,
)

__all__ = [
    'parse_code',
    'parse_file',
    'print_ast',
    'parsers',
    'get_language_from_extension',
    'is_supported_language',
    'get_node_text',
    'get_node_lines',
    'EXTENSION_MAP',
]
