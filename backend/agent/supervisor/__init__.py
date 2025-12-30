"""
Supervisor Module

Orchestrates the multi-agent code review pipeline:
- SupervisorAgent: Main orchestration
- Reducer: Merge and deduplicate results
- KBFilter: Filter suggestions using Knowledge Base
"""

from agent.supervisor.reducer import Reducer, reduce_issues
from agent.supervisor.kb_filter import KBFilter, filter_with_kb
from agent.supervisor.supervisor_agent import SupervisorAgent

__all__ = [
    "SupervisorAgent",
    "Reducer",
    "reduce_issues",
    "KBFilter",
    "filter_with_kb",
]
