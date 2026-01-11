"""
Supervisor Configuration

Configuration dataclass for the Supervisor Agent.
"""

from dataclasses import dataclass
from typing import Optional

from ..llm_factory import LLMProvider


@dataclass
class SupervisorConfig:
    """Configuration for the Supervisor Agent."""
    
    # LLM settings
    llm_provider: LLMProvider = LLMProvider.OPENAI
    llm_model: Optional[str] = None
    
    # Knowledge Base settings
    kb_url: Optional[str] = None
    kb_enabled: bool = True
    kb_elasticsearch_url: Optional[str] = None
    
    # E2B Sandbox settings
    sandbox_enabled: bool = True  # Use E2B sandbox for isolation
    sandbox_timeout_ms: int = 300_000  # 5 minutes
    sandbox_template_id: Optional[str] = None  # Custom template or use default
    
    # Execution settings
    timeout_seconds: float = 600.0  # 10 minutes total
    max_retries: int = 3
    
    # Checkpointing - uses database for persistence
    enable_checkpointing: bool = True
    
    # Mock mode for testing
    use_mock_agents: bool = False
