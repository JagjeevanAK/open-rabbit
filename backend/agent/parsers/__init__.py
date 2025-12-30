"""
Parsers Module
Provides AST parsing, semantic analysis, and analysis pipeline for source code.
"""

from agent.parsers.ast_module.ast_parser import (
    parse_code,
    parse_file,
    print_ast,
    get_language_from_extension,
    is_supported_language,
    EXTENSION_MAP,
)

from agent.parsers.semantic.semantic_builder import (
    SemanticNode,
    SemanticEdge,
    EdgeType,
    SemanticGraph,
    SemanticGraphBuilder,
    build_semantic_graph_from_ast,
    build_semantic_graph_from_all,
)

from agent.parsers.pipeline import (
    AnalysisPipeline,
    analyze_code,
    analyze_file,
)

from agent.parsers.analysis_reports import (
    generate_ast_report,
    generate_semantic_report,
)

__all__ = [
    # AST Parser
    "parse_code",
    "parse_file",
    "print_ast",
    "get_language_from_extension",
    "is_supported_language",
    "EXTENSION_MAP",
    # Semantic
    "SemanticNode",
    "SemanticEdge",
    "EdgeType",
    "SemanticGraph",
    "SemanticGraphBuilder",
    "build_semantic_graph_from_ast",
    "build_semantic_graph_from_all",
    # Pipeline
    "AnalysisPipeline",
    "analyze_code",
    "analyze_file",
    # Reports
    "generate_ast_report",
    "generate_semantic_report",
]
