"""
Agent Schema Definitions

Pydantic models for agent inputs, outputs, and shared types.
"""

from .common import (
    AgentStatus,
    Severity,
    IssueCategory,
    FileChange,
    ReviewRequest,
    ReviewIssue,
    PRContext,
    KBContext,
    SupervisorOutput,
    SupervisorConfig,
)

from .parser_output import (
    FunctionInfo,
    ClassInfo,
    VariableInfo,
    ImportInfo,
    SecurityIssue,
    SecurityPattern,
    DeadCodeInfo,
    ComplexityIssue,
    ParserInput,
    ParserOutput,
)

from .review_output import (
    FileContent,
    ReviewInput,
    ReviewOutput,
)

from .test_output import (
    TestFramework,
    TestType,
    GeneratedTest,
    TestInput,
    TestOutput,
)

__all__ = [
    # Common
    "AgentStatus",
    "Severity", 
    "IssueCategory",
    "FileChange",
    "ReviewRequest",
    "ReviewIssue",
    "PRContext",
    "KBContext",
    "SupervisorOutput",
    "SupervisorConfig",
    # Parser
    "FunctionInfo",
    "ClassInfo",
    "VariableInfo",
    "ImportInfo",
    "SecurityIssue",
    "SecurityPattern",
    "DeadCodeInfo",
    "ComplexityIssue",
    "ParserInput",
    "ParserOutput",
    # Review
    "FileContent",
    "ReviewInput",
    "ReviewOutput",
    # Test
    "TestFramework",
    "TestType",
    "GeneratedTest",
    "TestInput",
    "TestOutput",
]
