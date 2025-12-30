"""
Backend Agent Module

Multi-agent code review system with:
- Supervisor Agent: Main orchestration
- Parser Agent: Static analysis (AST, security, complexity)
- Review Agent: LLM-powered code review
- Feedback Agent: User feedback processing

Legacy:
- CodeReviewWorkflow: Old workflow (deprecated)
"""

# New multi-agent system
from .supervisor import SupervisorAgent, Reducer, KBFilter, reduce_issues, filter_with_kb
from .subagents import BaseAgent, ParserAgent, ReviewAgent, FeedbackAgent
from .schemas.common import (
    ReviewRequest,
    ReviewIssue,
    SupervisorConfig,
    SupervisorOutput,
    FileChange,
    PRContext,
    Severity,
    IssueCategory,
    AgentStatus,
)

# Legacy (deprecated)
from .workflow import CodeReviewWorkflow
from .mock_llm import MockLLM

__all__ = [
    # New multi-agent system
    "SupervisorAgent",
    "Reducer",
    "KBFilter",
    "reduce_issues",
    "filter_with_kb",
    "BaseAgent",
    "ParserAgent",
    "ReviewAgent",
    "FeedbackAgent",
    # Schemas
    "ReviewRequest",
    "ReviewIssue",
    "SupervisorConfig",
    "SupervisorOutput",
    "FileChange",
    "PRContext",
    "Severity",
    "IssueCategory",
    "AgentStatus",
    # Legacy
    "CodeReviewWorkflow",
    "MockLLM",
]

