"""
Schemas module for agent input/output types.

Provides structured data types for:
- Parser Agent outputs (AST, semantic analysis)
- Code Review Agent outputs (issues, suggestions)
- Unit Test Agent outputs (generated tests)
- Supervisor orchestration types
"""

from .parser_output import (
    FileMetadata,
    Symbol,
    SymbolType,
    CallGraphEntry,
    Hotspot,
    ParserOutput,
)

from .review_output import (
    Severity,
    ReviewIssue,
    ReviewOutput,
)

from .test_output import (
    GeneratedTest,
    TestOutput,
)

from .common import (
    FileInfo,
    KBContext,
    ReviewRequest,
    UserIntent,
    SupervisorOutput,
    AgentStatus,
    CheckpointData,
)

__all__ = [
    # Parser outputs
    "FileMetadata",
    "Symbol",
    "SymbolType",
    "CallGraphEntry",
    "Hotspot",
    "ParserOutput",
    # Review outputs
    "Severity",
    "ReviewIssue",
    "ReviewOutput",
    # Test outputs
    "GeneratedTest",
    "TestOutput",
    # Common types
    "FileInfo",
    "KBContext",
    "ReviewRequest",
    "UserIntent",
    "SupervisorOutput",
    "AgentStatus",
    "CheckpointData",
]
