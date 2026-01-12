"""
Supervisor State

TypedDict state definition for the LangGraph supervisor workflow.
"""

from typing import Any, Dict, List, TypedDict


class SupervisorState(TypedDict, total=False):
    """State for the LangGraph supervisor workflow."""
    
    # Input
    request: Dict[str, Any]  # Serialized ReviewRequest
    session_id: str
    
    # Parsed intent
    intent: Dict[str, Any]  # Serialized UserIntent
    
    # Knowledge Base context
    kb_context: Dict[str, Any]  # Serialized KBContext
    
    # Sandbox state
    sandbox_repo_path: str  # Path to cloned repo inside sandbox
    sandbox_active: bool    # Whether sandbox is active
    
    # Agent outputs
    parser_output: Dict[str, Any]
    review_output: Dict[str, Any]
    test_output: Dict[str, Any]
    
    # Agent results with status
    parser_result: Dict[str, Any]
    review_result: Dict[str, Any]
    test_result: Dict[str, Any]
    
    # Workflow control
    current_step: str
    completed_steps: List[str]
    errors: List[str]
    
    # Final output
    final_output: Dict[str, Any]
    
    # Timing
    started_at: str
    completed_at: str
