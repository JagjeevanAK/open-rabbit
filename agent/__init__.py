"""
Backend Agent Module

Multi-Agent Code Review System with Supervisor-Worker Architecture.

Main Components:
- SupervisorAgent: Main orchestrator with LangGraph state machine
- ParserAgent: Code parsing and structure extraction (no LLM)
- CodeReviewAgent: Code review and issue detection
- UnitTestAgent: Unit test generation (explicit request only)

Usage:
    from agent import SupervisorAgent, ReviewRequest, FileInfo
    
    # Create supervisor
    supervisor = SupervisorAgent()
    
    # Create request
    request = ReviewRequest(
        files=[FileInfo(path="src/main.py", content="...")],
        user_request="review this code",
    )
    
    # Run review
    output = await supervisor.run(request)
    
    # Get GitHub-formatted review
    github_review = output.to_github_review()
"""

# Supervisor and orchestration
from .supervisor import (
    SupervisorAgent,
    SupervisorConfig,
    IntentParser,
    ResultAggregator,
)

# Sub-agents
from .subagents import (
    BaseAgent,
    AgentConfig,
    ParserAgent,
    CodeReviewAgent,
    UnitTestAgent,
)

# Schemas and types
from .schemas import (
    # Common types
    FileInfo,
    KBContext,
    ReviewRequest,
    UserIntent,
    SupervisorOutput,
    AgentStatus,
    CheckpointData,
    # Parser output
    ParserOutput,
    FileMetadata,
    Symbol,
    SymbolType,
    CallGraphEntry,
    Hotspot,
    # Review output
    ReviewOutput,
    ReviewIssue,
    Severity,
    # Test output
    TestOutput,
    GeneratedTest,
)

# LLM Factory
from .llm_factory import (
    LLMFactory,
    LLMProvider,
    LLMConfig,
    create_openai_llm,
    create_anthropic_llm,
    create_openrouter_llm,
)

# Production logging
from .logging_config import (
    setup_logging,
    get_logger,
    set_session_id,
    get_session_id,
    log_with_data,
    log_workflow_transition,
    log_agent_start,
    log_agent_complete,
    log_llm_call,
    log_checkpoint_saved,
    log_checkpoint_restored,
    timed,
    LogContext,
    AsyncLogContext,
)

__all__ = [
    # Main entry point
    "SupervisorAgent",
    "SupervisorConfig",
    # Sub-agents
    "ParserAgent",
    "CodeReviewAgent",
    "UnitTestAgent",
    "BaseAgent",
    "AgentConfig",
    # Supervisor components
    "IntentParser",
    "ResultAggregator",
    # Request/Response types
    "ReviewRequest",
    "SupervisorOutput",
    "FileInfo",
    "UserIntent",
    "KBContext",
    "AgentStatus",
    "CheckpointData",
    # Parser types
    "ParserOutput",
    "FileMetadata",
    "Symbol",
    "SymbolType",
    "CallGraphEntry",
    "Hotspot",
    # Review types
    "ReviewOutput",
    "ReviewIssue",
    "Severity",
    # Test types
    "TestOutput",
    "GeneratedTest",
    # LLM Factory
    "LLMFactory",
    "LLMProvider",
    "LLMConfig",
    "create_openai_llm",
    "create_anthropic_llm",
    "create_openrouter_llm",
    # Logging
    "setup_logging",
    "get_logger",
    "set_session_id",
    "get_session_id",
    "log_with_data",
    "log_workflow_transition",
    "log_agent_start",
    "log_agent_complete",
    "log_llm_call",
    "log_checkpoint_saved",
    "log_checkpoint_restored",
    "timed",
    "LogContext",
    "AsyncLogContext",
]
